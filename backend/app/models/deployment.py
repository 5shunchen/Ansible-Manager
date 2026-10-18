"""插件 / 部署工程 / 部署目标主机 / 部署记录 / 容器当前态。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, PkMixin, TimestampMixin


class Plugin(Base, PkMixin, TimestampMixin):
    __tablename__ = "plugin"

    name: Mapped[str] = mapped_column(String(128), unique=True)
    plugin_type: Mapped[str] = mapped_column(String(16), default="collection")  # collection/role
    source: Mapped[str] = mapped_column(String(255))  # galaxy 名或 git URL
    version: Mapped[Optional[str]] = mapped_column(String(64), default="")
    description: Mapped[Optional[str]] = mapped_column(String(255), default="")
    install_status: Mapped[str] = mapped_column(String(16), default="none")  # none/installing/installed/failed
    install_log: Mapped[Optional[str]] = mapped_column(Text, default="")
    installed_path: Mapped[Optional[str]] = mapped_column(String(255), default="")
    config: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    created_by: Mapped[Optional[str]] = mapped_column(String(64), default="")


class DeployProject(Base, PkMixin, TimestampMixin):
    __tablename__ = "deploy_project"

    name: Mapped[str] = mapped_column(String(128), unique=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("project.id", ondelete="SET NULL"), default=None)
    agent_host_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("host.id", ondelete="SET NULL"), default=None, index=True
    )  # 归属的 Agent 主机
    registry_url: Mapped[Optional[str]] = mapped_column(String(255), default="")
    image_repo: Mapped[str] = mapped_column(String(255))
    default_tag: Mapped[str] = mapped_column(String(64), default="latest")
    # 镜像来源：空 = 从 registry 拉取；docker = 在构建主机用 Docker 服务构建后分发
    build_type: Mapped[str] = mapped_column(String(16), default="")
    build_host_id: Mapped[Optional[int]] = mapped_column(ForeignKey("host.id", ondelete="SET NULL"), default=None)
    build_context: Mapped[Optional[str]] = mapped_column(String(255), default="")
    dockerfile: Mapped[Optional[str]] = mapped_column(String(128), default="Dockerfile")
    build_args: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    runtime: Mapped[str] = mapped_column(String(16), default="nerdctl")  # nerdctl/ctr
    namespace: Mapped[str] = mapped_column(String(64), default="k8s.io")
    env: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    ports: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    mounts: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    labels: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    network: Mapped[Optional[str]] = mapped_column(String(64), default="")
    restart_policy: Mapped[Optional[str]] = mapped_column(String(32), default="")
    healthcheck: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    pre_cmd: Mapped[Optional[str]] = mapped_column(Text, default="")
    post_cmd: Mapped[Optional[str]] = mapped_column(Text, default="")
    pull_policy: Mapped[str] = mapped_column(String(16), default="always")  # always/missing
    rollback_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(64), default="")

    hosts: Mapped[list["DeployProjectHost"]] = relationship(
        back_populates="deploy_project", cascade="all, delete-orphan", lazy="selectin"
    )


class DeployProjectHost(Base, PkMixin, TimestampMixin):
    __tablename__ = "deploy_project_host"
    __table_args__ = (UniqueConstraint("deploy_project_id", "host_id", name="uq_deploy_host"),)

    deploy_project_id: Mapped[int] = mapped_column(ForeignKey("deploy_project.id", ondelete="CASCADE"), index=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("host.id", ondelete="CASCADE"))
    container_name: Mapped[str] = mapped_column(String(128), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    deploy_project: Mapped[DeployProject] = relationship(back_populates="hosts")
    container: Mapped[Optional["DeployContainer"]] = relationship(
        back_populates="deploy_host", cascade="all, delete-orphan", lazy="selectin"
    )


class DeployRecord(Base, PkMixin, TimestampMixin):
    __tablename__ = "deploy_record"

    deploy_project_id: Mapped[int] = mapped_column(ForeignKey("deploy_project.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("task.id", ondelete="SET NULL"), default=None)
    image_tag: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(16), default="deploy")  # deploy/rollback/restart/stop/start
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    from_tag: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    triggered_by: Mapped[Optional[str]] = mapped_column(String(64), default="")
    stats: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)


class DeployContainer(Base, PkMixin, TimestampMixin):
    __tablename__ = "deploy_container"
    __table_args__ = (UniqueConstraint("deploy_project_host_id", name="uq_deploy_container"),)

    deploy_project_host_id: Mapped[int] = mapped_column(
        ForeignKey("deploy_project_host.id", ondelete="CASCADE"), index=True
    )
    container_id: Mapped[Optional[str]] = mapped_column(String(128), default="")
    container_name: Mapped[str] = mapped_column(String(128), default="")
    current_tag: Mapped[Optional[str]] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="unknown")  # running/stopped/unknown
    deployed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)

    deploy_host: Mapped[DeployProjectHost] = relationship(
        back_populates="container", foreign_keys=[deploy_project_host_id]
    )


class HostApp(Base, PkMixin, TimestampMixin):
    """应用主机上已安装的 App（插件包）实例：一台主机 + 一个插件 = 一条记录。

    与 DeployContainer 的区别：DeployContainer 跟踪容器镜像 tag；HostApp 跟踪插件包的
    安装状态/版本/最近一次任务。两者互不影响。
    """

    __tablename__ = "host_app"
    __table_args__ = (UniqueConstraint("host_id", "plugin_id", name="uq_host_app"),)

    host_id: Mapped[int] = mapped_column(ForeignKey("host.id", ondelete="CASCADE"), index=True)
    plugin_id: Mapped[int] = mapped_column(ForeignKey("plugin.id", ondelete="CASCADE"))
    # unknown/installing/installed/running/failed/uninstalling
    status: Mapped[str] = mapped_column(String(16), default="unknown", index=True)
    version: Mapped[Optional[str]] = mapped_column(String(64), default="")
    last_task_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("task.id", ondelete="SET NULL"), default=None
    )
    installed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    uninstalled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    extra_vars: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
