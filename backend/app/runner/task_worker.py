"""任务队列消费 worker：状态机 + 并发控制 + 超时 + 取消 + 事件落库与广播。"""
import asyncio
import contextlib
import time
from datetime import datetime, timezone
from app.core.time import now_cn

from app.core.logging import get_logger
from app.ws.task_log_manager import task_log_manager

logger = get_logger(__name__)


def now() -> datetime:
    return now_cn()


# ansible-runner 状态 → 平台任务状态
STATUS_MAP = {"successful": "success", "failed": "failed", "canceled": "canceled", "timeout": "timeout"}


class TaskWorker:
    """单进程内嵌任务队列。start() 在 app lifespan 中调用。"""

    def __init__(self):
        self.queue: asyncio.Queue[int] = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(5)
        self.registry: dict[int, object] = {}  # task_id → RunningHandle（cancel 用）
        self._loop_task: asyncio.Task | None = None
        self._results: dict[int, tuple[str, int]] = {}  # task_id → (status, rc)
        self._event_chains: dict[int, asyncio.Task] = {}  # task_id → 最后一个事件落库协程（串行化）

    def start(self) -> None:
        if self._loop_task is None:
            self._loop_task = asyncio.get_event_loop().create_task(self._loop())
            logger.info("task_worker_started")

    async def stop(self) -> None:
        if self._loop_task:
            self._loop_task.cancel()
            self._loop_task = None

    async def submit(self, task_id: int) -> None:
        await self.queue.put(task_id)

    def cancel(self, task_id: int) -> bool:
        handle = self.registry.get(task_id)
        if handle is None:
            return False
        handle.cancel()
        return True

    # ---- 内部 ----
    async def _loop(self) -> None:
        while True:
            task_id = await self.queue.get()
            asyncio.get_event_loop().create_task(self._run_one(task_id))

    async def _run_one(self, task_id: int) -> None:
        from app.db.session import AsyncSessionLocal
        from app.models.task import Task
        from app.runner.ansible_executor import AnsibleExecutor
        from app.services import task_service

        async with AsyncSessionLocal() as db:
            task = await db.get(Task, task_id)
            if not task or task.status in ("success", "failed", "canceled", "timeout"):
                return
            task.status = "running"
            task.started_at = now()
            await db.commit()
            try:
                spec = await task_service.load_task_spec(db, task)
            except Exception as e:  # noqa: BLE001
                task.status, task.message = "failed", f"任务准备失败: {e}"
                task.finished_at = now()
                await db.commit()
                return

        executor = AnsibleExecutor()
        loop = asyncio.get_event_loop()
        counter = {"seq": 0}

        def on_event(ev: dict) -> None:
            """在 ansible-runner 线程中被调用 → 桥接回 asyncio。

            每个任务的事件落库串行成链，保证 seq 顺序提交、target 状态不被并发覆盖。
            """
            counter["seq"] += 1
            payload = task_service.extract_event(task_id, counter["seq"], ev)
            if payload:
                prev = self._event_chains.get(task_id)

                async def _chained(p=payload, pr=prev):
                    if pr is not None:
                        with contextlib.suppress(Exception):
                            await pr
                    await self._persist_and_broadcast(p)

                self._event_chains[task_id] = loop.create_task(_chained())

        started = time.monotonic()
        try:
            status, rc = await asyncio.wait_for(
                asyncio.to_thread(executor.run, spec, on_event),
                timeout=spec.timeout_seconds + 120,
            )
        except asyncio.TimeoutError:
            status, rc = "timeout", -1
            executor.handles.get(task_id) and executor.handles[task_id].kill()
        except Exception as e:  # noqa: BLE001
            logger.error("task_execute_error", task_id=task_id, error=str(e))
            status, rc = "failed", -1

        final_status = STATUS_MAP.get(status, "failed")
        async with AsyncSessionLocal() as db:
            task = await db.get(Task, task_id)
            if task:
                task.status = final_status
                task.rc = rc
                task.finished_at = now()
                task.duration_ms = int((time.monotonic() - started) * 1000)
                task.message = task.message or {
                    "timeout": "任务执行超时", "canceled": "任务已取消",
                }.get(final_status)
                # 汇总 stats
                try:
                    task.stats = await task_service.collect_stats(db, task_id)
                except Exception:  # noqa: BLE001
                    pass
                await db.commit()
                # 部署任务联动
                if task.deploy_record_id:
                    from app.services import deploy_service

                    await deploy_service.on_task_finished(db, task)
                # App 安装任务联动：回写 HostApp.status
                if task.task_type in ("app_install", "app_uninstall"):
                    from app.services import app_service

                    with contextlib.suppress(Exception):
                        await app_service.on_task_finished(db, task)

        await task_log_manager.broadcast(task_id, {
            "type": "task_status", "task_id": task_id, "status": final_status, "rc": rc,
        })

    async def _persist_and_broadcast(self, payload: dict) -> None:
        """事件持久化 + WS 广播 + task_target 状态推进。"""
        from sqlalchemy import select

        from app.db.session import AsyncSessionLocal
        from app.models.host import Host
        from app.models.task import TaskEvent, TaskTarget

        async with AsyncSessionLocal() as db:
            db.add(TaskEvent(
                task_id=payload["task_id"], seq=payload["seq"], ts=payload.get("ts"),
                level=payload["level"], host=payload.get("host") or "",
                message=payload.get("message", ""), raw_event=payload.get("raw_event"),
            ))
            if payload.get("host"):
                host = (await db.execute(select(Host).where(Host.hostname == payload["host"]))).scalar_one_or_none()
                if host:
                    tgt = (await db.execute(select(TaskTarget).where(
                        TaskTarget.task_id == payload["task_id"],
                        TaskTarget.host_id == host.id,
                    ))).scalar_one_or_none()
                    if tgt:
                        tgt.status = payload["target_status"]
                        if payload["target_status"] in ("ok", "failed", "unreachable"):
                            tgt.finished_at = now()
            await db.commit()

        await task_log_manager.broadcast(payload["task_id"], {
            "type": "task_event", **{k: v for k, v in payload.items() if k != "raw_event"},
        })


task_worker = TaskWorker()
