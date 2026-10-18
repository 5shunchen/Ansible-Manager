FROM python:3.11-slim

RUN sed -i 's@deb.debian.org@mirrors.aliyun.com@g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true
RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-client sshpass curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
        fastapi "uvicorn[standard]" "sqlalchemy[asyncio]" aiomysql aiosqlite alembic \
        pydantic pydantic-settings "python-jose[cryptography]" "passlib[bcrypt]" \
        asyncssh ansible-runner ansible-core apscheduler jinja2 cryptography \
        python-multipart structlog bcrypt

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
