"""sys_config 运行时参数服务：60s 内存缓存，改配置后主动失效。"""
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.system import SysConfig

_cache: dict = {}
_cache_ts: float = 0
_TTL = 60.0

# 运行时可调参数及默认值（.env 只管静态配置，这里管运行时热更新）
DEFAULTS: dict = {
    "collect.interval_seconds": 60,
    "collect.concurrency": 20,
    "collect.timeout": 15,
    "collect.retry": 2,
    "collect.enabled": True,
    "metric.retention_days": 30,
    "task.max_concurrent": 5,
    "task.default_timeout": 3600,
    "terminal.enabled": True,
    # 部署用隔离 containerd 套件：目标机独立目录 + 可选二进制 bundle（URL 或 file: 控制端路径）
    "deploy.containerd_dir": "/opt/am-containerd",
    "deploy.containerd_bundle": "",
    "deploy.registry_plain_http": True,
}


def invalidate_cache() -> None:
    global _cache_ts
    _cache.clear()
    _cache_ts = 0.0


async def _load_all(db: AsyncSession) -> dict:
    rows = (await db.execute(select(SysConfig))).scalars().all()
    return {r.key: r.value for r in rows}


async def get(db: AsyncSession, key: str, default=None):
    """读运行时配置；未配置时回落 DEFAULTS 再回落 settings/.env。"""
    global _cache_ts
    now = time.monotonic()
    if not _cache or now - _cache_ts > _TTL:
        _cache.clear()
        _cache.update(await _load_all(db))
        _cache_ts = now
    if key in _cache:
        return _cache[key]
    if key in DEFAULTS:
        return DEFAULTS[key]
    # .env 同名兜底（collect.interval_seconds → settings.collect_interval_seconds）
    env_key = key.replace(".", "_")
    return getattr(settings, env_key, default)


async def get_int(db: AsyncSession, key: str, default: int = 0) -> int:
    v = await get(db, key)
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


async def get_bool(db: AsyncSession, key: str, default: bool = False) -> bool:
    v = await get(db, key)
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("1", "true", "yes", "on")
