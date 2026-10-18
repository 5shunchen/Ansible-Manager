"""项目 / SSH凭据 / 主机 / 主机组。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, JSON, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, PkMixin, TimestampMixin


class Project(Base, PkMixin, TimestampMixin):
    __tablename__ = "project"

    name: Mapped[str] = mapped_column(String(64), unique=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), default="")
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="active")  # active/archived
    agent_host_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("host.id", ondelete="SET NULL"), default=None, index=True
    )  # 归属的 Agent 主机


class SshCredential(Base, PkMixin, TimestampMixin):
    __tablename__ = "ssh_credential"

    name: Mapped[str] = mapped_column(String(64), unique=True)
    auth_type: Mapped[str] = mapped_column(String(16))  # password/private_key
    username: Mapped[str] = mapped_column(String(64))
    password_enc: Mapped[Optional[str]] = mapped_column(String(512), default=None)
    private_key_enc: Mapped[Optional[str]] = mapped_column(Text, default=None)
    passphrase_enc: Mapped[Optional[str]] = mapped_column(String(512), default=None)
    default_port: Mapped[int] = mapped_column(SmallInteger, default=22)
    created_by: Mapped[Optional[str]] = mapped_column(String(64), default="")


class Host(Base, PkMixin, TimestampMixin):
    __tablename__ = "host"

    hostname: Mapped[str] = mapped_column(String(128))
    ip: Mapped[str] = mapped_column(String(64), index=True)
    port: Mapped[int] = mapped_column(SmallInteger, default=22)
    host_type: Mapped[str] = mapped_column(String(16), default="managed", index=True)  # app/agent/managed
    # 归属的 Agent 主机（host_type=agent 的记录）：被管主机挂到控制机下；控制机自身为 NULL
    agent_host_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("host.id", ondelete="SET NULL"), default=None, index=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("project.id", ondelete="SET NULL"), default=None)
    credential_id: Mapped[int] = mapped_column(ForeignKey("ssh_credential.id", ondelete="RESTRICT"))
    os_type: Mapped[Optional[str]] = mapped_column(String(32), default=None)
    os_release: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    cpu_cores: Mapped[Optional[int]] = mapped_column(SmallInteger, default=None)
    mem_total_mb: Mapped[Optional[int]] = mapped_column(BigInteger, default=None)
    status: Mapped[str] = mapped_column(String(16), default="unknown", index=True)  # unknown/online/offline
    # Agent 主机生命周期：not_installed/installed/running/error（仅 host_type=agent 有意义）
    agent_status: Mapped[str] = mapped_column(String(16), default="not_installed")
    agent_version: Mapped[Optional[str]] = mapped_column(String(32), default=None)
    # Agent 主机专属 playbook 存放目录（创建时规划，默认 /opt/ansible）
    playbook_dir: Mapped[Optional[str]] = mapped_column(String(255), default="/opt/ansible")
    fail_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    last_check_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    last_collect_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    description: Mapped[Optional[str]] = mapped_column(String(255), default="")
    tags: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    credential: Mapped["SshCredential"] = relationship(lazy="joined")
    groups: Mapped[list["HostGroup"]] = relationship(
        secondary="host_group_member", back_populates="hosts", lazy="selectin"
    )


class HostGroup(Base, PkMixin, TimestampMixin):
    __tablename__ = "host_group"

    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), default="")
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("project.id", ondelete="SET NULL"), default=None)
    vars: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    agent_host_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("host.id", ondelete="SET NULL"), default=None, index=True
    )  # 归属的 Agent 主机

    hosts: Mapped[list[Host]] = relationship(
        secondary="host_group_member", back_populates="groups", lazy="selectin"
    )


class HostGroupMember(Base):
    __tablename__ = "host_group_member"

    group_id: Mapped[int] = mapped_column(ForeignKey("host_group.id", ondelete="CASCADE"), primary_key=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("host.id", ondelete="CASCADE"), primary_key=True)
