"""指标查询服务：时间桶降采样 + 大屏概览。"""
from datetime import datetime, timedelta, timezone
from app.core.time import now_cn

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scope import apply_scope
from app.models.host import Host
from app.models.metric import MetricDisk, MetricHost


def now() -> datetime:
    return now_cn()


async def host_history(
    db: AsyncSession, host_id: int, metric: str, minutes: int = 60, points: int = 60,
) -> list[dict]:
    """按时间桶聚合的折线数据。metric ∈ {cpu_usage, mem_used_pct, load1, net_rx_kbps, net_tx_kbps, disk_root_used_pct}"""
    allowed = {
        "cpu_usage", "cpu_user", "cpu_sys", "cpu_iowait", "mem_used_pct", "load1", "load5",
        "load15", "net_rx_kbps", "net_tx_kbps", "disk_root_used_pct", "swap_used_pct",
    }
    if metric not in allowed:
        from app.core.exceptions import ValidationAppError

        raise ValidationAppError(f"不支持的指标: {metric}")

    from_col = getattr(MetricHost, metric)
    since = now() - timedelta(minutes=minutes)
    bucket = max(1, minutes * 60 // max(1, points))
    # MySQL: FROM_UNIXTIME(FLOOR(UNIX_TIMESTAMP(collected_at)/bucket)*bucket)
    # SQLite 无 UNIX_TIMESTAMP，用 strftime；两种方言统一在 Python 侧聚合更简单可靠
    rows = (await db.execute(
        select(MetricHost.collected_at, from_col)
        .where(MetricHost.host_id == host_id, MetricHost.collected_at >= since)
        .order_by(MetricHost.collected_at)
    )).all()
    buckets: dict[int, list[tuple[datetime, float]]] = {}
    for ts, val in rows:
        if val is None:
            continue
        key = int(ts.timestamp()) // bucket * bucket
        buckets.setdefault(key, []).append(float(val))
    return [
        {"time": datetime.fromtimestamp(k, tz=timezone.utc).strftime("%H:%M:%S"),
         "avg": round(sum(v) / len(v), 2), "max": round(max(v), 2)}
        for k, v in sorted(buckets.items())
    ]


async def latest_snapshot(db: AsyncSession, host_id: int) -> dict | None:
    row = (await db.execute(
        select(MetricHost).where(MetricHost.host_id == host_id).order_by(desc(MetricHost.collected_at)).limit(1)
    )).scalar_one_or_none()
    if not row:
        return None
    return {
        "collected_at": row.collected_at, "cpu_usage": row.cpu_usage, "mem_used_pct": row.mem_used_pct,
        "load1": row.load1, "net_rx_kbps": row.net_rx_kbps, "net_tx_kbps": row.net_tx_kbps,
        "disk_root_used_pct": row.disk_root_used_pct, "uptime_s": row.uptime_s,
        "mem_total_mb": row.mem_total_mb, "mem_used_mb": row.mem_used_mb,
    }


async def latest_disks(db: AsyncSession, host_id: int) -> list[dict]:
    latest = (await db.execute(
        select(MetricHost.collected_at).where(MetricHost.host_id == host_id)
        .order_by(desc(MetricHost.collected_at)).limit(1)
    )).scalar_one_or_none()
    if not latest:
        return []
    rows = (await db.execute(
        select(MetricDisk).where(MetricDisk.host_id == host_id, MetricDisk.collected_at == latest)
    )).scalars().all()
    return [{"mount": r.mount, "device": r.device, "total_mb": r.total_mb,
             "used_mb": r.used_mb, "used_pct": r.used_pct} for r in rows]


async def dashboard_overview(db: AsyncSession) -> dict:
    """大屏概览：主机统计 + 全局均值 + Top 主机（按当前 Agent 主机收窄）。"""
    stmt = apply_scope(select(Host).where(Host.enabled.is_(True)), Host)
    hosts = list((await db.execute(stmt)).scalars().all())
    total = len(hosts)
    online = sum(1 for h in hosts if h.status == "online")
    by_type = {"app": 0, "agent": 0, "managed": 0}
    for h in hosts:
        by_type[h.host_type] = by_type.get(h.host_type, 0) + 1

    # 各主机最新一条指标
    recent = {}
    for h in hosts:
        snap = await latest_snapshot(db, h.id)
        if snap:
            recent[h.id] = snap

    def _avg(key: str) -> float | None:
        vals = [s[key] for s in recent.values() if s.get(key) is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    cpu_top = sorted(
        ({"host_id": hid, "hostname": next(h.hostname for h in hosts if h.id == hid), "cpu_usage": s["cpu_usage"]}
         for hid, s in recent.items() if s.get("cpu_usage") is not None),
        key=lambda x: x["cpu_usage"], reverse=True,
    )[:10]

    return {
        "total": total, "online": online, "offline": total - online,
        "by_type": by_type,
        "avg": {"cpu_usage": _avg("cpu_usage"), "mem_used_pct": _avg("mem_used_pct"),
                "net_rx_kbps": _avg("net_rx_kbps"), "net_tx_kbps": _avg("net_tx_kbps")},
        "cpu_top": cpu_top,
        "hosts": [
            {"host_id": h.id, "hostname": h.hostname, "ip": h.ip, "status": h.status,
             "host_type": h.host_type, "cpu_usage": (recent.get(h.id) or {}).get("cpu_usage"),
             "mem_used_pct": (recent.get(h.id) or {}).get("mem_used_pct"),
             "last_collect_at": h.last_collect_at}
            for h in hosts
        ],
    }
