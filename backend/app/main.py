"""应用入口：create_app + lifespan（建表/seed/调度器/中断任务恢复）。"""
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import request_id_var, setup_logging
from app.core.response import error

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.debug)
    # 建表 + seed（alembic 用于生产演进；开发期直接 create_all 兜底）
    from app.db.base import Base
    from app.db.init_db import init_db
    from app.db.migrate import ensure_schema
    from app.db.session import AsyncSessionLocal, engine
    import app.models  # noqa: F401 导入即注册全部表到 metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # create_all 不会给已有表加列，这里幂等补齐（老库升级路径）
    await ensure_schema(engine)
    async with AsyncSessionLocal() as db:
        await init_db(db)

    # 历史数据归属：归到第一台 Agent 主机；库里还没有则跳过，用户建好后再触发
    from app.db.backfill import backfill_agent_scope
    async with AsyncSessionLocal() as db:
        await backfill_agent_scope(db)

    # 启动恢复：中断任务置 failed
    from sqlalchemy import update

    from app.models.task import Task
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Task)
            .where(Task.status.in_(["pending", "queued", "running"]))
            .values(status="failed", message="服务重启导致任务中断")
        )
        await db.commit()

    # 任务队列 worker
    from app.runner.task_worker import task_worker

    task_worker.start()

    # 定时调度器（监控采集/健康检查/数据清理）
    from app.workers.scheduler import build_scheduler

    scheduler = build_scheduler()
    scheduler.start()

    yield

    scheduler.shutdown(wait=False)
    await task_worker.stop()
    from app.db.session import engine as _engine

    await _engine.dispose()


def _mount_frontend(app: FastAPI) -> None:
    """单端口模式：把前端构建产物挂到后端同一端口。

    命中真实静态文件则返回文件，否则回落 index.html 交给前端路由（SPA）。
    /api、/docs 等后端自身路径不参与回落，保持原有 404/文档行为。
    """
    dist = settings.static_dir
    index = dist / "index.html"
    if not index.exists():
        logger.info("未发现前端构建产物 %s，跳过挂载（前后端分离开发模式）", dist)
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    dist_root = dist.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.startswith(("api/", "docs", "redoc", "openapi.json")):
            return JSONResponse(status_code=404, content={"code": 40400, "message": "Not Found", "data": None})
        candidate = (dist_root / full_path).resolve()
        # 防目录穿越：只允许读取 dist 内部文件
        if full_path and candidate.is_file() and candidate.is_relative_to(dist_root):
            return FileResponse(candidate)
        return FileResponse(index)

    logger.info("已挂载前端构建产物：%s（单端口模式）", dist)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request_id_var.set(rid)
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response

    app.include_router(api_router)
    register_exception_handlers(app)

    @app.get("/api/v1/healthz")
    async def healthz():
        return {"code": 0, "message": "ok", "data": None}

    # 单端口模式：前端产物挂在最后，避免抢占 /api 路由
    _mount_frontend(app)

    return app


app = create_app()
