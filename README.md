# ansible-manager

Ansible 主机管理运维平台：主机管理、SSH 定时资源监控、Playbook 批量执行、跨主机 containerd 镜像部署。

## 功能菜单

项目管理 / 应用主机 / Agent主机 / 主机管理（主机列表、Web终端、文件管理）/ 监控大屏 / Playbook管理 / 任务管理 / 系统配置 / 权限管理 / 插件工程 / 工程部署

## 架构

- **后端** `backend/`：FastAPI + SQLAlchemy(async) + ansible-runner + asyncssh + APScheduler，单进程内嵌任务 worker 与采集调度器
- **前端** `frontend/`：Vue3 + Element Plus + Pinia + ECharts + xterm.js，动态菜单与按钮级权限
- **部署** `deploy/`：docker-compose（MySQL + backend + frontend/nginx）

核心设计：

1. **监控采集**：APScheduler 10s tick 动态读 `sys_config` 采集间隔，派发 SSH 单次往返采集（`/proc/stat` 差分 CPU、meminfo、df、net/dev），失败重试 → 连续 3 次置 offline
2. **任务执行**：`pending → queued → running → success/failed/canceled/timeout` 状态机；ansible-runner 在线程池执行，事件回调桥接回 asyncio 落库 + WebSocket 实时日志；启动恢复、超时、取消
3. **containerd 部署**：部署工程（镜像/多主机/容器参数/健康检查）→ Jinja2 渲染 playbook（pull → rm → run → 健康检查 → block/rescue 回滚）→ 走统一任务管线
4. **工程化**：pydantic-settings 配置分层（.env 静态 / sys_config 热更新）、structlog 结构化日志 + request_id、统一错误码与响应包裹、RBAC 中间件、SSH/执行层 Protocol 抽象可 mock

## 快速开始（Docker）

```bash
cd deploy
docker compose up -d --build
# 前端 http://<host>/  初始账号 admin / admin123
```

## 本地开发

```bash
# 后端（Python ≥ 3.11）
cd backend
pip install -e ".[dev]"   # 或按 pyproject 安装依赖
cp .env.example .env
uvicorn app.main:app --reload --port 8000

# 前端（Node ≥ 18）
cd frontend
npm install
npm run dev   # http://localhost:5173，/api 代理到 8000
```

## 测试

```bash
cd backend
pytest        # 单测：采集解析纯函数 + API 集成（Fake SSH/Executor，无需真实主机）
```

## 数据库迁移

```bash
cd backend
alembic revision --autogenerate -m "msg"
alembic upgrade head
```
