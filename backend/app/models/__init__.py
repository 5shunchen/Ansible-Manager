"""models 汇总导出，供 alembic 与 init_db 引用（保证所有表注册到 metadata）。"""
from app.db.base import Base
from app.models.system import (  # noqa: F401
    SysAuditLog, SysConfig, SysMenu, SysRole, SysUser, role_menu, user_role,
)
from app.models.host import Host, HostGroup, HostGroupMember, Project, SshCredential  # noqa: F401
from app.models.metric import MetricCollectLog, MetricDisk, MetricHost  # noqa: F401
from app.models.task import Playbook, Task, TaskEvent, TaskTarget  # noqa: F401
from app.models.deployment import (  # noqa: F401
    DeployContainer, DeployProject, DeployProjectHost, DeployRecord, Plugin,
)

__all__ = ["Base"]
