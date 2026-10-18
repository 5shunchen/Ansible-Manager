"""App 安装服务：在应用主机上以插件包（collection/role）作为 ansible role 跑一遍。

链路：
  install_app → 合成 playbook_content（include_role）→ task_service.create_task(task_type='app_install')
             → upsert HostApp(status=installing, last_task_id=...)
  task_worker 终态 → on_task_finished → 回写 HostApp.status
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.logging import get_logger
from app.core.time import now_cn
from app.models.deployment import HostApp, Plugin
from app.models.host import Host
from app.models.task import Task

logger = get_logger(__name__)


def _role_call_name(plugin: Plugin) -> str:
    """插件 source → include_role.name。

    - collection: `namespace.name` 直接可用（collection 内默认 role 与 collection 同名）
    - role: source 可能是 galaxy 名（`owner.role`）或本地路径 basename；
      roles_path 已注入 ansible.cfg，这里取最后一段（`owner.role` → `role`）。
    """
    src = (plugin.source or "").strip()
    if plugin.plugin_type == "collection":
        return src
    return src.split(".")[-1]


def _render_playbook(plugin: Plugin, action: str, merged_vars: dict[str, Any]) -> str:
    """合成 site.yml：include_role 调用插件。

    action=install → tasks/main.yml（默认）
    action=uninstall → tasks/uninstall.yml（若不存在会失败，由任务日志暴露）
    """
    role_name = _role_call_name(plugin)
    tasks_from = "" if action == "install" else "\n      tasks_from: uninstall"
    vars_block = ""
    if merged_vars:
        vars_block = "  vars:\n"
        for k, v in merged_vars.items():
            vars_block += f"    {k}: {json.dumps(v, ensure_ascii=False)}\n"

    action_zh = "安装" if action == "install" else "卸载"
    # name 必须 quote：中文 + 冒号会让 YAML 误判为嵌套 mapping
    task_name = f"{action_zh} {plugin.name}（{plugin.plugin_type}: {role_name}）"
    # tasks_from 必须嵌在 include_role 下，缩进 8 空格
    tasks_from_line = "" if action == "install" else f"\n        tasks_from: uninstall"
    # 默认关 gather_facts：目标机可能是 CentOS7 自带 python3.6，不满足 ansible 2.17 的 facts 采集要求；
    # 安装 containerd/起容器这类任务只需要 command/shell/copy 模块，不需要 facts。
    return f"""- hosts: all
  gather_facts: false
{vars_block}  tasks:
    - name: "{task_name}"
      ansible.builtin.include_role:
        name: {role_name}{tasks_from_line}
