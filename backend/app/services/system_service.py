"""用户/角色/菜单管理服务。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.system import SysMenu, SysRole, SysUser, role_menu, user_role
from app.schemas.system import MenuCreate, MenuTree, MenuUpdate, RoleCreate, RoleUpdate, UserCreate, UserUpdate
from app.core.security import hash_password


# ---------- User ----------
async def list_users(db: AsyncSession) -> list[SysUser]:
    return list((await db.execute(select(SysUser).order_by(SysUser.id))).scalars().all())


async def create_user(db: AsyncSession, req: UserCreate) -> SysUser:
    exists = (await db.execute(select(SysUser).where(SysUser.username == req.username))).scalar_one_or_none()
    if exists:
        raise ConflictError(f"用户名已存在: {req.username}")
    user = SysUser(
        username=req.username,
        password_hash=hash_password(req.password),
        nickname=req.nickname,
        email=req.email,
        phone=req.phone,
        is_active=req.is_active,
    )
    db.add(user)
    await db.flush()
    await _set_user_roles(db, user, req.role_ids)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user_id: int, req: UserUpdate) -> SysUser:
    user = await db.get(SysUser, user_id)
    if not user:
        raise NotFoundError("用户不存在")
    for f in ("nickname", "email", "phone", "is_active"):
        v = getattr(req, f)
        if v is not None:
            setattr(user, f, v)
    if req.password:
        user.password_hash = hash_password(req.password)
    if req.role_ids is not None:
        await _set_user_roles(db, user, req.role_ids)
    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: int) -> None:
    user = await db.get(SysUser, user_id)
    if not user:
        raise NotFoundError("用户不存在")
    if user.is_superuser:
        raise ConflictError("内置管理员不可删除")
    await db.delete(user)
    await db.commit()


async def _set_user_roles(db: AsyncSession, user: SysUser, role_ids: list[int]) -> None:
    await db.execute(user_role.delete().where(user_role.c.user_id == user.id))
    if role_ids:
        await db.execute(user_role.insert().values([
            {"user_id": user.id, "role_id": rid} for rid in role_ids
        ]))


# ---------- Role ----------
async def list_roles(db: AsyncSession) -> list[SysRole]:
    return list((await db.execute(select(SysRole).order_by(SysRole.id))).scalars().all())


async def create_role(db: AsyncSession, req: RoleCreate) -> SysRole:
    exists = (await db.execute(select(SysRole).where(SysRole.code == req.code))).scalar_one_or_none()
    if exists:
        raise ConflictError(f"角色编码已存在: {req.code}")
    role = SysRole(name=req.name, code=req.code, description=req.description)
    db.add(role)
    await db.flush()
    await _set_role_menus(db, role, req.menu_ids)
    await db.commit()
    await db.refresh(role)
    return role


async def update_role(db: AsyncSession, role_id: int, req: RoleUpdate) -> SysRole:
    role = await db.get(SysRole, role_id)
    if not role:
        raise NotFoundError("角色不存在")
    if req.name is not None:
        role.name = req.name
    if req.description is not None:
        role.description = req.description
    if req.enabled is not None:
        role.enabled = req.enabled
    if req.menu_ids is not None:
        await _set_role_menus(db, role, req.menu_ids)
    await db.commit()
    await db.refresh(role)
    return role


async def delete_role(db: AsyncSession, role_id: int) -> None:
    role = await db.get(SysRole, role_id)
    if not role:
        raise NotFoundError("角色不存在")
    await db.delete(role)
    await db.commit()


async def _set_role_menus(db: AsyncSession, role: SysRole, menu_ids: list[int]) -> None:
    await db.execute(role_menu.delete().where(role_menu.c.role_id == role.id))
    if menu_ids:
        await db.execute(role_menu.insert().values([
            {"role_id": role.id, "menu_id": mid} for mid in menu_ids
        ]))


# ---------- Menu ----------
async def list_menus(db: AsyncSession) -> list[SysMenu]:
    return list((await db.execute(select(SysMenu).order_by(SysMenu.sort, SysMenu.id))).scalars().all())


async def create_menu(db: AsyncSession, req: MenuCreate) -> SysMenu:
    menu = SysMenu(**req.model_dump())
    db.add(menu)
    await db.commit()
    await db.refresh(menu)
    return menu


async def update_menu(db: AsyncSession, menu_id: int, req: MenuUpdate) -> SysMenu:
    menu = await db.get(SysMenu, menu_id)
    if not menu:
        raise NotFoundError("菜单不存在")
    for f, v in req.model_dump(exclude_unset=True).items():
        setattr(menu, f, v)
    await db.commit()
    await db.refresh(menu)
    return menu


async def delete_menu(db: AsyncSession, menu_id: int) -> None:
    menu = await db.get(SysMenu, menu_id)
    if not menu:
        raise NotFoundError("菜单不存在")
    await db.delete(menu)
    await db.commit()


def build_menu_tree(menus: list[SysMenu]) -> list[MenuTree]:
    """平铺菜单 → 树。"""
    nodes = {m.id: MenuTree(
        id=m.id, parent_id=m.parent_id, name=m.name, path=m.path or "", component=m.component or "",
        icon=m.icon or "", sort=m.sort, menu_type=m.menu_type, permission=m.permission,
        visible=m.visible, children=[],
    ) for m in menus}
    roots: list[MenuTree] = []
    for node in nodes.values():
        if node.parent_id and node.parent_id in nodes:
            nodes[node.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots
