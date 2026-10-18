"""v1 路由汇总注册。"""
from fastapi import APIRouter

from app.api.v1 import app, auth, deployment, files, host, metric, plugin, system, task, terminal

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(system.users_router)
api_router.include_router(system.roles_router)
api_router.include_router(system.menus_router)
api_router.include_router(system.audit_router)
api_router.include_router(system.config_router)
api_router.include_router(host.projects_router)
api_router.include_router(host.credentials_router)
api_router.include_router(host.groups_router)
api_router.include_router(host.hosts_router)
api_router.include_router(task.playbooks_router)
api_router.include_router(task.tasks_router)
api_router.include_router(task.ws_router)
api_router.include_router(metric.metrics_router)
api_router.include_router(metric.dashboard_router)
api_router.include_router(deployment.deploy_router)
api_router.include_router(deployment.records_router)
api_router.include_router(plugin.plugins_router)
api_router.include_router(app.apps_router)
api_router.include_router(terminal.terminals_router)
api_router.include_router(files.files_router)
