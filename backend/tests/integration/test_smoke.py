from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

if TYPE_CHECKING:
    from httpx import AsyncClient
    from motor.motor_asyncio import AsyncIOMotorDatabase
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_migrations_applied_and_tables_empty(
    db_session: AsyncSession,
) -> None:
    for table in ("clients", "users", "external_apis", "api_keys", "permissions"):
        result = await db_session.execute(text(f"SELECT COUNT(*) FROM {table}"))
        assert result.scalar() == 0, f"expected empty table {table}"


async def test_redis_is_reachable(redis_client_integration: Redis) -> None:
    assert await redis_client_integration.ping() is True


async def test_mongo_is_reachable(
    mongo_db_integration: AsyncIOMotorDatabase,
) -> None:
    pong = await mongo_db_integration.command("ping")
    assert pong.get("ok") == 1.0


async def test_health_endpoint_wired_with_real_dependencies(
    client: AsyncClient,
) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
