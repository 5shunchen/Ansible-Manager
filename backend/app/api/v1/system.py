"""系统管理路由：用户/角色/菜单/审计/系统配置。"""
from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbDep, PageDep, require_perm
from app.core.response import ok, paginated
from app.models.system import SysAuditLog, SysConfig
from app.schemas.system import (
    AuditLogOut, MenuCreate, MenuOut, MenuUpdate, RoleCreate, RoleOut, RoleUpdate,
    SystemConfigUpdate, UserCreate, UserOut, UserUpdate,
)
from app.services import auth_service, system_service
from app.core.config import settings

router = APIRouter(tags=["system"])


# ---------- 用户 ----------
users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.get("")
async def list_users(db: DbDep, _: CurrentUser, page: PageDep):
    """用户量小，内存分页即可。"""
    rows = await system_service.list_users(db)
    items = [(await auth_service.to_user_out(u)).model_dump() for u in rows[page.offset: page.offset + page.page_size]]
    return paginated(items, len(rows), page.page, page.page_size)


@users_router.post("", dependencies=[Depends(require_perm("user:create"))])
async def create_user(req: UserCreate, db: DbDep):
    user = await system_service.create_user(db, req)
    return ok(data=(await auth_service.to_user_out(user)).model_dump())


@users_router.put("/{user_id}", dependencies=[Depends(require_perm("user:update"))])
async def update_user(user_id: int, req: UserUpdate, db: DbDep):
    user = await system_service.update_user(db, user_id, req)
    return ok(data=(await auth_service.to_user_out(user)).model_dump())


@users_router.delete("/{user_id}", dependencies=[Depends(require_perm("user:delete"))])
async def delete_user(user_id: int, db: DbDep):
    await system_service.delete_user(db, user_id)
    return ok(message="已删除")


# ---------- 角色 ----------
roles_router = APIRouter(prefix="/roles", tags=["roles"])


@roles_router.get("")
async def list_roles(db: DbDep, _: CurrentUser):
    roles = await system_service.list_roles(db)
    return ok(data=[RoleOut(
        id=r.id, name=r.name, code=r.code, description=r.description or "", enabled=r.enabled,
        menu_ids=[m.id for m in r.menus], created_at=r.created_at,
    ).model_dump() for r in roles])


@roles_router.post("", dependencies=[Depends(require_perm("role:create"))])
async def create_role(req: RoleCreate, db: DbDep):
    role = await system_service.create_role(db, req)
    return ok(data={"id": role.id})


@roles_router.put("/{role_id}", dependencies=[Depends(require_perm("role:update"))])
async def update_role(role_id: int, req: RoleUpdate, db: DbDep):
    await system_service.update_role(db, role_id, req)
    return ok(message="已更新")


@roles_router.delete("/{role_id}", dependencies=[Depends(require_perm("role:delete"))])
async def delete_role(role_id: int, db: DbDep):
    await system_service.delete_role(db, role_id)
    return ok(message="已删除")


# ---------- 菜单 ----------
menus_router = APIRouter(prefix="/menus", tags=["menus"])


@menus_router.get("")
async def list_menus(db: DbDep, _: CurrentUser):
    menus = await system_service.list_menus(db)
    return ok(data=[MenuOut.model_validate(m).model_dump() for m in menus])


@menus_router.get("/tree")
async def menu_tree(db: DbDep, _: CurrentUser):
    menus = await system_service.list_menus(db)
    return ok(data=[t.model_dump() for t in system_service.build_menu_tree(menus)])


@menus_router.post("", dependencies=[Depends(require_perm("menu:create"))])
async def create_menu(req: MenuCreate, db: DbDep):
    menu = await system_service.create_menu(db, req)
    return ok(data=MenuOut.model_validate(menu).model_dump())


@menus_router.put("/{menu_id}", dependencies=[Depends(require_perm("menu:update"))])
async def update_menu(menu_id: int, req: MenuUpdate, db: DbDep):
    menu = await system_service.update_menu(db, menu_id, req)
    return ok(data=MenuOut.model_validate(menu).model_dump())


@menus_router.delete("/{menu_id}", dependencies=[Depends(require_perm("menu:delete"))])
async def delete_menu(menu_id: int, db: DbDep):
    await system_service.delete_menu(db, menu_id)
    return ok(message="已删除")


# ---------- 审计 ----------
audit_router = APIRouter(prefix="/audit-logs", tags=["audit"])


@audit_router.get("", dependencies=[Depends(require_perm("audit:read"))])
async def list_audit_logs(db: DbDep, page: PageDep, username: str = Query(None)):
    from sqlalchemy import func, select

    stmt = select(SysAuditLog).order_by(SysAuditLog.id.desc())
    if username:
        stmt = stmt.where(SysAuditLog.username == username)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    rows = (await db.execute(stmt.offset(page.offset).limit(page.page_size))).scalars().all()
    return paginated([AuditLogOut.model_validate(r).model_dump() for r in rows], total, page.page, page.page_size)


# ---------- 系统配置 ----------
config_router = APIRouter(prefix="/system-configs", tags=["system-config"])


@config_router.get("")
async def list_configs(db: DbDep, _: CurrentUser):
    from sqlalchemy import select

    rows = (await db.execute(select(SysConfig).order_by(SysConfig.key))).scalars().all()
    return ok(data=[{"key": c.key, "value": c.value, "description": c.description or ""} for c in rows])


@config_router.put("", dependencies=[Depends(require_perm("system:config"))])
async def update_configs(req: SystemConfigUpdate, db: DbDep, user: CurrentUser):
    from sqlalchemy import select
    from datetime import datetime, timezone

    for key, value in req.configs.items():
        cfg = (await db.execute(select(SysConfig).where(SysConfig.key == key))).scalar_one_or_none()
        if cfg:
            cfg.value = value
            cfg.updated_by = user.username
        else:
            db.add(SysConfig(key=key, value=value, updated_by=user.username,
                             created_at=datetime.now(timezone.utc).replace(tzinfo=None)))
    await db.commit()
    from app.services.config_service import invalidate_cache

    invalidate_cache()
    return ok(message="已保存")