"""


async def _get_plugin(db: AsyncSession, plugin_id: int) -> Plugin:
    p = await db.get(Plugin, plugin_id)
    if not p:
        raise NotFoundError("插件不存在")
    if p.install_status != "installed":
        raise ValidationAppError(f"插件「{p.name}」尚未安装（当前：{p.install_status}）")
    return p


async def _get_app_host(db: AsyncSession, host_id: int) -> Host:
    h = await db.get(Host, host_id)
    if not h:
        raise NotFoundError("主机不存在")
    if h.host_type != "app":
        raise ValidationAppError("仅应用主机可安装 App")
    return h


async def install_app(
    db: AsyncSession,
    host_id: int,
    plugin_id: int,
    extra_vars: Optional[dict[str, Any]],
    username: str,
) -> HostApp:
    host = await _get_app_host(db, host_id)
    plugin = await _get_plugin(db, plugin_id)

    # 已存在的 HostApp 记录：若上一次任务还在跑则拒绝
    existing = (await db.execute(
        select(HostApp).where(HostApp.host_id == host_id, HostApp.plugin_id == plugin_id)
    )).scalar_one_or_none()
    if existing and existing.status in ("installing", "uninstalling"):
        raise ValidationAppError(f"「{plugin.name}」正在{existing.status}中，请等待当前任务结束")

    merged_vars: dict[str, Any] = dict(plugin.config or {})
    merged_vars.update(extra_vars or {})

    playbook_content = _render_playbook(plugin, "install", merged_vars)

    from app.services import task_service

    task = await task_service.create_task(
        db, None, triggered_by=username,
        task_type="app_install",
        name=f"[App安装] {plugin.name} → {host.hostname}",
        host_ids=[host_id],
        playbook_content=playbook_content,
        extra_vars=merged_vars,
    )

    if existing is None:
        existing = HostApp(host_id=host_id, plugin_id=plugin_id)
        db.add(existing)
    existing.status = "installing"
    existing.version = plugin.version or ""
    existing.last_task_id = task.id
    existing.extra_vars = merged_vars
    existing.uninstalled_at = None
    await db.commit()
    await db.refresh(existing)
    return existing


async def uninstall_app(db: AsyncSession, host_id: int, plugin_id: int, username: str) -> HostApp:
    host = await _get_app_host(db, host_id)
    plugin = await _get_plugin(db, plugin_id)

    existing = (await db.execute(
        select(HostApp).where(HostApp.host_id == host_id, HostApp.plugin_id == plugin_id)
    )).scalar_one_or_none()
    if not existing:
        raise NotFoundError("该主机上未安装此 App")
    if existing.status in ("installing", "uninstalling"):
        raise ValidationAppError(f"「{plugin.name}」正在{existing.status}中，无法卸载")

    # 卸载时也重新合并 plugin.config（可能已更新，比如 ansible_python_interpreter），
    # existing.extra_vars 里的用户自定义变量覆盖默认值
    merged_vars: dict[str, Any] = dict(plugin.config or {})
    merged_vars.update(existing.extra_vars or {})

    playbook_content = _render_playbook(plugin, "uninstall", merged_vars)

    from app.services import task_service

    task = await task_service.create_task(
        db, None, triggered_by=username,
        task_type="app_uninstall",
        name=f"[App卸载] {plugin.name} → {host.hostname}",
        host_ids=[host_id],
        playbook_content=playbook_content,
        extra_vars=merged_vars,
    )

    existing.status = "uninstalling"
    existing.last_task_id = task.id
    await db.commit()
    await db.refresh(existing)
    return existing


async def list_host_apps(db: AsyncSession, host_id: int) -> list[dict[str, Any]]:
    """返回 join plugin 的 HostApp 列表（前端展示用）。"""
    rows = (await db.execute(
        select(HostApp, Plugin)
        .join(Plugin, Plugin.id == HostApp.plugin_id)
        .where(HostApp.host_id == host_id)
        .order_by(HostApp.id.desc())
    )).all()
    out: list[dict[str, Any]] = []
    for ha, p in rows:
        out.append({
            "id": ha.id,
            "host_id": ha.host_id,
            "plugin_id": ha.plugin_id,
            "plugin_name": p.name,
            "plugin_type": p.plugin_type,
            "plugin_source": p.source,
            "status": ha.status,
            "version": ha.version,
            "last_task_id": ha.last_task_id,
            "installed_at": ha.installed_at.isoformat() if ha.installed_at else None,
            "uninstalled_at": ha.uninstalled_at.isoformat() if ha.uninstalled_at else None,
            "extra_vars": ha.extra_vars,
            "created_at": ha.created_at.isoformat() if ha.created_at else None,
        })
    return out


async def on_task_finished(db: AsyncSession, task: Task) -> None:
    """task_worker 终态回调：按 task_type 回写 HostApp。"""
    if task.task_type == "app_install":
        # inventory.host_ids[0] 是目标主机；last_task_id 关联 HostApp
        ha = (await db.execute(
            select(HostApp).where(HostApp.last_task_id == task.id)
        )).scalar_one_or_none()
        if not ha:
            return
        if task.status == "success":
            ha.status = "installed"
            ha.installed_at = now_cn()
        elif task.status in ("failed", "timeout"):
            ha.status = "failed"
        elif task.status == "canceled":
            ha.status = "unknown"
        await db.commit()
    elif task.task_type == "app_uninstall":
        ha = (await db.execute(
            select(HostApp).where(HostApp.last_task_id == task.id)
        )).scalar_one_or_none()
        if not ha:
            return
        if task.status == "success":
            ha.status = "uninstalled"
            ha.uninstalled_at = now_cn()
        elif task.status in ("failed", "timeout"):
            ha.status = "installed"  # 卸载失败 → 仍视为已装
        await db.commit()
