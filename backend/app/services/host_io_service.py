"""主机导入导出：Excel 模板 / 导出 / 导入（逐行校验 + 失败明细）。

模板、导出、导入三处共用同一份列定义，导出的 xlsx 可以直接回灌导入。
"""
import io

from openpyxl import Workbook, load_workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationAppError
from app.models.host import Host
from app.schemas.host import HostCreate
from app.services import host_service

# 表头即导入契约
COLUMNS = ["主机名", "IP地址", "SSH端口", "主机类型", "登录凭据", "所属项目", "描述"]
_REQUIRED_COLUMNS = ["主机名", "IP地址", "登录凭据"]
_SAMPLE_ROW = ["web-01", "10.0.0.11", "22", "managed", "local-root", "", "示例行，请替换或删除"]

# 主机类型支持中文别名，降低手填成本
_TYPE_ALIASES = {
    "app": "app", "应用": "app", "应用主机": "app",
    "agent": "agent", "agent主机": "agent", "控制机": "agent",
    "managed": "managed", "被管": "managed", "被管主机": "managed",
}


def _xlsx_bytes(rows: list[list]) -> bytes:
    buf = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "主机清单"
    ws.append(COLUMNS)
    for r in rows:
        ws.append(r)
    wb.save(buf)
    return buf.getvalue()


def build_template() -> bytes:
    """导入模板：表头 + 示例行。"""
    return _xlsx_bytes([_SAMPLE_ROW])


async def export_hosts(db: AsyncSession, host_type: str | None = None) -> bytes:
    """导出当前作用域下的主机，列与模板一致，可直接回灌导入。"""
    rows, _ = await host_service.list_hosts(
        db, host_type=host_type, offset=0, limit=100000,
    )
    creds = {c.id: c.name for c in await host_service.list_credentials(db)}
    projects = {p.id: p.name for p in await host_service.list_projects(db)}
    data = [
        [h.hostname, h.ip, h.port, h.host_type, creds.get(h.credential_id, ""),
         projects.get(h.project_id, "") or "", h.description or ""]
        for h in rows
    ]
    return _xlsx_bytes(data)


def _field(row: dict, name: str) -> str:
    return (row.get(name) or "").strip()


def _reason(exc: Exception) -> str:
    return getattr(exc, "message", None) or str(exc) or exc.__class__.__name__


def _build_payload(row: dict, *, creds: dict, projects: dict, taken_ips: set) -> HostCreate:
    hostname = _field(row, "主机名")
    if not hostname:
        raise ValidationAppError("主机名为空")
    ip = _field(row, "IP地址")
    if not ip:
        raise ValidationAppError("IP地址为空")
    if ip in taken_ips:
        raise ValidationAppError(f"IP {ip} 已存在")

    raw_port = _field(row, "SSH端口")
    try:
        port = int(raw_port) if raw_port else 22
    except ValueError:
        raise ValidationAppError(f"SSH端口不是数字：{raw_port}")
    if not 1 <= port <= 65535:
        raise ValidationAppError(f"SSH端口超出范围：{port}")

    raw_type = _field(row, "主机类型") or "managed"
    host_type = _TYPE_ALIASES.get(raw_type.lower()) or _TYPE_ALIASES.get(raw_type)
    if not host_type:
        raise ValidationAppError(f"主机类型无法识别：{raw_type}（可选 app/agent/managed）")

    cred_name = _field(row, "登录凭据")
    if not cred_name:
        raise ValidationAppError("登录凭据为空")
    if cred_name not in creds:
        raise ValidationAppError(f"凭据不存在：{cred_name}")

    proj_name = _field(row, "所属项目")
    if proj_name and proj_name not in projects:
        raise ValidationAppError(f"项目不存在：{proj_name}")

    return HostCreate(
        hostname=hostname, ip=ip, port=port, host_type=host_type,
        credential_id=creds[cred_name],
        project_id=projects.get(proj_name) if proj_name else None,
        description=_field(row, "描述"),
    )


def _read_xlsx_rows(content: bytes) -> list[dict]:
    """把 xlsx 内容转成 [{列名: 值}] 字典列表（第 1 行为表头）。"""
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception:
        raise ValidationAppError("文件必须是 Excel（.xlsx）格式")
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    return [
        {headers[i]: ("" if v is None else str(v)) for i, v in enumerate(row)}
        for row in rows[1:]
    ]


async def import_hosts(db: AsyncSession, content: bytes) -> dict:
    """逐行导入；单行失败只记录明细，不阻断其余行。"""
    row_dicts = _read_xlsx_rows(content)
    if not row_dicts:
        raise ValidationAppError("Excel 无数据行，请先下载导入模板")
    fieldnames = list(row_dicts[0].keys()) if row_dicts else []
    missing = [c for c in _REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        raise ValidationAppError("表头缺少列：" + "、".join(missing) + "，请先下载导入模板")

    creds = {c.name: c.id for c in await host_service.list_credentials(db)}
    projects = {p.name: p.id for p in await host_service.list_projects(db)}
    taken_ips = set((await db.execute(select(Host.ip))).scalars().all())

    errors: list[dict] = []
    success = 0
    total = 0
    for line, row in enumerate(row_dicts, start=2):  # 第 1 行是表头
        hostname = _field(row, "主机名")
        ip = _field(row, "IP地址")
        if not hostname and not ip:
            continue  # 跳过空行
        total += 1
        try:
            payload = _build_payload(row, creds=creds, projects=projects, taken_ips=taken_ips)
            await host_service.create_host(db, payload)
            taken_ips.add(payload.ip)
            success += 1
        except Exception as exc:
            # create_host 内部会提交，失败行需要回滚以便继续处理后续行
            errors.append({"line": line, "hostname": hostname, "message": _reason(exc)})

    return {"total": total, "success": success, "failed": len(errors), "errors": errors}
