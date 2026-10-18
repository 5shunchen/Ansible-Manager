"""采集器编排：并发控制 + 重试 + 入库 + 主机状态机。"""
import asyncio
import time
from datetime import datetime, timedelta, timezone
from app.core.time import now_cn

from app.core.logging import get_logger
from app.runner.ssh.asyncssh_transport import transport_factory
from app.runner.ssh.command_script import COLLECT_SCRIPT, parse_metric_sections

logger = get_logger(__name__)

_in_flight: set[int] = set()
_last_net: dict[int, tuple[float, float]] = {}  # host_id → (rx_bytes, tx_bytes, ts) 跨周期网络差分


def now() -> datetime:
    """东八区当前时间（now_cn 已含 +8）。"""
    return now_cn()


async def collect_host(host_id: int, *, transport_factory_fn=transport_factory) -> None:
    """单主机一次采集。失败重试 → 记日志 → fail_count++ → 连续 3 次置 offline。"""
    from app.db.session import AsyncSessionLocal
    from app.models.host import Host
    from app.models.metric import MetricCollectLog, MetricDisk, MetricHost
    from app.services import config_service, host_service

    started = time.monotonic()
    async with AsyncSessionLocal() as db:
        host = await db.get(Host, host_id)
        if not host or not host.enabled:
            _in_flight.discard(host_id)
            return
        # Agent 主机自身：只有"已安装"才承担采集与控制职责，未安装直接跳过
        # （未安装的 Agent 主机名下被管主机也因此不会被正常调度）
        if host.host_type == "agent" and host.agent_status not in ("installed", "running"):
            _in_flight.discard(host_id)
            return
        # 被管主机：若挂在某个 Agent 主机名下，需该 Agent 已安装才采集（否则无控制节点）
        if host.agent_host_id:
            owner = await db.get(Host, host.agent_host_id)
            if owner and owner.host_type == "agent" and owner.agent_status not in ("installed", "running"):
                _in_flight.discard(host_id)
                return
        retry = await config_service.get_int(db, "collect.retry", 2)
        timeout = await config_service.get_int(db, "collect.timeout", 15)

        target = await host_service.build_ssh_target(db, host)
        out = None
        error_msg = ""
        for attempt in range(retry + 1):
            transport = transport_factory_fn(target)
            try:
                await transport.connect()
                result = await transport.exec(COLLECT_SCRIPT, timeout=timeout + 5)
                if result.rc != 0:
                    raise RuntimeError(f"远端脚本退出码 {result.rc}: {result.stderr[:200]}")
                out = result.stdout
                break
            except Exception as e:  # noqa: BLE001
                error_msg = str(e)
                if attempt < retry:
                    await asyncio.sleep(1.5 * (attempt + 1))
            finally:
                await transport.close()

        if out is None:
            await _mark_fail(db, host, error_msg, started)
            _in_flight.discard(host_id)
            return

        try:
            samples = parse_metric_sections(out)
        except ValueError as e:
            await _mark_fail(db, host, f"指标解析失败: {e}", started)
            _in_flight.discard(host_id)
            return

        # 网络差分（/proc/net/dev 最后两列 rx/tx）
        net_rx = net_tx = None
        rx_sum = tx_sum = 0
        for line in out.splitlines():
            if ":" in line and "|" not in line and line.count(":") == 1:
                iface, data = line.split(":")
                fields = data.split()
                if len(fields) >= 9:
                    try:
                        rx_sum += int(fields[0])
                        tx_sum += int(fields[8])
                    except ValueError:
                        continue
        ts = time.monotonic()
        prev = _last_net.get(host_id)
        if prev:
            dt = ts - prev[2]
            if dt > 0:
                net_rx = round((rx_sum - prev[0]) / dt / 1024, 2)
                net_tx = round((tx_sum - prev[1]) / dt / 1024, 2)
        _last_net[host_id] = (rx_sum, tx_sum, ts)

        collected_at = now()
        db.add(MetricHost(
            host_id=host_id, collected_at=collected_at,
            cpu_usage=samples.get("cpu_usage"), cpu_user=samples.get("cpu_user"),
            cpu_sys=samples.get("cpu_sys"), cpu_iowait=samples.get("cpu_iowait"),
            load1=samples.get("load1"), load5=samples.get("load5"), load15=samples.get("load15"),
            mem_total_mb=samples.get("mem_total_mb"), mem_used_mb=samples.get("mem_used_mb"),
            mem_used_pct=samples.get("mem_used_pct"), swap_total_mb=samples.get("swap_total_mb"),
            swap_used_pct=samples.get("swap_used_pct"), disk_root_used_pct=samples.get("disk_root_used_pct"),
            net_rx_kbps=net_rx, net_tx_kbps=net_tx, uptime_s=samples.get("uptime_s"),
        ))
        for d in samples.get("disks", []):
            db.add(MetricDisk(
                host_id=host_id, collected_at=collected_at, mount=d["mount"], device=d["device"],
                total_mb=d["total_mb"], used_mb=d["used_mb"], used_pct=d["used_pct"],
            ))
        db.add(MetricCollectLog(
            host_id=host_id, started_at=host.last_collect_at or collected_at,
            finished_at=collected_at, status="ok", duration_ms=int((time.monotonic() - started) * 1000),
        ))
        host.status, host.fail_count = "online", 0
        host.last_collect_at = collected_at
        await db.commit()

    _in_flight.discard(host_id)


async def _mark_fail(db, host, error_msg: str, started: float) -> None:
    """失败入库：collect_log + fail_count++，连续 3 次置 offline。"""
    from app.models.metric import MetricCollectLog

    failed_at = now()
    db.add(MetricCollectLog(
        host_id=host.id, started_at=host.last_collect_at or failed_at, finished_at=failed_at,
        status="failed", error=(error_msg or "unknown")[:1000],
        duration_ms=int((time.monotonic() - started) * 1000),
    ))
    host.fail_count = (host.fail_count or 0) + 1
    if host.fail_count >= 3:
        host.status = "offline"
    await db.commit()
    logger.warning("collect_failed", host_id=host.id, error=error_msg[:200], fail_count=host.fail_count)


async def collect_tick(transport_factory_fn=transport_factory) -> None:
    """APScheduler 10s tick：动态读 interval，派发到期主机。"""
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.host import Host
    from app.services import config_service

    async with AsyncSessionLocal() as db:
        enabled = await config_service.get_bool(db, "collect.enabled", True)
        if not enabled:
            return
        interval = await config_service.get_int(db, "collect.interval_seconds", 60)
        concurrency = await config_service.get_int(db, "collect.concurrency", 20)
        due = list((await db.execute(select(Host.id).where(
            Host.enabled.is_(True),
            (Host.last_collect_at.is_(None))
            | (Host.last_collect_at <= now() - timedelta(seconds=interval))
        ))).scalars().all())
        # 派发时立即置 last_collect_at，防止下个 tick 重复派发
        for hid in due:
            h = await db.get(Host, hid)
            h.last_collect_at = now()
        await db.commit()

    running = len(_in_flight)
    slots = max(0, concurrency - running)
    for hid in due[:slots]:
        if hid in _in_flight:
            continue
        _in_flight.add(hid)
        asyncio.get_event_loop().create_task(collect_host(hid, transport_factory_fn=transport_factory_fn))
    if len(due) > slots:
        logger.info("collect_backlog", due=len(due), dispatched=slots)
