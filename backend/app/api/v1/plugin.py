"""插件路由。"""
from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbDep, require_perm
from app.core.response import ok
from app.schemas.deployment import PluginCreate, PluginOut, PluginUpdate
from app.services import plugin_service

plugins_router = APIRouter(prefix="/plugins", tags=["plugins"])


@plugins_router.get("")
async def list_plugins(db: DbDep, _: CurrentUser, keyword: str = Query(None)):
    rows = await plugin_service.list_plugins(db, keyword)
    return ok(data=[PluginOut.model_validate(p).model_dump() for p in rows])


@plugins_router.get("/installed")
async def list_installed_plugins(db: DbDep, _: CurrentUser):
    """精简列表：只返回 install_status=installed 的插件，供「应用主机装 App」下拉选择。"""
    from sqlalchemy import select
    from app.models.deployment import Plugin

    rows = (await db.execute(
        select(Plugin).where(Plugin.install_status == "installed").order_by(Plugin.name)
    )).scalars().all()
    return ok(data=[
        {"id": p.id, "name": p.name, "plugin_type": p.plugin_type,
         "source": p.source, "version": p.version or "", "config": p.config or {}}
        for p in rows
    ])


@plugins_router.post("", dependencies=[Depends(require_perm("plugin:create"))])
async def create_plugin(req: PluginCreate, db: DbDep, user: CurrentUser):
    p = await plugin_service.create_plugin(db, req, created_by=user.username)
    return ok(data=PluginOut.model_validate(p).model_dump())


@plugins_router.put("/{pid}", dependencies=[Depends(require_perm("plugin:install"))])
async def update_plugin(pid: int, req: PluginUpdate, db: DbDep):
    p = await plugin_service.update_plugin(db, pid, req)
    return ok(data=PluginOut.model_validate(p).model_dump())


@plugins_router.post("/{pid}/install", dependencies=[Depends(require_perm("plugin:install"))])
async def install_plugin(pid: int, db: DbDep, _: CurrentUser):
    p = await plugin_service.install_plugin(db, pid)
    return ok(data=PluginOut.model_validate(p).model_dump())


@plugins_router.delete("/{pid}", dependencies=[Depends(require_perm("plugin:delete"))])
async def delete_plugin(pid: int, db: DbDep):
    await plugin_service.delete_plugin(db, pid)
    return ok(message="已删除")


@plugins_router.post("/{pid}/refresh-image", dependencies=[Depends(require_perm("plugin:install"))])
async def refresh_image_version(pid: int, db: DbDep):
    """读取控制端 docker daemon 上 am_image_ref 镜像的 digest，写回 plugin.version。

    部署时 HostApp.version 记录的就是这个 digest；目标机 digest 与 plugin.version 不一致
    时，前端显示「更新」按钮。
    """
    import asyncio
    import json
    from sqlalchemy import select
    from app.models.deployment import Plugin

    p = (await db.execute(select(Plugin).where(Plugin.id == pid))).scalar_one_or_none()
    if not p:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("插件不存在")

    image_ref = (p.config or {}).get("am_image_ref", "ansible-manager:local")
    # docker image inspect --format '{{ index .RepoDigests 0 }}' 或走 digest
    proc = await asyncio.create_subprocess_exec(
        "docker", "image", "inspect", image_ref,
        "--format", "{{json .RepoDigests}}|{{.Id}}",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        return ok(data={"id": p.id, "version": p.version or "",
                        "error": (err or b"").decode(errors="replace")[:500]})

    text = out.decode().strip()
    # 形如 ["ansible-manager@sha256:abc..."]|sha256:def...
    # 本地 build 的镜像 RepoDigests 为空，用 .Id（image id）作为版本指纹
    digest_short = ""
    image_id = text.split("|", 1)[-1].strip() if "|" in text else text
    if image_id.startswith("sha256:"):
        digest_short = "sha256:" + image_id[7:19]
    if not digest_short and "|" in text:
        repo_digests_raw = text.split("|", 1)[0]
        try:
            repo_digests = json.loads(repo_digests_raw)
            if repo_digests:
                d = repo_digests[0].split("sha256:")[-1]
                digest_short = "sha256:" + d[:12]
        except Exception:
            pass
    if digest_short:
        p.version = digest_short
        await db.commit()
    return ok(data={"id": p.id, "version": p.version or "", "digest": digest_short})
