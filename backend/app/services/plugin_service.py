"""插件服务：ansible-galaxy 安装（后台线程）+ 状态轮询。"""
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.deployment import Plugin
from app.schemas.deployment import PluginCreate, PluginUpdate

logger = get_logger(__name__)


async def list_plugins(db: AsyncSession, keyword: str | None = None) -> list[Plugin]:
    stmt = select(Plugin)
    if keyword:
        stmt = stmt.where(Plugin.name.like(f"%{keyword}%"))
    return list((await db.execute(stmt.order_by(Plugin.id.desc()))).scalars().all())


async def create_plugin(db: AsyncSession, req: PluginCreate, created_by: str = "") -> Plugin:
    p = Plugin(**req.model_dump(), created_by=created_by, install_status="none")
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def update_plugin(db: AsyncSession, pid: int, req: PluginUpdate) -> Plugin:
    p = await db.get(Plugin, pid)
    if not p:
        raise NotFoundError("插件不存在")
    for f, v in req.model_dump(exclude_unset=True).items():
        setattr(p, f, v)
    await db.commit()
    return p


async def delete_plugin(db: AsyncSession, pid: int) -> None:
    p = await db.get(Plugin, pid)
    if not p:
        raise NotFoundError("插件不存在")
    await db.delete(p)
    await db.commit()


def _galaxy_args(p: Plugin) -> list[str]:
    args = ["ansible-galaxy", "collection" if p.plugin_type == "collection" else "role", "install"]
    if p.plugin_type == "collection":
        args += ["-p", str(settings.plugin_dir / "collections"), "-c"]
    else:
        args += ["-p", str(settings.plugin_dir / "roles"), "-c"]
    src = p.source
    if p.version:
        src = f"{src}:{p.version}" if ":" not in src else src
    args.append(src)
    return args


async def install_plugin(db: AsyncSession, pid: int) -> Plugin:
    """后台线程执行 ansible-galaxy install，状态轮询由前端刷新。"""
    p = await db.get(Plugin, pid)
    if not p:
        raise NotFoundError("插件不存在")
    if p.install_status == "installing":
        return p
    p.install_status, p.install_log = "installing", ""
    await db.commit()

    args = _galaxy_args(p)
    logger.info("plugin_install", plugin=p.name, args=" ".join(args))

    async def _run():
        from app.db.session import AsyncSessionLocal

        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            env={"PATH": "/usr/local/bin:/usr/bin:/bin:~/.local/bin", "HOME": "/root", "ANSIBLE_CONFIG": "/dev/null"},
        )
        out, _ = await proc.communicate()
        log = (out or b"").decode(errors="replace")[-10000:]
        async with AsyncSessionLocal() as db2:
            pl = await db2.get(Plugin, pid)
            pl.install_status = "installed" if proc.returncode == 0 else "failed"
            pl.install_log = log
            pl.installed_path = str(settings.plugin_dir / ("collections" if pl.plugin_type == "collection" else "roles"))
            await db2.commit()

    asyncio.get_event_loop().create_task(_run())
    await db.refresh(p)
    return p
