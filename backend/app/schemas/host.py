"""主机域 schemas：项目/凭据/主机/主机组。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- Project ----------
class ProjectCreate(BaseModel):
    name: str = Field(max_length=64)
    code: str = Field(max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    description: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None  # active/archived


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: str
    status: str
    created_at: datetime


# ---------- Credential ----------
class CredentialCreate(BaseModel):
    name: str = Field(max_length=64)
    auth_type: str = Field(pattern="^(password|private_key)$")
    username: str = Field(max_length=64)
    password: Optional[str] = None
    private_key: Optional[str] = None
    passphrase: Optional[str] = None
    default_port: int = 22


class CredentialUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    private_key: Optional[str] = None
    passphrase: Optional[str] = None
    default_port: Optional[int] = None


class CredentialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    auth_type: str
    username: str
    default_port: int
    created_at: datetime


# ---------- Host ----------
class HostCreate(BaseModel):
    hostname: str = Field(max_length=128)
    ip: str = Field(max_length=64)
    port: int = 22
    host_type: str = Field(default="managed", pattern="^(app|agent|managed)$")
    project_id: Optional[int] = None
    credential_id: Optional[int] = None
    # 直接输主机密码（免选凭据）：后端自动建/更新对应密码凭据并挂载
    ssh_username: str = "root"
    ssh_password: Optional[str] = None
    description: str = ""
    tags: Optional[dict] = None
    group_ids: list[int] = []
    # Agent 主机专属 playbook 存放目录（仅 host_type=agent 有意义）
    playbook_dir: Optional[str] = "/opt/ansible"


class HostUpdate(BaseModel):
    hostname: Optional[str] = None
    ip: Optional[str] = None
    port: Optional[int] = None
    host_type: Optional[str] = None
    project_id: Optional[int] = None
    credential_id: Optional[int] = None
    ssh_password: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[dict] = None
    playbook_dir: Optional[str] = None
    enabled: Optional[bool] = None
    group_ids: Optional[list[int]] = None


class HostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hostname: str
    ip: str
    port: int
    host_type: str
    project_id: Optional[int]
    credential_id: int
    os_type: Optional[str]
    os_release: Optional[str]
    cpu_cores: Optional[int]
    mem_total_mb: Optional[int]
    status: str
    agent_status: str = "not_installed"
    agent_version: Optional[str] = None
    playbook_dir: Optional[str] = None
    fail_count: int
    last_check_at: Optional[datetime]
    last_collect_at: Optional[datetime]
    description: str
    tags: Optional[dict]
    enabled: bool
    group_ids: list[int] = []
    created_at: datetime


class HostCheckResult(BaseModel):
    host_id: int
    reachable: bool
    message: str = ""
    os_type: Optional[str] = None
    os_release: Optional[str] = None
    cpu_cores: Optional[int] = None
    mem_total_mb: Optional[int] = None


# ---------- 主机导入 ----------
class HostImportError(BaseModel):
    line: int
    hostname: str = ""
    message: str


class HostImportResult(BaseModel):
    total: int
    success: int
    failed: int
    errors: list[HostImportError] = []


# ---------- HostGroup ----------
class HostGroupCreate(BaseModel):
    name: str = Field(max_length=64)
    description: str = ""
    project_id: Optional[int] = None
    vars: Optional[dict] = None
    host_ids: list[int] = []


class HostGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    project_id: Optional[int] = None
    vars: Optional[dict] = None
    host_ids: Optional[list[int]] = None


class HostGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    project_id: Optional[int]
    vars: Optional[dict]
    host_ids: list[int] = []
    created_at: datetime
