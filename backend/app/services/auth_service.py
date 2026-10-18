"""认证与用户服务。"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.core.security import create_access_token, verify_password
from app.models.system import SysMenu, SysUser, SysRole
from app.schemas.system import LoginRequest, SshLoginRequest, TokenOut, UserOut


async def authenticate(db: AsyncSession, req: LoginRequest) -> TokenOut:
    user = (await db.execute(select(SysUser).where(SysUser.username == req.username))).scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise AuthError("用户名或密码错误")
    if not user.is_active:
        raise AuthError("账号已被禁用")
    user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()

    token = create_access_token(str(user.id))
    user_out = await to_user_out(user)
    return TokenOut(token=token, user=user_out)


async def test_ssh_connection(req: SshLoginRequest) -> dict:
    """真实 SSH 测连通：asyncssh 连接 + 执行 uname，返回系统信息。失败抛 AuthError。"""
    import asyncssh

    try:
        async with asyncssh.connect(
            req.host, port=req.port, username=req.username,
            password=req.password, known_hosts=None, connect_timeout=8,
        ) as conn:
            r = await conn.run("uname -s; uname -r; nproc 2>/dev/null || echo 0", timeout=10)
            lines = [x.strip() for x in (r.stdout or "").splitlines() if x.strip()]
            return {
                "reachable": True,
                "os": lines[0] if lines else "",
                "os_release": lines[1] if len(lines) > 1 else "",
                "cpu_cores": int(lines[2]) if len(lines) > 2 and lines[2].isdigit() else None,
            }
    except Exception as e:  # noqa: BLE001
        raise AuthError(f"连接失败: {type(e).__name__}: {str(e)[:120]}")


async def ssh_login(db: AsyncSession, req: SshLoginRequest) -> TokenOut:
    """主机密码登录：先测 SSH 连通（失败即拒绝），通过后给内置 admin 签发平台 token。

    设计：密码即目标主机密码，一次输入完成「连通测试 + 平台登录」；平台权限沿用内置管理员。
    """
    await test_ssh_connection(req)  # 测不过直接抛 AuthError
    admin = (await db.execute(select(SysUser).where(SysUser.is_superuser.is_(True)))).scalar_one_or_none()
    if not admin:
        raise AuthError("平台管理员不存在，请先完成初始化")
    admin.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()

    token = create_access_token(str(admin.id))
    user_out = await to_user_out(admin)
    return TokenOut(token=token, user=user_out)


async def get_user(db: AsyncSession, user_id: int) -> SysUser:
    user = await db.get(SysUser, user_id)
    if not user or not user.is_active:
        raise AuthError("用户不存在或已禁用")
    return user


async def to_user_out(user: SysUser) -> UserOut:
    roles = [r.name for r in user.roles]
    return UserOut(
        id=user.id,
        username=user.username,
        nickname=user.nickname or "",
        email=user.email or None,
        phone=user.phone or "",
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        role_ids=[r.id for r in user.roles],
        roles=roles,
    )


async def get_user_perm_codes(db: AsyncSession, user: SysUser) -> set[str]:
    """用户全部权限编码（角色→菜单 button.permission）。"""
    if user.is_superuser:
        menus = (await db.execute(select(SysMenu))).scalars().all()
        return {m.permission for m in menus if m.permission}
    perms: set[str] = set()
    for role in user.roles:
        if not role.enabled:
            continue
        for menu in role.menus:
            if menu.permission:
                perms.add(menu.permission)
    return perms


async def get_user_menus(db: AsyncSession, user: SysUser) -> list[SysMenu]:
    """用户可见的菜单（dir/menu，不含 button）。超管返回全部。"""
    stmt = select(SysMenu).where(SysMenu.menu_type != "button").order_by(SysMenu.sort)
    if user.is_superuser:
        return list((await db.execute(stmt)).scalars().all())
    menus: dict[int, SysMenu] = {}
    for role in user.roles:
        if role.enabled:
            for m in role.menus:
                if m.menu_type != "button":
                    menus[m.id] = m
    return sorted(menus.values(), key=lambda m: m.sort)
