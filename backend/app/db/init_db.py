"""首次启动 seed：admin 用户 + 全量菜单树（11 个菜单含子菜单+按钮权限）+ 默认系统配置。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.system import SysConfig, SysMenu, SysRole, SysUser, role_menu

logger = get_logger(__name__)

# (name, path, component, icon, sort, permission, menu_type)
# path/component 为空表示按钮
MENUS: list[dict] = [
    {"name": "项目管理", "path": "/project", "component": "project/index", "icon": "Folder", "sort": 1},
    {"name": "应用主机", "path": "/apphost", "component": "apphost/index", "icon": "Monitor", "sort": 2},
    {"name": "Agent主机", "path": "/agenthost", "component": "agenthost/index", "icon": "Cpu", "sort": 3},
    {"name": "主机管理", "path": "/host", "icon": "Platform", "sort": 4},
    {"name": "监控大屏", "path": "/monitor/dashboard", "component": "monitor/dashboard/index", "icon": "DataLine", "sort": 5},
    {"name": "Playbook管理", "path": "/playbook", "component": "playbook/index", "icon": "Document", "sort": 6},
    {"name": "任务管理", "path": "/task", "component": "task/index", "icon": "List", "sort": 7},
    {"name": "系统配置", "path": "/system/config", "component": "system/config/index", "icon": "Setting", "sort": 8},
    {"name": "权限管理", "path": "/permission", "component": "permission/user", "icon": "Lock", "sort": 9},
    {"name": "插件工程", "path": "/plugin", "component": "plugin/index", "icon": "Coin", "sort": 10},
    {"name": "工程部署", "path": "/deployment/project", "component": "deployment/project/index", "icon": "Box", "sort": 11},
]

HOST_SUBMENUS = [
    {"name": "主机列表", "path": "/host/list", "component": "host/list/index", "sort": 1},
    {"name": "Web终端", "path": "/host/terminal", "component": "host/terminal/index", "sort": 2},
    {"name": "文件管理", "path": "/host/files", "component": "host/files/index", "sort": 3},
]

# 每个页面菜单下的按钮权限
BUTTONS: dict[str, list[tuple[str, str]]] = {
    "项目管理": [("新增项目", "project:create"), ("编辑项目", "project:update"), ("删除项目", "project:delete")],
    "应用主机": [("新增主机", "host:create"), ("编辑主机", "host:update"), ("删除主机", "host:delete"),
                ("安装App", "app:install"), ("卸载App", "app:uninstall")],
    "主机列表": [
        ("新增主机", "host:create"), ("编辑主机", "host:update"), ("删除主机", "host:delete"), ("连通检测", "host:check"),
        ("主机组新增", "hostgroup:create"), ("主机组编辑", "hostgroup:update"), ("主机组删除", "hostgroup:delete"),
        ("凭据新增", "credential:create"), ("凭据编辑", "credential:update"), ("凭据删除", "credential:delete"),
    ],
    "Web终端": [("打开终端", "terminal:open")],
    "文件管理": [("文件浏览", "file:read"), ("文件上传", "file:write"), ("文件删除", "file:delete")],
    "Playbook管理": [("新增Playbook", "playbook:create"), ("编辑Playbook", "playbook:update"), ("删除Playbook", "playbook:delete"), ("执行Playbook", "task:execute")],
    "任务管理": [("新建任务", "task:execute"), ("取消任务", "task:cancel"), ("删除任务", "task:delete")],
    "权限管理": [
        ("新增用户", "user:create"), ("编辑用户", "user:update"), ("删除用户", "user:delete"),
        ("新增角色", "role:create"), ("编辑角色", "role:update"), ("删除角色", "role:delete"),
        ("新增菜单", "menu:create"), ("编辑菜单", "menu:update"), ("删除菜单", "menu:delete"),
    ],
    "工程部署": [
        ("新增部署工程", "deploy:create"), ("编辑部署工程", "deploy:update"), ("删除部署工程", "deploy:delete"),
        ("执行部署", "deploy:run"), ("执行回滚", "deploy:rollback"),
    ],
    "插件工程": [("新增插件", "plugin:create"), ("安装插件", "plugin:install"), ("删除插件", "plugin:delete")],
    "系统配置": [("保存配置", "system:config")],
}


async def init_db(db: AsyncSession) -> None:
    # 菜单
    existing = (await db.execute(select(SysMenu))).scalars().all()
    if not existing:
        logger.info("seeding_menus")
        host_dir = None
        for m in MENUS:
            menu = SysMenu(
                name=m["name"], path=m.get("path", ""), component=m.get("component", ""),
                icon=m.get("icon", ""), sort=m["sort"], menu_type="dir" if m["name"] == "主机管理" else "menu",
            )
            db.add(menu)
            await db.flush()
            if m["name"] == "主机管理":
                host_dir = menu
            for (btn_name, perm) in BUTTONS.get(m["name"], []):
                db.add(SysMenu(parent_id=menu.id, name=btn_name, menu_type="button", permission=perm, sort=0))
        for s in HOST_SUBMENUS:
            sub = SysMenu(parent_id=host_dir.id, name=s["name"], path=s["path"], component=s["component"], sort=s["sort"], menu_type="menu")
            db.add(sub)
            await db.flush()
            for (btn_name, perm) in BUTTONS.get(s["name"], []):
                db.add(SysMenu(parent_id=sub.id, name=btn_name, menu_type="button", permission=perm, sort=0))
        await db.flush()

    # admin 用户 + 超管角色
    admin = (await db.execute(select(SysUser).where(SysUser.username == "admin"))).scalar_one_or_none()
    if not admin:
        logger.info("seeding_admin")
        admin = SysUser(
            username="admin", password_hash=hash_password("admin123"),
            nickname="管理员", is_superuser=True, is_active=True,
        )
        db.add(admin)
        await db.flush()

    # 只读演示角色
    viewer = (await db.execute(select(SysRole).where(SysRole.code == "viewer"))).scalar_one_or_none()
    if not viewer:
        logger.info("seeding_viewer_role")
        viewer = SysRole(name="只读用户", code="viewer", description="仅查看，无操作权限")
        db.add(viewer)
        await db.flush()
        read_menus = (await db.execute(
            select(SysMenu).where(SysMenu.menu_type != "button")
        )).scalars().all()
        for m in read_menus:
            await db.execute(role_menu.insert().values(role_id=viewer.id, menu_id=m.id))

    # 默认系统配置
    from app.services.config_service import DEFAULTS

    for key, value in DEFAULTS.items():
        cfg = (await db.execute(select(SysConfig).where(SysConfig.key == key))).scalar_one_or_none()
        if not cfg:
            db.add(SysConfig(key=key, value=value, description="", updated_by="system"))

    # 自带示例插件：平台自身的 app 与 agent 服务，作为 role 放在 data/plugins/roles/
    # 这些 role 的真实部署逻辑后续迭代填充；MVP 阶段 role 只含 debug 任务以打通链路。
    from app.models.deployment import Plugin

    for name, source, desc in [
        ("am-app", "am_app", "Ansible Manager 自身后端服务（app）"),
        ("am-agent", "am_agent", "Ansible Manager Agent 子服务"),
    ]:
        existing_plugin = (await db.execute(select(Plugin).where(Plugin.name == name))).scalar_one_or_none()
        if not existing_plugin:
            db.add(Plugin(
                name=name, plugin_type="role", source=source, version="0.1.0",
                description=desc, install_status="installed",
                installed_path="", config={}, created_by="system",
            ))

    await db.commit()
    logger.info("init_db_done")
