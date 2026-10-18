# 单镜像方案：前端构建产物 + 后端同端口（3000）对外
# 构建（仓库根目录）：docker build -t ansible-manager:latest .
#
# ---------- 阶段一：构建前端 ----------
FROM node:18-alpine AS frontend

WORKDIR /build
RUN npm config set registry https://registry.npmmirror.com
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 阶段二：运行时（后端 + 前端产物）----------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    TZ=Asia/Shanghai \
    APP_PORT=3000 \
    STATIC_DIR=/app/static

# 部署功能依赖：ssh 客户端（ansible 连接受管主机）、sshpass（密码认证）、curl（健康检查）
RUN sed -i 's@deb.debian.org@mirrors.aliyun.com@g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        openssh-client sshpass curl ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/app ./app
# 依赖的唯一来源是 pyproject.toml，避免在此重复列清单导致遗漏
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple .

# 前端产物挂到后端托管目录（与 STATIC_DIR 一致）
COPY --from=frontend /build/dist /app/static

RUN mkdir -p /app/data

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:3000/api/v1/healthz || exit 1

# 单进程约束：任务 worker 与调度器内嵌，禁止多副本
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT:-3000} --workers 1"]
