"""部署域 schemas：插件/部署工程/记录。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- Plugin ----------
class PluginCreate(BaseModel):
    name: str = Field(max_length=128)
    plugin_type: str = Field(default="collection", pattern="^(collection|role)$")
    source: str = Field(max_length=255)  # galaxy 名或 git URL
    version: str = ""
    description: str = ""


class PluginUpdate(BaseModel):
    version: Optional[str] = None
    description: Optional[str] = None
    config: Optional[dict] = None


class PluginOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    plugin_type: str
    source: str
    version: str
    description: str
    install_status: str
    install_log: Optional[str]
    installed_path: Optional[str]
    config: Optional[dict] = None
    created_at: datetime


# ---------- DeployProject ----------
class DeployHostItem(BaseModel):
    host_id: int
    container_name: str = ""
    enabled: bool = True


class DeployProjectCreate(BaseModel):
    name: str = Field(max_length=128)
    code: str = Field(max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    project_id: Optional[int] = None
    registry_url: str = ""
    image_repo: str = Field(max_length=255)
    default_tag: str = "latest"
    # 镜像来源：空 = registry 拉取；docker = 构建主机 Docker 服务构建
    build_type: str = Field(default="", pattern="^(|docker)$")
    build_host_id: Optional[int] = None
    build_context: str = ""
    dockerfile: str = "Dockerfile"
    build_args: Optional[dict] = None
    runtime: str = Field(default="nerdctl", pattern="^(nerdctl|ctr)$")
    namespace: str = "k8s.io"
    env: Optional[dict] = None
    ports: Optional[dict] = None
    mounts: Optional[dict] = None
    labels: Optional[dict] = None
    network: str = ""
    restart_policy: str = ""
    healthcheck: Optional[dict] = None  # {type: tcp/http/cmd, target, port, path, retries, delay}
    pre_cmd: str = ""
    post_cmd: str = ""
    pull_policy: str = Field(default="always", pattern="^(always|missing)$")
    rollback_enabled: bool = True
    hosts: list[DeployHostItem] = []


class DeployProjectUpdate(BaseModel):
    name: Optional[str] = None
    project_id: Optional[int] = None
    registry_url: Optional[str] = None
    image_repo: Optional[str] = None
    default_tag: Optional[str] = None
    build_type: Optional[str] = None
    build_host_id: Optional[int] = None
    build_context: Optional[str] = None
    dockerfile: Optional[str] = None
    build_args: Optional[dict] = None
    runtime: Optional[str] = None
    namespace: Optional[str] = None
    env: Optional[dict] = None
    ports: Optional[dict] = None
    mounts: Optional[dict] = None
    labels: Optional[dict] = None
    network: Optional[str] = None
    restart_policy: Optional[str] = None
    healthcheck: Optional[dict] = None
    pre_cmd: Optional[str] = None
    post_cmd: Optional[str] = None
    pull_policy: Optional[str] = None
    rollback_enabled: Optional[bool] = None
    hosts: Optional[list[DeployHostItem]] = None


class DeployProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    project_id: Optional[int]
    registry_url: str
    image_repo: str
    default_tag: str
    build_type: str = ""
    build_host_id: Optional[int] = None
    build_context: str = ""
    dockerfile: str = "Dockerfile"
    build_args: Optional[dict] = None
    runtime: str
    namespace: str
    env: Optional[dict]
    ports: Optional[dict]
    mounts: Optional[dict]
    labels: Optional[dict]
    network: str
    restart_policy: str
    healthcheck: Optional[dict]
    pre_cmd: str
    post_cmd: str
    pull_policy: str
    rollback_enabled: bool
    created_by: str
    created_at: datetime
    host_ids: list[int] = []


class DeployActionRequest(BaseModel):
    image_tag: Optional[str] = None
    host_ids: Optional[list[int]] = None  # 不传则部署全部 enabled 主机


class DeployRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    deploy_project_id: int
    task_id: Optional[int]
    image_tag: str
    action: str
    status: str
    from_tag: Optional[str]
    triggered_by: str
    stats: Optional[dict]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime
