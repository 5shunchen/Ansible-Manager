"""系统表：用户/角色/菜单/关联/审计/配置。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, SmallInteger, String, Table, Column, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, PkMixin, TimestampMixin

user_role = Table(
    "sys_user_role",
    Base.metadata,
    Column("user_id", ForeignKey("sys_user.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("sys_role.id", ondelete="CASCADE"), primary_key=True),
)

role_menu = Table(
    "sys_role_menu",
    Base.metadata,
    Column("role_id", ForeignKey("sys_role.id", ondelete="CASCADE"), primary_key=True),
    Column("menu_id", ForeignKey("sys_menu.id", ondelete="CASCADE"), primary_key=True),
)


class SysUser(Base, PkMixin, TimestampMixin):
    __tablename__ = "sys_user"

    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    email: Mapped[Optional[str]] = mapped_column(String(128), default="")
    nickname: Mapped[Optional[str]] = mapped_column(String(64), default="")
    phone: Mapped[Optional[str]] = mapped_column(String(32), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)

    roles: Mapped[list["SysRole"]] = relationship(secondary=user_role, lazy="selectin")


class SysRole(Base, PkMixin, TimestampMixin):
    __tablename__ = "sys_role"

    name: Mapped[str] = mapped_column(String(64))
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    menus: Mapped[list["SysMenu"]] = relationship(secondary=role_menu, lazy="selectin")


class SysMenu(Base, PkMixin, TimestampMixin):
    __tablename__ = "sys_menu"

    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sys_menu.id", ondelete="CASCADE"), default=None, index=True)
    name: Mapped[str] = mapped_column(String(64))
    path: Mapped[Optional[str]] = mapped_column(String(128), default="")
    component: Mapped[Optional[str]] = mapped_column(String(128), default="")
    icon: Mapped[Optional[str]] = mapped_column(String(64), default="")
    sort: Mapped[int] = mapped_column(SmallInteger, default=0)
    menu_type: Mapped[str] = mapped_column(String(16), default="menu")  # dir/menu/button
    permission: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)


class SysAuditLog(Base, PkMixin):
    __tablename__ = "sys_audit_log"

    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL"))
    username: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(64))  # 如 host.create
    resource_type: Mapped[Optional[str]] = mapped_column(String(64), default="")
    resource_id: Mapped[Optional[str]] = mapped_column(String(64), default="")
    detail: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    ip: Mapped[str] = mapped_column(String(64), default="")
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class SysConfig(Base, PkMixin, TimestampMixin):
    __tablename__ = "sys_config"

    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    value: Mapped[dict | int | str | bool | None] = mapped_column(JSON)
    description: Mapped[Optional[str]] = mapped_column(String(255), default="")
    updated_by: Mapped[Optional[str]] = mapped_column(String(64), default="")
