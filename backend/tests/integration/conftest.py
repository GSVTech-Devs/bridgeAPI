from __future__ import annotations

import asyncio
import os
import socket
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncEngine

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://bridge:bridge@localhost:5433/bridgeapi_test",
)
TEST_MONGO_URL = os.environ.get(
    "TEST_MONGO_URL",
    "mongodb://bridge:bridge@localhost:27018/bridgelogs_test?authSource=admin",
)
TEST_MONGO_DB = os.environ.get("TEST_MONGO_DB", "bridgelogs_test")
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://:bridge@localhost:6380/1")

_DOMAIN_TABLES = (
    "request_metrics",
    "permissions",
    "api_keys",
    "endpoints",
    "external_apis",
    "clients",
    "users",
)


def _tcp_reachable(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port
    if port is None:
        return False
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip integration tests when Docker services are unreachable."""
    unreachable = [
        name
        for name, url in (
            ("postgres", TEST_DB_URL),
            ("mongo", TEST_MONGO_URL),
            ("redis", TEST_REDIS_URL),
        )
        if not _tcp_reachable(url)
    ]
    if not unreachable:
        return
    reason = f"docker services unreachable: {', '.join(unreachable)}"
    skip = pytest.mark.skip(reason=reason)
    integration_root = Path(__file__).resolve().parent
    for item in items:
        if integration_root in Path(str(item.fspath)).parents:
            item.add_marker(skip)


async def _ensure_test_database() -> None:
    import asyncpg

    parsed = urlparse(TEST_DB_URL.replace("postgresql+asyncpg", "postgresql"))
    test_db_name = parsed.path.lstrip("/")
    admin_dsn = parsed._replace(path="/postgres").geturl()

    conn = await asyncpg.connect(admin_dsn)
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", test_db_name
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{test_db_name}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def _setup_database() -> None:
    """Create test DB + run Alembic upgrade once per session.

    Runs synchronously (outside pytest-asyncio loops) so Alembic's internal
    ``asyncio.run`` doesn't collide with a running event loop, and so no
    pooled connection crosses event-loop boundaries.
    """
    from alembic.config import Config

    from alembic import command
    from app.core.config import settings

    asyncio.run(_ensure_test_database())

    settings.database_url = TEST_DB_URL  # env.py reads this
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture
async def test_engine(_setup_database: None) -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    test_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session
    async with factory() as cleanup:
        await cleanup.execute(
            text(
                "TRUNCATE TABLE "
                + ", ".join(_DOMAIN_TABLES)
                + " RESTART IDENTITY CASCADE"
            )
        )
        await cleanup.commit()


@pytest_asyncio.fixture
async def mongo_db_integration() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    from motor.motor_asyncio import AsyncIOMotorClient

    mc = AsyncIOMotorClient(TEST_MONGO_URL)
    db = mc[TEST_MONGO_DB]
    yield db
    for name in await db.list_collection_names():
        await db.drop_collection(name)
    mc.close()


@pytest_asyncio.fixture
async def redis_client_integration() -> AsyncGenerator[Redis, None]:
    import redis.asyncio as aioredis

    rc: Redis = aioredis.from_url(TEST_REDIS_URL, decode_responses=False)
    yield rc
    await rc.flushdb()
    await rc.aclose()


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    mongo_db_integration: AsyncIOMotorDatabase,
    redis_client_integration: Redis,
) -> AsyncGenerator[AsyncClient, None]:
    from app.core.database import get_db
    from app.core.mongo_client import get_mongo_db
    from app.core.redis_client import get_redis
    from app.main import app

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_mongo() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
        yield mongo_db_integration

    async def override_redis() -> AsyncGenerator[Redis, None]:
        yield redis_client_integration

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_mongo_db] = override_mongo
    app.dependency_overrides[get_redis] = override_redis
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
