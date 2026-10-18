"""Playbook / 任务 / 任务事件 / 任务目标。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, PkMixin, TimestampMixin


class Playbook(Base, PkMixin, TimestampMixin):
    __tablename__ = "playbook"

    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), default="")
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("project.id", ondelete="SET NULL"), default=None)
    entry_file: Mapped[str] = mapped_column(String(128), default="site.yml")
    disk_path: Mapped[str] = mapped_column(String(255))  # data/playbooks/{id}/
    tags: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    agent_host_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("host.id", ondelete="SET NULL"), default=None, index=True
    )  # 归属的 Agent 主机
    created_by: Mapped[Optional[str]] = mapped_column(String(64), default="")


class Task(Base, PkMixin, TimestampMixin):
    __tablename__ = "task"

    name: Mapped[str] = mapped_column(String(128))
    task_type: Mapped[str] = mapped_column(String(16), default="playbook")  # adhoc/playbook/deploy
    agent_host_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("host.id", ondelete="SET NULL"), default=None, index=True
    )  # 归属的 Agent 主机
    playbook_id: Mapped[Optional[int]] = mapped_column(ForeignKey("playbook.id", ondelete="SET NULL"), default=None)
    inventory: Mapped[Optional[dict]] = mapped_column(JSON, default=None)  # {host_ids, group_ids, extra}
    extra_vars: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # pending/queued/running/success/failed/canceled/timeout
    triggered_by: Mapped[Optional[str]] = mapped_column(String(64), default="")
    deploy_record_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    rc: Mapped[Optional[int]] = mapped_column(SmallInteger, default=None)
    stats: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    message: Mapped[Optional[str]] = mapped_column(Text, default=None)

    targets: Mapped[list["TaskTarget"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="selectin"
    )


class TaskEvent(Base, PkMixin):
    __tablename__ = "task_event"

    task_id: Mapped[int] = mapped_column(ForeignKey("task.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    ts: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    level: Mapped[str] = mapped_column(String(16), default="info")  # info/warn/error/debug
    host: Mapped[Optional[str]] = mapped_column(String(128), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    raw_event: Mapped[Optional[dict]] = mapped_column(JSON, default=None)

    __table_args__ = (UniqueConstraint("task_id", "seq", name="uq_task_event_seq"),)


class TaskTarget(Base, PkMixin):
    __tablename__ = "task_target"

    task_id: Mapped[int] = mapped_column(ForeignKey("task.id", ondelete="CASCADE"), index=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("host.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # pending/running/changed/ok/failed/unreachable/skipped
    rc: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    summary: Mapped[Optional[str]] = mapped_column(Text, default="")

    task: Mapped[Task] = relationship(back_populates="targets")
