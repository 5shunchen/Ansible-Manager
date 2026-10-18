"""任务服务：创建/查询/取消 + 事件提炼 + TaskSpec 组装。"""
from datetime import datetime, timezone
from app.core.time import now_cn

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.scope import scope_conds, scope_value
from app.core.config import settings
from app.models.host import Host, HostGroup
from app.models.task import Playbook, Task, TaskEvent, TaskTarget
from app.schemas.task import TaskCreate


def now() -> datetime:
    return now_cn()


# ---------- 创建与查询 ----------
async def create_task(db: AsyncSession, req: TaskCreate, triggered_by: str, *,
                     task_type: str = "playbook", playbook_id: int | None = None,
                     name: str | None = None, extra_vars: dict | None = None,
                     host_ids: list[int] | None = None, deploy_record_id: int | None = None,
                     playbook_content: str | None = None) -> Task:
    """通用任务创建（playbook 任务与部署任务共用）。

    playbook_content 必须在这里一次落库：submit 之后 worker 会立刻读取 inventory，
    若在 create_task 返回后再补写，worker 可能已按空 playbook 处理而失败。
    """
    pb_id = playbook_id if playbook_id is not None else (req.playbook_id if req else None)
    playbook = None
    if pb_id is not None:
        playbook = await db.get(Playbook, pb_id)
        if not playbook:
            raise NotFoundError("Playbook 不存在")
    ids = host_ids if host_ids is not None else (req.host_ids if req else [])
    if not ids and not (req.group_ids if req else []):
        raise ValidationAppError("目标主机不能为空")
    hosts = list((await db.execute(select(Host).where(Host.id.in_(ids)))).scalars().all()) if ids else []
    if not hosts:
        raise NotFoundError("目标主机不存在")

    inv_snapshot: dict = {"host_ids": ids or [], "group_ids": (req.group_ids if req else [])}
    if playbook_content:
        inv_snapshot["playbook_content"] = playbook_content
    task = Task(
        name=name or (req.name if req else "任务"), task_type=task_type, playbook_id=pb_id,
        inventory=inv_snapshot,
        agent_host_id=scope_value(),
        extra_vars=extra_vars or (req.extra_vars if req else None),
        status="pending", triggered_by=triggered_by,
        deploy_record_id=deploy_record_id,
        timeout_seconds=(req.timeout_seconds if req else None) or settings.task_default_timeout,
    )
    db.add(task)
    await db.flush()
    for h in hosts:
        db.add(TaskTarget(task_id=task.id, host_id=h.id))
    await db.commit()
    await db.refresh(task)

    from app.runner.task_worker import task_worker

    await task_worker.submit(task.id)
    task.status = "queued"
    await db.commit()
    return task


async def get_task(db: AsyncSession, task_id: int) -> Task:
    t = await db.get(Task, task_id)
    if not t:
        raise NotFoundError("任务不存在")
    return t


async def list_tasks(db: AsyncSession, *, offset: int = 0, limit: int = 20,
                     status: str | None = None, task_type: str | None = None) -> tuple[list[Task], int]:
    conditions = []
    if status:
        conditions.append(Task.status == status)
    if task_type:
        conditions.append(Task.task_type == task_type)
    conditions.extend(scope_conds(Task))
    stmt = select(Task)
    count_stmt = select(func.count()).select_from(Task)
    if conditions:
        from sqlalchemy import and_

        stmt = stmt.where(and_(*conditions))
        count_stmt = count_stmt.where(and_(*conditions))
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (await db.execute(stmt.order_by(Task.id.desc()).offset(offset).limit(limit))).scalars().all()
    return list(rows), total


async def list_events(db: AsyncSession, task_id: int, after_seq: int = 0, limit: int = 500) -> list[TaskEvent]:
    stmt = select(TaskEvent).where(TaskEvent.task_id == task_id)
    if after_seq:
        stmt = stmt.where(TaskEvent.seq > after_seq)
    return list((await db.execute(stmt.order_by(TaskEvent.seq).limit(limit))).scalars().all())


async def delete_task(db: AsyncSession, task_id: int) -> None:
    t = await get_task(db, task_id)
    if t.status in ("pending", "queued", "running"):
        raise ValidationAppError("运行中的任务不可删除")
    await db.delete(t)
    await db.commit()


async def cancel_task(db: AsyncSession, task_id: int) -> Task:
    t = await get_task(db, task_id)
    if t.status not in ("pending", "queued", "running"):
        raise ValidationAppError(f"任务状态 {t.status} 不可取消")
    from app.runner.task_worker import task_worker

    task_worker.cancel(task_id)
    t.status = "canceled"
    t.message = "任务已取消"
    t.finished_at = now()
    await db.commit()
    return t


async def collect_stats(db: AsyncSession, task_id: int) -> dict:
    rows = (await db.execute(select(TaskTarget).where(TaskTarget.task_id == task_id))).scalars().all()
    stats = {"ok": 0, "changed": 0, "failed": 0, "unreachable": 0, "skipped": 0}
    for r in rows:
        if r.status in stats:
            stats[r.status] += 1
    return stats


