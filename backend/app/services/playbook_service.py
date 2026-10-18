"""Playbook 服务：CRUD + 文件树读写 + 扫描 Agent 主机 playbook 目录。"""
import os
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.scope import apply_scope, scope_value
from app.models.host import Host
from app.models.task import Playbook
from app.schemas.task import PlaybookCreate, PlaybookUpdate


async def list_files(db: AsyncSession, pid: int) -> list[dict]:
    pb = await get_playbook(db, pid)
    root = Path(pb.disk_path)
    out = []
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            fp = Path(dirpath) / f
            rel = fp.relative_to(root).as_posix()
            st = fp.stat()
            from datetime import datetime

            out.append({
                "path": rel, "is_dir": False, "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
            })
    return out


def _validate_yaml(content: str) -> None:
    try:
        docs = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ValidationAppError(f"YAML 语法错误: {e}")
    if docs is not None and not isinstance(docs, list):
        raise ValidationAppError("Playbook 顶层应为 play 列表")


async def list_playbooks(db: AsyncSession, keyword: str | None = None) -> list[Playbook]:
    stmt = apply_scope(select(Playbook), Playbook)
    if keyword:
        stmt = stmt.where(Playbook.name.like(f"%{keyword}%"))
    return list((await db.execute(stmt.order_by(Playbook.id.desc()))).scalars().all())


async def get_playbook(db: AsyncSession, pid: int) -> Playbook:
    p = await db.get(Playbook, pid)
    if not p:
        raise NotFoundError("Playbook 不存在")
    return p


async def agent_playbook_root(agent_host_id: int) -> Path:
    """Agent 主机专属 playbook 根目录：data/playbooks/agent-{host_id}/。

    每个 Agent 主机有独立的 playbook 存放地址，创建 Agent 主机时由 host_service 预建。
    """
    return Path(settings.playbook_dir) / f"agent-{agent_host_id}"


async def create_playbook(db: AsyncSession, req: PlaybookCreate, created_by: str = "") -> Playbook:
    content = req.content or ""
    if content:
        _validate_yaml(content)
    p = Playbook(
        name=req.name, description=req.description, project_id=req.project_id,
        entry_file=req.entry_file, created_by=created_by, disk_path="pending",
        agent_host_id=scope_value(),
    )
    db.add(p)
    await db.flush()
    # 归属到 Agent 主机的 playbook 落盘到该 Agent 主机的专属目录下
    if p.agent_host_id:
        root = await agent_playbook_root(p.agent_host_id)
        root.mkdir(parents=True, exist_ok=True)
        disk_path = root / str(p.id)
    else:
        disk_path = Path(settings.playbook_dir) / str(p.id)
    disk_path.mkdir(parents=True, exist_ok=True)
    (disk_path / req.entry_file).write_text(content)
    p.disk_path = str(disk_path)
    await db.commit()
    await db.refresh(p)
    return p


async def update_playbook(db: AsyncSession, pid: int, req: PlaybookUpdate) -> Playbook:
    p = await get_playbook(db, pid)
    for f, v in req.model_dump(exclude_unset=True).items():
        setattr(p, f, v)
    await db.commit()
    return p


async def delete_playbook(db: AsyncSession, pid: int) -> None:
    p = await get_playbook(db, pid)
    await db.delete(p)
    await db.commit()
    import shutil

    shutil.rmtree(p.disk_path, ignore_errors=True)


def _safe_path(pb: Playbook, rel: str) -> Path:
    """限制文件操作在 playbook 目录内，防路径穿越。"""
    root = Path(pb.disk_path).resolve()
    target = (root / rel).resolve()
    if not str(target).startswith(str(root)):
        raise ValidationAppError("非法路径")
    return target


async def read_file(db: AsyncSession, pid: int, rel: str) -> str:
    pb = await get_playbook(db, pid)
    fp = _safe_path(pb, rel)
    if not fp.is_file():
        raise NotFoundError("文件不存在")
    return fp.read_text(encoding="utf-8")


async def write_file(db: AsyncSession, pid: int, rel: str, content: str, validate: bool = True) -> None:
    pb = await get_playbook(db, pid)
    fp = _safe_path(pb, rel)
    if validate and (rel.endswith(".yml") or rel.endswith(".yaml")):
        _validate_yaml(content)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8")


async def validate_playbook(db: AsyncSession, pid: int, rel: str | None = None) -> dict:
    """语法校验：YAML 解析 + 顶层结构检查（完整 lint 需目标机，暂不做）。"""
    pb = await get_playbook(db, pid)
    rel = rel or pb.entry_file
    content = await read_file(db, pid, rel)
    docs = yaml.safe_load(content)
    issues = []
    if docs is None:
        issues.append("文件为空")
    elif not isinstance(docs, list):
        issues.append("顶层应为 play 列表")
    else:
        for i, play in enumerate(docs):
            if not isinstance(play, dict) or "hosts" not in play:
                issues.append(f"play #{i + 1} 缺少 hosts 字段")
    return {"valid": not issues, "issues": issues}


async def scan_agent_playbooks(db: AsyncSession) -> list[dict]:
    """扫描当前作用域 Agent 主机的 playbook_dir（如 /opt/ansible），
    列出目录下所有符合 playbook 要求的 .yml/.yaml 文件。

    返回：[{name, path, agent_host_id, agent_hostname}]
    """
    scope = scope_value()
    if not scope:
        return []
    agent = await db.get(Host, scope)
    if not agent or not agent.playbook_dir:
        return []
    root = Path(agent.playbook_dir)
    if not root.exists():
        return []
    out: list[dict] = []
    for fp in sorted(root.rglob("*.yml")) + sorted(root.rglob("*.yaml")):
        # 只保留含 play 列表的 yml（符合 playbook 要求）
        try:
            docs = yaml.safe_load(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(docs, list):
            continue
        if not any(isinstance(d, dict) and "hosts" in d for d in docs):
            continue
        out.append({
            "name": fp.name,
            "path": str(fp),
            "agent_host_id": agent.id,
            "agent_hostname": agent.hostname,
        })
    return out
