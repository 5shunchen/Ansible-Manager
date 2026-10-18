"""schemas 汇总导出。"""
from app.schemas.system import (  # noqa: F401
    AuditLogOut, LoginRequest, MenuCreate, MenuOut, MenuTree, RoleCreate, RoleOut, RoleUpdate,
    SystemConfigOut, SystemConfigUpdate, TokenOut, UserCreate, UserOut, UserUpdate,
)
from app.schemas.host import (  # noqa: F401
    CredentialCreate, CredentialOut, CredentialUpdate, HostCreate, HostGroupCreate, HostGroupOut,
    HostOut, HostUpdate, ProjectCreate, ProjectOut, ProjectUpdate,
)
from app.schemas.task import (  # noqa: F401
    PlaybookCreate, PlaybookOut, TaskCreate, TaskEventOut, TaskOut, TaskTargetOut,
)
from app.schemas.deployment import (  # noqa: F401
    DeployActionRequest, DeployProjectCreate, DeployProjectOut, DeployProjectUpdate,
    DeployRecordOut, PluginCreate, PluginOut, PluginUpdate,
)
