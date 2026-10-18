"""部署工程与部署记录路由。"""
from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbDep, PageDep, require_perm
from app.core.response import ok, paginated
from app.schemas.deployment import (
    DeployActionRequest, DeployProjectCreate, DeployProjectOut, DeployProjectUpdate, DeployRecordOut,
)
from app.services import deploy_service, task_service
from app.runner.task_worker import task_worker

deploy_router = APIRouter(prefix="/deploy-projects", tags=["deployment"])


def _to_out(p) -> dict:
    data = {k: getattr(p, k) for k in (
        "id", "name", "code", "project_id", "registry_url", "image_repo", "default_tag",
        "build_type", "build_host_id", "build_context", "dockerfile", "build_args",
        "runtime", "namespace", "env", "ports", "mounts", "labels", "network", "restart_policy",
        "healthcheck", "pre_cmd", "post_cmd", "pull_policy", "rollback_enabled", "created_by",
        "created_at")}
    data["host_ids"] = [h.host_id for h in p.hosts]
    return data


@deploy_router.get("")
async def list_deploy_projects(db: DbDep, _: CurrentUser, keyword: str = Query(None)):
    rows = await deploy_service.list_projects(db, keyword)
    return ok(data=[_to_out(p) for p in rows])


@deploy_router.get("/{pid}")
async def get_deploy_project(pid: int, db: DbDep, _: CurrentUser):
    p = await deploy_service.get_project(db, pid)
    data = _to_out(p)
    data["hosts"] = [{"host_id": h.host_id, "container_name": h.container_name, "enabled": h.enabled} for h in p.hosts]
    return ok(data=data)


@deploy_router.post("", dependencies=[Depends(require_perm("deploy:create"))])
async def create_deploy_project(req: DeployProjectCreate, db: DbDep, user: CurrentUser):
    p = await deploy_service.create_project(db, req, created_by=user.username)
    return ok(data={"id": p.id})


@deploy_router.put("/{pid}", dependencies=[Depends(require_perm("deploy:update"))])
async def update_deploy_project(pid: int, req: DeployProjectUpdate, db: DbDep):
    p = await deploy_service.update_project(db, pid, req)
    return ok(data={"id": p.id})


@deploy_router.delete("/{pid}", dependencies=[Depends(require_perm("deploy:delete"))])
async def delete_deploy_project(pid: int, db: DbDep):
    await deploy_service.delete_project(db, pid)
    return ok(message="已删除")


@deploy_router.post("/{pid}/deploy", dependencies=[Depends(require_perm("deploy:run"))])
async def deploy(pid: int, req: DeployActionRequest, db: DbDep, user: CurrentUser):
    task_worker.start()
    record = await deploy_service.deploy(db, pid, req, user.username, action="deploy")
    return ok(data=DeployRecordOut.model_validate(record).model_dump())


@deploy_router.post("/{pid}/rollback", dependencies=[Depends(require_perm("deploy:rollback"))])
async def rollback(pid: int, req: DeployActionRequest, db: DbDep, user: CurrentUser):
    task_worker.start()
    record = await deploy_service.deploy(db, pid, req, user.username, action="rollback")
    return ok(data=DeployRecordOut.model_validate(record).model_dump())


@deploy_router.post("/{pid}/restart", dependencies=[Depends(require_perm("deploy:run"))])
async def restart(pid: int, req: DeployActionRequest, db: DbDep, user: CurrentUser):
    task_worker.start()
    record = await deploy_service.deploy(db, pid, req, user.username, action="restart")
    return ok(data=DeployRecordOut.model_validate(record).model_dump())


@deploy_router.post("/{pid}/stop", dependencies=[Depends(require_perm("deploy:run"))])
async def stop(pid: int, req: DeployActionRequest, db: DbDep, user: CurrentUser):
    task_worker.start()
    record = await deploy_service.deploy(db, pid, req, user.username, action="stop")
    return ok(data=DeployRecordOut.model_validate(record).model_dump())


@deploy_router.post("/{pid}/start", dependencies=[Depends(require_perm("deploy:run"))])
async def start(pid: int, req: DeployActionRequest, db: DbDep, user: CurrentUser):
    task_worker.start()
    record = await deploy_service.deploy(db, pid, req, user.username, action="start")
    return ok(data=DeployRecordOut.model_validate(record).model_dump())


records_router = APIRouter(prefix="/deploy-records", tags=["deployment"])


@records_router.get("")
async def list_records(db: DbDep, _: CurrentUser, page: PageDep, deploy_project_id: int = Query(None)):
    rows, total = await deploy_service.list_records(
        db, deploy_project_id, offset=page.offset, limit=page.page_size
    )
    return paginated([DeployRecordOut.model_validate(r).model_dump() for r in rows], total, page.page, page.page_size)
