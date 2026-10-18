"""监控指标：metric_host 宽表 / metric_disk / 采集日志。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, PkMixin


class MetricHost(Base, PkMixin):
    __tablename__ = "metric_host"
    __table_args__ = (Index("ix_metric_host_host_time", "host_id", "collected_at"),)

    host_id: Mapped[int] = mapped_column(ForeignKey("host.id", ondelete="CASCADE"))
    collected_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    cpu_usage: Mapped[Optional[float]] = mapped_column(Float, default=None)
    cpu_user: Mapped[Optional[float]] = mapped_column(Float, default=None)
    cpu_sys: Mapped[Optional[float]] = mapped_column(Float, default=None)
    cpu_iowait: Mapped[Optional[float]] = mapped_column(Float, default=None)
    load1: Mapped[Optional[float]] = mapped_column(Float, default=None)
    load5: Mapped[Optional[float]] = mapped_column(Float, default=None)
    load15: Mapped[Optional[float]] = mapped_column(Float, default=None)
    mem_total_mb: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    mem_used_mb: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    mem_used_pct: Mapped[Optional[float]] = mapped_column(Float, default=None)
    swap_total_mb: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    swap_used_pct: Mapped[Optional[float]] = mapped_column(Float, default=None)
    disk_root_used_pct: Mapped[Optional[float]] = mapped_column(Float, default=None)
    net_rx_kbps: Mapped[Optional[float]] = mapped_column(Float, default=None)
    net_tx_kbps: Mapped[Optional[float]] = mapped_column(Float, default=None)
    uptime_s: Mapped[Optional[int]] = mapped_column(BigInteger, default=None)


class MetricDisk(Base, PkMixin):
    __tablename__ = "metric_disk"
    __table_args__ = (Index("ix_metric_disk_host_time", "host_id", "collected_at"),)

    host_id: Mapped[int] = mapped_column(ForeignKey("host.id", ondelete="CASCADE"))
    collected_at: Mapped[datetime] = mapped_column(DateTime)
    mount: Mapped[str] = mapped_column(String(255))
    device: Mapped[Optional[str]] = mapped_column(String(128), default="")
    total_mb: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    used_mb: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    used_pct: Mapped[Optional[float]] = mapped_column(Float, default=None)


class MetricCollectLog(Base, PkMixin):
    __tablename__ = "metric_collect_log"

    host_id: Mapped[int] = mapped_column(ForeignKey("host.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    status: Mapped[str] = mapped_column(String(16), default="ok")  # ok/failed
    error: Mapped[Optional[str]] = mapped_column(Text, default=None)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, default=None)
