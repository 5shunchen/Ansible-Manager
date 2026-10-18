"""任务日志 WS 广播管理：task_id → 订阅者集合。"""
import asyncio
from typing import Optional

from fastapi import WebSocket


class TaskLogManager:
    def __init__(self):
        self._subs: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, task_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._subs.setdefault(task_id, set()).add(ws)

    async def unsubscribe(self, task_id: int, ws: WebSocket) -> None:
        async with self._lock:
            subs = self._subs.get(task_id)
            if subs:
                subs.discard(ws)
                if not subs:
                    self._subs.pop(task_id, None)

    async def broadcast(self, task_id: int, message: dict) -> None:
        subs = self._subs.get(task_id)
        if not subs:
            return
        dead = []
        for ws in list(subs):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            await self.unsubscribe(task_id, ws)

    def subscriber_count(self, task_id: int) -> int:
        return len(self._subs.get(task_id, ()))


task_log_manager = TaskLogManager()
