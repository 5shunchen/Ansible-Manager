"""认证路由。"""
from fastapi import APIRouter

from app.api.deps import CurrentUser, DbDep
from app.core.exceptions import AuthError
from app.core.response import ok
from app.schemas.system import LoginRequest, SshLoginRequest
from app.services import auth_service, system_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(req: LoginRequest, db: DbDep):
    result = await auth_service.authenticate(db, req)
    return ok(data={"token": result.token, "user": result.user.model_dump()})


@router.post("/ssh-login")
async def ssh_login(req: SshLoginRequest, db: DbDep):
    """主机 root 密码登录：先真实 SSH 测连通，通过即签发平台 token（密码即主机密码）。"""
    result = await auth_service.ssh_login(db, req)
    return ok(data={"token": result.token, "user": result.user.model_dump()})


@router.post("/ssh-test")
async def ssh_test(req: SshLoginRequest):
    """仅测试 SSH 连通性（登录页「连接测试」按钮），不签发 token。"""
    info = await auth_service.test_ssh_connection(req)
    return ok(data=info)


@router.post("/logout")
async def logout(_: CurrentUser):
    return ok(message="已退出登录")


@router.get("/me")
async def me(user: CurrentUser, db: DbDep):
    """前端动态菜单/权限的入口：user + menus 树 + permission 编码集合。"""
    user_out = await auth_service.to_user_out(user)
    menus = await auth_service.get_user_menus(db, user)
    tree = system_service.build_menu_tree(menus)
    perms = await auth_service.get_user_perm_codes(db, user)
    return ok(data={
        "user": user_out.model_dump(),
        "menus": [t.model_dump() for t in tree],
        "permissions": sorted(perms),
        # 系统最新 Agent 版本：前端据此判断是否显示「更新」按钮
        "latest_agent_version": _latest_agent_version(),
    })


def _latest_agent_version() -> str:
    from app.services.host_service import LATEST_AGENT_VERSION

    return LATEST_AGENT_VERSION
