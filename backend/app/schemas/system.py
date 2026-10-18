"""系统域 schemas：用户/角色/菜单/配置/审计。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------- Auth ----------
class LoginRequest(BaseModel):
    username: str
    password: str


class SshLoginRequest(BaseModel):
    """主机 root 密码登录：目标主机 IP + root 密码，先 SSH 测连通再签发平台 token。"""
    host: str = Field(max_length=64)
    port: int = 22
    username: str = "root"
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    token: str
    user: "UserOut"


# ---------- User ----------
class UserBase(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    nickname: str = ""
    email: Optional[EmailStr] = None
    phone: str = ""
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=6, max_length=64)
    role_ids: list[int] = []


class UserUpdate(BaseModel):
    nickname: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6, max_length=64)
    role_ids: Optional[list[int]] = None


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_superuser: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    role_ids: list[int] = []
    roles: list[str] = []


# ---------- Role ----------
class RoleCreate(BaseModel):
    name: str
    code: str
    description: str = ""
    menu_ids: list[int] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    menu_ids: Optional[list[int]] = None
    enabled: Optional[bool] = None


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: str
    enabled: bool
    menu_ids: list[int] = []
    created_at: datetime


# ---------- Menu ----------
class MenuCreate(BaseModel):
    parent_id: Optional[int] = None
    name: str
    path: str = ""
    component: str = ""
    icon: str = ""
    sort: int = 0
    menu_type: str = "menu"  # dir/menu/button
    permission: Optional[str] = None
    visible: bool = True


class MenuUpdate(BaseModel):
    parent_id: Optional[int] = None
    name: Optional[str] = None
    path: Optional[str] = None
    component: Optional[str] = None
    icon: Optional[str] = None
    sort: Optional[int] = None
    menu_type: Optional[str] = None
    permission: Optional[str] = None
    visible: Optional[bool] = None


class MenuOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: Optional[int]
    name: str
    path: str
    component: str
    icon: str
    sort: int
    menu_type: str
    permission: Optional[str]
    visible: bool


class MenuTree(MenuOut):
    children: list["MenuTree"] = []


# ---------- SystemConfig ----------
class SystemConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: object
    description: str


class SystemConfigUpdate(BaseModel):
    configs: dict[str, object]


# ---------- Audit ----------
class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    action: str
    resource_type: str
    resource_id: str
    detail: Optional[dict]
    ip: str
    success: bool
    created_at: datetime


TokenOut.model_rebuild()
