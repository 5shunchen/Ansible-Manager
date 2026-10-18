"""文件管理路由：SFTP 浏览/上传/下载/重命名/删除。"""
import asyncio
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, UploadFile, WebSocket
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DbDep, TransportFactoryDep, resolve_target, require_perm
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.response import ok

files_router = APIRouter(prefix="/hosts/{host_id}/files", tags=["files"])


def _normalize(path: str) -> str:
    """SFTP 路径规范：空 → /，禁止 .. 穿越。"""
    if not path:
        return "/"
    p = PurePosixPath(path)
    if ".." in p.parts:
        raise ValidationAppError("非法路径")
    return "/" + str(p).lstrip("/")


async def _sftp_session(factory, target):
    transport = factory(target)
    await transport.connect()
    sftp = await transport.sftp()
    return transport, sftp


@files_router.get("", dependencies=[Depends(require_perm("file:read"))])
async def list_files(host_id: int, db: DbDep, factory: TransportFactoryDep,
                     _: CurrentUser, path: str = "/"):
    """目录列表。"""
    path = _normalize(path)
    target = await resolve_target(host_id, db)
    transport, sftp = await _sftp_session(factory, target)
    try:
        entries = []
        for attr in await sftp.readdir(path):
            name = attr.filename
            if name in (".", ".."):
                continue
            full = str(PurePosixPath(path) / name)
            longname = getattr(attr, "longname", "") or ""
            entries.append({
                "name": name, "path": full,
                "is_dir": longname.startswith("d"),
                "size": getattr(attr.attrs, "size", None) or 0,
                "mtime": getattr(attr.attrs, "mtime", None) or 0,
            })
        return ok(data={"path": path, "entries": entries})
    finally:
        await transport.close()


@files_router.post("/upload", dependencies=[Depends(require_perm("file:write"))])
async def upload_file(host_id: int, db: DbDep, factory: TransportFactoryDep,
                      _: CurrentUser, file: UploadFile, path: str = "/tmp"):
    path = _normalize(path)
    dest = str(PurePosixPath(path) / file.filename)
    target = await resolve_target(host_id, db)
    transport, sftp = await _sftp_session(factory, target)
    try:
        content = await file.read()
        async with sftp.open(dest, "wb") as f:
            await f.write(content)
        return ok(data={"path": dest, "size": len(content)})
    finally:
        await transport.close()


@files_router.get("/download", dependencies=[Depends(require_perm("file:read"))])
async def download_file(host_id: int, db: DbDep, factory: TransportFactoryDep,
                        _: CurrentUser, path: str):
    path = _normalize(path)
    target = await resolve_target(host_id, db)
    transport, sftp = await _sftp_session(factory, target)
    try:
        try:
            f = await sftp.open(path, "rb")
        except Exception as e:  # noqa: BLE001
            raise NotFoundError(f"文件不存在或不可读: {e}")
        stat = await f.stat()
        size = stat.attrs.get("size", 0) if isinstance(stat.attrs, dict) else 0

        async def stream():
            try:
                offset = 0
                while True:
                    chunk = await f.read(offset, 1024 * 256)
                    if not chunk:
                        break
                    offset += len(chunk)
                    yield chunk
            finally:
                f.close()
                await transport.close()

        name = PurePosixPath(path).name
        return StreamingResponse(
            stream(), media_type="application/octet-stream",
            headers={"content-disposition": f'attachment; filename="{name}"', "content-length": str(size)},
        )
    except NotFoundError:
        await transport.close()
        raise


@files_router.post("/mkdir", dependencies=[Depends(require_perm("file:write"))])
async def mkdir(host_id: int, db: DbDep, factory: TransportFactoryDep,
                _: CurrentUser, path: str, name: str):
    target = await resolve_target(host_id, db)
    transport, sftp = await _sftp_session(factory, target)
    try:
        full = str(PurePosixPath(_normalize(path)) / name)
        await sftp.mkdir(full)
        return ok(data={"path": full})
    finally:
        await transport.close()


@files_router.post("/rename", dependencies=[Depends(require_perm("file:write"))])
async def rename(host_id: int, db: DbDep, factory: TransportFactoryDep,
                 _: CurrentUser, path: str, new_path: str):
    target = await resolve_target(host_id, db)
    transport, sftp = await _sftp_session(factory, target)
    try:
        await sftp.rename(_normalize(path), _normalize(new_path))
        return ok(data={"path": new_path})
    finally:
        await transport.close()


@files_router.delete("", dependencies=[Depends(require_perm("file:delete"))])
async def delete_file(host_id: int, db: DbDep, factory: TransportFactoryDep,
                      _: CurrentUser, path: str):
    path = _normalize(path)
    target = await resolve_target(host_id, db)
    transport, sftp = await _sftp_session(factory, target)
    try:
        try:
            await sftp.remove(path)
        except Exception:  # 目录则 rmdir
            await sftp.rmdir(path)
        return ok(message="已删除")
    finally:
        await transport.close()