# ---------- 执行准备 ----------
async def load_task_spec(db: AsyncSession, task: Task):
    """Task → TaskSpec（inventory 快照展开 + private_data_dir 生成）。"""
    from app.runner.interfaces import TaskSpec
    from app.runner.inventory import prepare_task_dir

    inv = task.inventory or {}
    host_ids = inv.get("host_ids", [])
    group_ids = inv.get("group_ids", [])
    stmt = select(Host)
    if host_ids:
        stmt = stmt.where(Host.id.in_(host_ids))
    if group_ids:
        from app.models.host import HostGroupMember

        stmt = stmt.where(Host.id.in_(select(HostGroupMember.c.host_id).where(HostGroupMember.c.group_id.in_(group_ids))))
    hosts = list((await db.execute(stmt)).scalars().unique().all())
    if not hosts:
        raise NotFoundError("任务目标主机不存在或已删除")

    playbook = await db.get(Playbook, task.playbook_id) if task.playbook_id else None
    rendered = inv.get("playbook_content")
    if playbook is None and not rendered:
        raise NotFoundError("任务缺少 playbook")
    task_dir = await prepare_task_dir(task.id, hosts, playbook, playbook_content=rendered)
    return TaskSpec(
        task_id=task.id,
        private_data_dir=task_dir,
        playbook_entry=(playbook.entry_file if playbook else "site.yml"),
        extra_vars=task.extra_vars or {},
        timeout_seconds=task.timeout_seconds or settings.task_default_timeout,
    )


# ---------- 事件提炼 ----------
TARGET_STATUS = {
    "runner_on_start": "running",
    "runner_on_ok": "ok", "runner_on_failed": "failed",
    "runner_on_unreachable": "unreachable", "runner_on_skipped": "skipped",
}


def extract_event(task_id: int, seq: int, ev: dict) -> dict | None:
    """ansible-runner 原始事件 → 平台事件 payload；无价值事件返回 None。"""
    event_key = ev.get("event", "")
    if event_key == "verbose":
        level = ev.get("level2", "debug") or "debug"
        return {"task_id": task_id, "seq": seq, "ts": now(), "level": level,
                "host": ev.get("host") or "", "message": ev.get("stdout") or "",
                "event_key": event_key, "raw_event": ev}
    if not event_key.startswith("runner_on") and event_key not in ("playbook_on_start", "playbook_on_stats"):
        return None
    event_data = ev.get("event_data", {}) or {}
    host = event_data.get("host") or ""
    message = ev.get("stdout") or _summarize(event_key, event_data)
    level = "error" if event_key == "runner_on_failed" or event_key == "runner_on_unreachable" else "info"
    payload = {
        "task_id": task_id, "seq": seq, "ts": now(), "level": level, "host": host,
        "message": message.strip()[:8000], "event_key": event_key,
        "target_status": TARGET_STATUS.get(event_key), "raw_event": ev,
    }
    if event_key == "playbook_on_stats":
        payload["message"] = ev.get("stdout") or "playbook 统计"
        payload["raw_event"] = ev
    return payload


def _summarize(event_key: str, data: dict) -> str:
    task_name = data.get("task") or ""
    res = data.get("res") or {}
    reason = data.get("reason") or res.get("msg") or res.get("stderr") or ""
    action = data.get("task_action") or ""
    if event_key == "runner_on_failed":
        return f"任务失败 [{action}] {task_name}: {reason}"
    if event_key == "runner_on_unreachable":
        return f"主机不可达: {reason}"
    if event_key == "runner_on_ok":
        msg = res.get("msg") or res.get("stdout") or ""
        changed = " [changed]" if data.get("changed") else ""
        return f"执行成功{changed} [{action}] {task_name} {msg}".strip()
    if event_key == "runner_on_start":
        return f"开始执行 [{action}] {task_name}"
    if event_key == "runner_on_skipped":
        return f"跳过 [{action}] {task_name}"
    if event_key == "playbook_on_start":
        return f"Playbook 开始: {data.get('name', '')}"
    return task_name or event_key


async def run_debug_playbook(db: AsyncSession, playbook_path: str, host_ids: list[int], agent) -> dict:
    """调试指定路径的 playbook 文件：直接用 ansible-playbook 跑（不依赖 DB playbook）。"""
    import subprocess
    import tempfile
    from pathlib import Path
    from app.services.host_service import build_ssh_target

    hosts = list((await db.execute(select(Host).where(Host.id.in_(host_ids)))).scalars().all())
    if not hosts:
        raise NotFoundError("目标主机不存在")

    inv_lines = []
    for h in hosts:
        target = await build_ssh_target(db, h)
        inv_lines.append(
            f"{h.ip} ansible_port={h.port} ansible_user={target.username} "
            f"ansible_ssh_pass='{target.password}' ansible_ssh_common_args='-o StrictHostKeyChecking=no'"
        )

    with tempfile.TemporaryDirectory() as tmp:
        inv_path = Path(tmp) / "inventory.ini"
        inv_path.write_text("\n".join(inv_lines))
        import shutil
        ansible_bin = shutil.which("ansible-playbook")
        if not ansible_bin:
            return {
                "path": playbook_path,
                "rc": -1,
                "stdout": f"[调试模拟] inventory 已生成：{inv_path}\n命令：ansible-playbook -i {inv_path} {playbook_path}\n（控制端未安装 ansible-playbook，仅生成命令）",
                "stderr": "控制端缺少 ansible-playbook",
            }
        cmd = [ansible_bin, "-i", str(inv_path), playbook_path]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    return {
        "path": playbook_path,
        "rc": proc.returncode,
        "stdout": proc.stdout[-3000:],
        "stderr": proc.stderr[-1000:],
    }
