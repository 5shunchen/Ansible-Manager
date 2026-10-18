"""APScheduler 装配：采集 tick / 健康检查 / 指标清理。"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.workers.collector import now


async def _health_check() -> None:
    """SSH 连通性探测，维护 host.status（离线主机探测恢复）。"""
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.host import Host
    from app.runner.ssh.asyncssh_transport import transport_factory
    from app.services import host_service

    async with AsyncSessionLocal() as db:
        hosts = list((await db.execute(select(Host.id).where(Host.enabled.is_(True)))).scalars().all())
    for hid in hosts:
        async with AsyncSessionLocal() as db:
            h = await db.get(Host, hid)
            target = await host_service.build_ssh_target(db, h)
            t = transport_factory(target)
            try:
                await t.connect()
                h.status, h.fail_count = "online", 0
            except Exception:  # noqa: BLE001
                h.status = "offline"
            finally:
                await t.close()
            h.last_check_at = now()
            await db.commit()


async def _metrics_retention() -> None:
    """每日清理过期指标，分批 DELETE 避免大锁。"""
    from datetime import timedelta

    from sqlalchemy import delete, select

    from app.db.session import AsyncSessionLocal
    from app.models.metric import MetricCollectLog, MetricDisk, MetricHost
    from app.services import config_service

    async with AsyncSessionLocal() as db:
        days = await config_service.get_int(db, "metric.retention_days", 30)
        cutoff = now() - timedelta(days=days)
        time_cols = {
            MetricHost: MetricHost.collected_at,
            MetricDisk: MetricDisk.collected_at,
            MetricCollectLog: MetricCollectLog.finished_at,
        }
        for model, time_col in time_cols.items():
            while True:
                stale_ids = select(model.id).where(time_col < cutoff).limit(10000)
                result = await db.execute(delete(model).where(model.id.in_(stale_ids)))
                await db.commit()
                if result.rowcount < 10000:
                    break


def build_scheduler() -> AsyncIOScheduler:
    from app.workers.collector import collect_tick

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(collect_tick, IntervalTrigger(seconds=10), id="collector_tick", max_instances=1)
    scheduler.add_job(_health_check, IntervalTrigger(minutes=5), id="host_health_check", max_instances=1)
    scheduler.add_job(_metrics_retention, IntervalTrigger(hours=24), id="metrics_retention", max_instances=1)
    return scheduler
