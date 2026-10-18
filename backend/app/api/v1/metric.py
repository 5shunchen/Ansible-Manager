"""监控路由：指标历史 / 快照 / 大屏概览。"""
from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbDep, require_perm
from app.core.exceptions import NotFoundError
from app.core.response import ok
from app.services import host_service, metric_service

metrics_router = APIRouter(prefix="/metrics", tags=["metrics"])
dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@metrics_router.get("/hosts/{host_id}/history")
async def host_history(host_id: int, db: DbDep, _: CurrentUser,
                       metric: str = Query("cpu_usage"),
                       minutes: int = Query(60, ge=5, le=1440),
                       points: int = Query(60, ge=10, le=300)):
    await host_service.get_host(db, host_id)  # 存在性校验
    data = await metric_service.host_history(db, host_id, metric, minutes, points)
    return ok(data={"metric": metric, "points": data})


@metrics_router.get("/hosts/{host_id}/current")
async def current_snapshot(host_id: int, db: DbDep, _: CurrentUser):
    await host_service.get_host(db, host_id)
    snap = await metric_service.latest_snapshot(db, host_id)
    if not snap:
        return ok(data=None, message="暂无采集数据")
    snap["disks"] = await metric_service.latest_disks(db, host_id)
    return ok(data=snap)


@dashboard_router.get("/overview")
async def overview(db: DbDep, _: CurrentUser):
    return ok(data=await metric_service.dashboard_overview(db))
