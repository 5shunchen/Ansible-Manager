"""应用主机上的 App（插件包）安装/卸载/列表。"""
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbDep, require_perm
from app.core.response import ok
from app.services import app_service

apps_router = APIRouter(prefix="/apps", tags=["apps"])


class AppInstallBody(BaseModel):
    host_id: int
    plugin_id: int
    extra_vars: Optional[dict[str, Any]] = None


class AppUninstallBody(BaseModel):
    host_id: int
    plugin_id: int


@apps_router.get("/host/{host_id}")
async def list_host_apps(host_id: int, db: DbDep, _: CurrentUser):
    rows = await app_service.list_host_apps(db, host_id)
    return ok(data=rows)


@apps_router.post("/install", dependencies=[Depends(require_perm("app:install"))])
async def install_app(body: AppInstallBody, db: DbDep, user: CurrentUser):
    ha = await app_service.install_app(
        db, host_id=body.host_id, plugin_id=body.plugin_id,
        extra_vars=body.extra_vars, username=user.username,
    )
    return ok(data={"id": ha.id, "host_id": ha.host_id, "plugin_id": ha.plugin_id,
                    "status": ha.status, "last_task_id": ha.last_task_id})


@apps_router.post("/uninstall", dependencies=[Depends(require_perm("app:uninstall"))])
async def uninstall_app(body: AppUninstallBody, db: DbDep, user: CurrentUser):
    ha = await app_service.uninstall_app(
        db, host_id=body.host_id, plugin_id=body.plugin_id, username=user.username,
    )
    return ok(data={"id": ha.id, "status": ha.status, "last_task_id": ha.last_task_id})
