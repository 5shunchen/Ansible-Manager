"""主机域路由：项目/凭据/主机组/主机(含连通检测/导入导出)。"""
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response

from app.api.deps import CurrentUser, DbDep, PageDep, TransportFactoryDep, require_perm, resolve_target
from app.core.exceptions import AppError
from app.core.response import ok, paginated
from app.schemas.host import (
    CredentialCreate, CredentialOut, CredentialUpdate, HostCheckResult, HostCreate,
    HostGroupCreate, HostGroupOut, HostGroupUpdate, HostImportResult, HostOut, HostUpdate,
    ProjectCreate, ProjectOut, ProjectUpdate,
)
from app.services import host_io_service, host_service

router = APIRouter(tags=["hosts"])


# ---------- 项目 ----------
projects_router = APIRouter(prefix="/projects", tags=["projects"])


@projects_router.get("")
async def list_projects(db: DbDep, _: CurrentUser):
    rows = await host_service.list_projects(db)
    return ok(data=[ProjectOut.model_validate(p).model_dump() for p in rows])


@projects_router.post("", dependencies=[Depends(require_perm("project:create"))])
async def create_project(req: ProjectCreate, db: DbDep, user: CurrentUser, request: Request):
    p = await host_service.create_project(db, req)
    await host_service.add_audit(db, user_id=user.id, username=user.username, action="project.create",
                                 resource_type="project", resource_id=p.id, ip=request.client.host if request.client else "")
    return ok(data=ProjectOut.model_validate(p).model_dump())


@projects_router.put("/{pid}", dependencies=[Depends(require_perm("project:update"))])
async def update_project(pid: int, req: ProjectUpdate, db: DbDep):
    p = await host_service.update_project(db, pid, req)
    return ok(data=ProjectOut.model_validate(p).model_dump())


@projects_router.delete("/{pid}", dependencies=[Depends(require_perm("project:delete"))])
async def delete_project(pid: int, db: DbDep):
    await host_service.delete_project(db, pid)
    return ok(message="已删除")


# ---------- 凭据 ----------
credentials_router = APIRouter(prefix="/credentials", tags=["credentials"])


@credentials_router.get("")
async def list_credentials(db: DbDep, _: CurrentUser):
    rows = await host_service.list_credentials(db)
    return ok(data=[CredentialOut.model_validate(c).model_dump() for c in rows])


@credentials_router.post("", dependencies=[Depends(require_perm("credential:create"))])
async def create_credential(req: CredentialCreate, db: DbDep, user: CurrentUser):
    c = await host_service.create_credential(db, req, created_by=user.username)
    return ok(data=CredentialOut.model_validate(c).model_dump())


@credentials_router.put("/{cid}", dependencies=[Depends(require_perm("credential:update"))])
async def update_credential(cid: int, req: CredentialUpdate, db: DbDep):
    c = await host_service.update_credential(db, cid, req)
    return ok(data=CredentialOut.model_validate(c).model_dump())


@credentials_router.delete("/{cid}", dependencies=[Depends(require_perm("credential:delete"))])
async def delete_credential(cid: int, db: DbDep):
    await host_service.delete_credential(db, cid)
    return ok(message="已删除")


# ---------- 主机组 ----------
groups_router = APIRouter(prefix="/host-groups", tags=["host-groups"])


@groups_router.get("")
async def list_groups(db: DbDep, _: CurrentUser):
    rows = await host_service.list_groups(db)
    return ok(data=[HostGroupOut(
        id=g.id, name=g.name, description=g.description or "", project_id=g.project_id,
        vars=g.vars, host_ids=[h.id for h in g.hosts], created_at=g.created_at,
    ).model_dump() for g in rows])


@groups_router.post("", dependencies=[Depends(require_perm("hostgroup:create"))])
async def create_group(req: HostGroupCreate, db: DbDep):
    g = await host_service.create_group(db, req)
    return ok(data={"id": g.id})


@groups_router.put("/{gid}", dependencies=[Depends(require_perm("hostgroup:update"))])
async def update_group(gid: int, req: HostGroupUpdate, db: DbDep):
    g = await host_service.update_group(db, gid, req)
    return ok(data={"id": g.id})


@groups_router.delete("/{gid}", dependencies=[Depends(require_perm("hostgroup:delete"))])
async def delete_group(gid: int, db: DbDep):
    await host_service.delete_group(db, gid)
    return ok(message="已删除")


# ---------- 主机 ----------
hosts_router = APIRouter(prefix="/hosts", tags=["hosts"])


@hosts_router.get("")
async def list_hosts(
    db: DbDep,
    _: CurrentUser,
    page: PageDep,
    host_type: str = Query(None, pattern="^(app|agent|managed)$"),
    project_id: int = Query(None),
    group_id: int = Query(None),
    keyword: str = Query(None),
):
    rows, total = await host_service.list_hosts(
        db, host_type=host_type, project_id=project_id, group_id=group_id,
        keyword=keyword, offset=page.offset, limit=page.page_size,
    )
    items = [HostOut(
        id=h.id, hostname=h.hostname, ip=h.ip, port=h.port, host_type=h.host_type,
        project_id=h.project_id, credential_id=h.credential_id, os_type=h.os_type,
        os_release=h.os_release, cpu_cores=h.cpu_cores, mem_total_mb=h.mem_total_mb,
        status=h.status, agent_status=h.agent_status, agent_version=h.agent_version,
        playbook_dir=h.playbook_dir,
        fail_count=h.fail_count, last_check_at=h.last_check_at,
        last_collect_at=h.last_collect_at, description=h.description or "", tags=h.tags,
        enabled=h.enabled, group_ids=[g.id for g in h.groups], created_at=h.created_at,
    ).model_dump() for h in rows]
    return paginated(items, total, page.page, page.page_size)


