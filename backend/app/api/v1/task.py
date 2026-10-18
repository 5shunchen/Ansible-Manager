"""任务与 Playbook 路由（含任务日志 WS）。"""
from fastapi import APIRouter, Body, Depends, Query, WebSocket, WebSocketDisconnect

from app.api.deps import CurrentUser, DbDep, PageDep, require_perm
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.response import ok, paginated
from app.core.scope import scope_value
from app.models.task import TaskEvent, TaskTarget
from app.schemas.task import PlaybookCreate, PlaybookFileWrite, PlaybookOut, PlaybookUpdate, TaskCreate, TaskOut, TaskTargetOut
from app.services import playbook_service, task_service
from app.ws.task_log_manager import task_log_manager

# ---------- Playbook ----------
playbooks_router = APIRouter(prefix="/playbooks", tags=["playbooks"])


@playbooks_router.get("")
async def list_playbooks(db: DbDep, _: CurrentUser, keyword: str = Query(None)):
    rows = await playbook_service.list_playbooks(db, keyword)
    return ok(data=[PlaybookOut.model_validate(p).model_dump() for p in rows])


@playbooks_router.get("/scan")
async def scan_agent_playbooks(db: DbDep, _: CurrentUser):
    """扫描当前作用域 Agent 主机的 playbook_dir（如 /opt/ansible），列出所有 playbook 文件。"""
    return ok(data=await playbook_service.scan_agent_playbooks(db))


@playbooks_router.post("/debug")
async def debug_playbook(
    db: DbDep, _: CurrentUser,
    path: str = Body(...),
    host_ids: list[int] = Body(default=[]),
):
    """调试指定路径的 playbook 文件：临时创建任务并立即执行。"""
    from app.models.host import Host
    agent = await db.get(Host, scope_value())
    if not agent or not agent.playbook_dir:
        raise NotFoundError("当前未选 Agent 主机或未配置 playbook 目录")
    from pathlib import Path
    pb_root = Path(agent.playbook_dir).resolve()
    target = (pb_root / path).resolve() if not path.startswith("/") else Path(path)
    if not str(target).startswith(str(pb_root)):
        raise ValidationAppError("非法路径")
    if not target.exists():
        raise NotFoundError(f"文件不存在: {path}")
    targets = host_ids or [agent.id]
    result = await task_service.run_debug_playbook(db, str(target), targets, agent)
    return ok(data=result)


@playbooks_router.post("/write-file")
async def write_playbook_file(
    db: DbDep, _: CurrentUser,
    path: str = Body(...),
    content: str = Body(""),
):
    """在当前 Agent 主机的 playbook_dir 下写 yml 文件（新增/覆盖）。"""
    from app.models.host import Host
    agent = await db.get(Host, scope_value())
    if not agent or not agent.playbook_dir:
        raise NotFoundError("当前未选 Agent 主机或未配置 playbook 目录")
    from pathlib import Path
    pb_root = Path(agent.playbook_dir).resolve()
    target = (pb_root / path).resolve()
    if not str(target).startswith(str(pb_root)):
        raise ValidationAppError("非法路径")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return ok(data={"path": str(target)})


@playbooks_router.get("/read-file")
async def read_playbook_file(db: DbDep, _: CurrentUser, path: str = Query(...)):
    """读取 playbook_dir 下指定 yml 文件内容。"""
    from app.models.host import Host
    agent = await db.get(Host, scope_value())
    if not agent or not agent.playbook_dir:
        raise NotFoundError("当前未选 Agent 主机或未配置 playbook 目录")
    from pathlib import Path
    pb_root = Path(agent.playbook_dir).resolve()
    target = Path(path).resolve() if path.startswith("/") else (pb_root / path).resolve()
    if not str(target).startswith(str(pb_root)):
        raise ValidationAppError("非法路径")
    if not target.exists():
        raise NotFoundError(f"文件不存在: {path}")
    return ok(data={"content": target.read_text(encoding="utf-8")})


@playbooks_router.delete("/file")
async def delete_playbook_file(db: DbDep, _: CurrentUser, path: str = Query(...)):
    """删除 playbook_dir 下指定 yml 文件。"""
    from app.models.host import Host
    agent = await db.get(Host, scope_value())
    if not agent or not agent.playbook_dir:
        raise NotFoundError("当前未选 Agent 主机或未配置 playbook 目录")
    from pathlib import Path
    pb_root = Path(agent.playbook_dir).resolve()
    target = Path(path).resolve() if path.startswith("/") else (pb_root / path).resolve()
    if not str(target).startswith(str(pb_root)):
        raise ValidationAppError("非法路径")
    if not target.exists():
        raise NotFoundError(f"文件不存在: {path}")
    target.unlink()
    return ok(data={"deleted": str(target)})


@playbooks_router.get("/{pid}/files")
async def list_files(pid: int, db: DbDep, _: CurrentUser):
    return ok(data=await playbook_service.list_files(db, pid))


@playbooks_router.get("/{pid}/files/content")
async def read_file(pid: int, db: DbDep, _: CurrentUser, path: str = Query(...)):
    return ok(data={"path": path, "content": await playbook_service.read_file(db, pid, path)})


