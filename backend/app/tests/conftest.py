"""pytest 公共夹具：sqlite 内存库 + FastAPI 测试客户端。

worker（task_worker/collector）内部用 AsyncSessionLocal 自建会话，
因此必须把全局 session factory monkeypatch 到测试库（StaticPool 共享同一内存连接）。
"""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import *  # noqa: F401,F403


@pytest_asyncio.fixture
async def db_session(monkeypatch):
    """每个测试独立内存库，并接管全局 AsyncSessionLocal。"""
    import app.db.session as db_session_mod

    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    monkeypatch.setattr(db_session_mod, "AsyncSessionLocal", maker)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    """API 客户端：get_db 替换为测试库，seed 数据注入。"""
    from app.api import deps
    from app.db.init_db import init_db
    from app.main import create_app

    async def override_get_db():
        yield db_session

    app = create_app()
    app.dependency_overrides[deps.get_db] = override_get_db

    await init_db(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_headers(client):
    """admin 登录后的请求头。"""
    resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}
