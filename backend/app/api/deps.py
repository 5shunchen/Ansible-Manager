"""DI 汇总点：DB session / 当前用户 / 权限校验 / transport 工厂 / task executor。

分层组装唯一入口；tests 用 app.dependency_overrides 替换 get_transport_factory/get_task_executor。
"""
from typing import Annotated, Optional

from fastapi import Depends, Query, Request, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.core.pagination import PageParams
from app.core.scope import set_scope
from app.db.session import get_session
from app.models.system import SysUser
from app.runner.interfaces import SshTarget, TaskExecutor, TransportFactory
from app.runner.ssh.asyncssh_transport import transport_factory as default_transport_factory
from app.services.auth_service import get_user, get_user_perm_codes


async def get_db() -> AsyncSession:
    async for s in get_session():
        yield s


DbDep = Annotated[AsyncSession, Depends(get_db)]


def _extract_token(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization", "") or request.query_params.get("token", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return auth or None


def _header_scope(request: Request) -> Optional[int]:
    """当前 Agent 主机：顶部筛选框所在前端通过请求头携带。"""
    raw = request.headers.get("x-agent-host-id", "")
    return int(raw) if raw.isdigit() else None


async def get_current_user(
    db: DbDep, request: Request, token: Optional[str] = Depends(_extract_token)
) -> SysUser:
    # 全局作用域：本请求后续所有业务查询按该 Agent 主机收窄
    set_scope(_header_scope(request))
    if not token:
        raise AuthError("未登录")
    from app.core.security import decode_token

    payload = decode_token(token)
    sub = payload.get("sub")
    if not sub:
        raise AuthError("无效的登录凭证")
    return await get_user(db, int(sub))


CurrentUser = Annotated[SysUser, Depends(get_current_user)]


async def get_current_user_ws(db: DbDep, ws: WebSocket) -> SysUser:
    """WS 场景：token 从 query 参数取。"""
    return await get_current_user(ws, db)


def require_perm(*perms: str):
    """按钮/接口级权限：全部 perms 都在用户权限集合内才放行；超管直通。"""

    async def dep(user: CurrentUser, db: DbDep) -> SysUser:
        if user.is_superuser:
            return user
        user_perms = await get_user_perm_codes(db, user)
        if not set(perms) <= user_perms:
            from app.core.exceptions import PermError

            raise PermError(f"缺少权限: {','.join(perms)}")
        return user

    return dep


def get_transport_factory() -> TransportFactory:
    return default_transport_factory


TransportFactoryDep = Annotated[TransportFactory, Depends(get_transport_factory)]


async def resolve_target(host_id: int, db: DbDep) -> SshTarget:
    """路径参数 host_id → SshTarget（供连通检测/终端/文件/采集使用）。"""
    from app.services.host_service import build_ssh_target, get_host

    host = await get_host(db, host_id)
    return await build_ssh_target(db, host)


TargetDep = Annotated[SshTarget, Depends(resolve_target)]


def get_page_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PageParams:
    return PageParams(page=page, page_size=page_size).clamp()


PageDep = Annotated[PageParams, Depends(get_page_params)]


def get_task_executor() -> TaskExecutor:
    from app.runner.ansible_executor import AnsibleExecutor

    return AnsibleExecutor()


ExecutorDep = Annotated[TaskExecutor, Depends(get_task_executor)]