@hosts_router.post("", dependencies=[Depends(require_perm("host:create"))])
async def create_host(req: HostCreate, db: DbDep, user: CurrentUser, request: Request):
    h = await host_service.create_host(db, req)
    await host_service.add_audit(db, user_id=user.id, username=user.username, action="host.create",
                                 resource_type="host", resource_id=h.id, ip=request.client.host if request.client else "")
    return ok(data={"id": h.id})


# ---------- 主机导入导出（Excel） ----------
def _xlsx_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@hosts_router.get("/import-template")
async def download_import_template(_: CurrentUser):
    """下载导入模板（含示例行）。"""
    return _xlsx_response(host_io_service.build_template(), "host-import-template.xlsx")


@hosts_router.get("/export")
async def export_hosts(
    db: DbDep,
    _: CurrentUser,
    host_type: str = Query(None, pattern="^(app|agent|managed)$"),
):
    """导出当前 Agent 主机作用域下的主机（列与导入模板一致，可回灌）。"""
    content = await host_io_service.export_hosts(db, host_type=host_type)
    return _xlsx_response(content, "hosts.xlsx")


@hosts_router.post("/import", dependencies=[Depends(require_perm("host:create"))])
async def import_hosts(
    db: DbDep,
    user: CurrentUser,
    request: Request,
    file: UploadFile = File(...),
):
    """按 CSV 批量导入主机，返回成功数与失败明细。"""
    # 先取出审计字段：导入过程中逐行回滚会让 ORM 对象过期，之后再取会触发 async 上下文外的懒加载
    user_id, username = user.id, user.username
    result = await host_io_service.import_hosts(db, await file.read())
    await host_service.add_audit(
        db, user_id=user_id, username=username, action="host.import",
        resource_type="host", detail=result,
        ip=request.client.host if request.client else "",
    )
    return ok(data=HostImportResult(**result).model_dump())


@hosts_router.put("/{host_id}", dependencies=[Depends(require_perm("host:update"))])
async def update_host(host_id: int, req: HostUpdate, db: DbDep):
    h = await host_service.update_host(db, host_id, req)
    return ok(data={"id": h.id})


@hosts_router.delete("/{host_id}", dependencies=[Depends(require_perm("host:delete"))])
async def delete_host(host_id: int, db: DbDep):
    await host_service.delete_host(db, host_id)
    return ok(message="已删除")


@hosts_router.post("/{host_id}/check", dependencies=[Depends(require_perm("host:check"))])
async def check_host(host_id: int, db: DbDep, factory: TransportFactoryDep):
    host = await host_service.get_host(db, host_id)
    target = await resolve_target(host_id, db)
    transport = factory(target)
    try:
        result = await host_service.check_host(db, host, transport)
    finally:
        await transport.close()
    return ok(data=result)


@hosts_router.post("/check-connect")
async def check_connect(
    _: CurrentUser,
    ip: str,
    port: int = 22,
    username: str = "root",
    password: str = "",
):
    """建主机表单的「连接测试」：用临时凭据（不入库）真实 SSH 测连通。"""
    from app.services import auth_service

    try:
        info = await auth_service.test_ssh_connection(
            type("R", (), {"host": ip, "port": port, "username": username, "password": password})()
        )
    except AppError as e:
        # 保持原业务错误码与 http_status，仅转写成 JSON 响应
        raise AppError(e.message, code=e.code, http_status=e.http_status)
    except Exception as e:  # noqa: BLE001
        raise AppError(f"连接失败: {type(e).__name__}: {str(e)[:120]}", code=40100, http_status=401)
    return ok(data=info)


@hosts_router.post("/{host_id}/passwordless")
async def enable_passwordless(host_id: int, db: DbDep, factory: TransportFactoryDep):
    """SSH 免密：把控制端公钥追加到目标机 authorized_keys，实现免密登录。"""
    host = await host_service.get_host(db, host_id)
    target = await resolve_target(host_id, db)
    transport = factory(target)
    try:
        result = await host_service.install_public_key(db, host, transport)
    finally:
        await transport.close()
    return ok(data=result)


# ---------- Agent 主机生命周期 ----------
@hosts_router.post("/{host_id}/agent/install")
async def agent_install(host_id: int, db: DbDep, factory: TransportFactoryDep):
    """安装 Agent 程序（目标机创建 /opt/am-agent）。"""
    host = await host_service.get_host(db, host_id)
    target = await resolve_target(host_id, db)
    transport = factory(target)
    try:
        result = await host_service.install_agent(db, host, transport)
    finally:
        await transport.close()
    return ok(data=result)


@hosts_router.post("/{host_id}/agent/uninstall")
async def agent_uninstall(host_id: int, db: DbDep, factory: TransportFactoryDep):
    """卸载 Agent 程序（删除目标机 /opt/am-agent）。"""
    host = await host_service.get_host(db, host_id)
    target = await resolve_target(host_id, db)
    transport = factory(target)
    try:
        result = await host_service.uninstall_agent(db, host, transport)
    finally:
        await transport.close()
    return ok(data=result)


@hosts_router.post("/{host_id}/agent/update")
async def agent_update(host_id: int, db: DbDep, factory: TransportFactoryDep):
    """更新 Agent 程序（远程升级到最新版本）。"""
    host = await host_service.get_host(db, host_id)
    target = await resolve_target(host_id, db)
    transport = factory(target)
    try:
        result = await host_service.update_agent(db, host, transport)
    finally:
        await transport.close()
    return ok(data=result)