@playbooks_router.put("/{pid}/files/content")
async def write_file(pid: int, req: PlaybookFileWrite, db: DbDep, __: CurrentUser,
                     _: None = Depends(require_perm("playbook:update"))):
    await playbook_service.write_file(db, pid, req.path, req.content)
    return ok(message="已保存")


@playbooks_router.post("", dependencies=[Depends(require_perm("playbook:create"))])
async def create_playbook(req: PlaybookCreate, db: DbDep, user: CurrentUser):
    p = await playbook_service.create_playbook(db, req, created_by=user.username)
    return ok(data=PlaybookOut.model_validate(p).model_dump())


@playbooks_router.put("/{pid}", dependencies=[Depends(require_perm("playbook:update"))])
async def update_playbook(pid: int, req: PlaybookUpdate, db: DbDep):
    p = await playbook_service.update_playbook(db, pid, req)
    return ok(data=PlaybookOut.model_validate(p).model_dump())


@playbooks_router.post("/{pid}/validate")
async def validate_playbook(pid: int, db: DbDep, _: CurrentUser, path: str = Query(None)):
    return ok(data=await playbook_service.validate_playbook(db, pid, path))


@playbooks_router.delete("/{pid}", dependencies=[Depends(require_perm("playbook:delete"))])
async def delete_playbook(pid: int, db: DbDep):
    await playbook_service.delete_playbook(db, pid)
    return ok(message="已删除")


# ---------- Task ----------
tasks_router = APIRouter(prefix="/tasks", tags=["tasks"])


@tasks_router.get("")
async def list_tasks(db: DbDep, _: CurrentUser, page: PageDep,
                     status: str = Query(None), task_type: str = Query(None)):
    rows, total = await task_service.list_tasks(
        db, offset=page.offset, limit=page.page_size, status=status, task_type=task_type
    )
    return paginated([TaskOut.model_validate(t).model_dump() for t in rows], total, page.page, page.page_size)


@tasks_router.post("", dependencies=[Depends(require_perm("task:execute"))])
async def create_task(req: TaskCreate, db: DbDep, user: CurrentUser):
    from app.runner.task_worker import task_worker

    task_worker.start()
    task = await task_service.create_task(db, req, triggered_by=user.username)
    return ok(data=TaskOut.model_validate(task).model_dump())


@tasks_router.get("/{task_id}")
async def get_task(task_id: int, db: DbDep, _: CurrentUser):
    from sqlalchemy import select

    task = await task_service.get_task(db, task_id)
    targets = (await db.execute(
        select(TaskTarget).where(TaskTarget.task_id == task_id)
    )).scalars().all()
    return ok(data={
        "task": TaskOut.model_validate(task).model_dump(),
        "targets": [TaskTargetOut.model_validate(t).model_dump() for t in targets],
    })


@tasks_router.get("/{task_id}/events")
async def list_events(task_id: int, db: DbDep, _: CurrentUser,
                      after_seq: int = Query(0), limit: int = Query(500, le=2000)):
    rows = await task_service.list_events(db, task_id, after_seq=after_seq, limit=limit)
    return ok(data=[
        {"id": e.id, "seq": e.seq, "ts": e.ts, "level": e.level, "host": e.host, "message": e.message}
        for e in rows
    ])


@tasks_router.post("/{task_id}/cancel", dependencies=[Depends(require_perm("task:cancel"))])
async def cancel_task(task_id: int, db: DbDep):
    t = await task_service.cancel_task(db, task_id)
    return ok(data=TaskOut.model_validate(t).model_dump())


@tasks_router.delete("/{task_id}", dependencies=[Depends(require_perm("task:delete"))])
async def delete_task(task_id: int, db: DbDep):
    await task_service.delete_task(db, task_id)
    return ok(message="已删除")


# ---------- 任务日志 WS ----------
ws_router = APIRouter(prefix="/ws", tags=["ws"])


@ws_router.websocket("/tasks/{task_id}/logs")
async def task_logs_ws(ws: WebSocket, task_id: int):
    """实时任务日志：token 走 query 参数；连接即补发历史，随后实时推送。"""
    from app.db.session import AsyncSessionLocal
    from app.core.security import decode_token
    from app.core.exceptions import AuthError

    token = ws.query_params.get("token", "")
    try:
        payload = decode_token(token) if token else None
        if not payload:
            raise AuthError("未认证")
    except AuthError:
        await ws.close(code=4401)
        return

    await ws.accept()
    await task_log_manager.subscribe(task_id, ws)

    # 补发历史
    async with AsyncSessionLocal() as db:
        task = await task_service.get_task(db, task_id)
        events = await task_service.list_events(db, task_id, limit=500)
        await ws.send_json({"type": "task_status", "task_id": task_id, "status": task.status})
        for e in events:
            await ws.send_json({"type": "task_event", "task_id": task_id, "seq": e.seq,
                                "ts": e.ts, "level": e.level, "host": e.host, "message": e.message})

    try:
        while True:
            # 客户端心跳/断线检测
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await task_log_manager.unsubscribe(task_id, ws)
