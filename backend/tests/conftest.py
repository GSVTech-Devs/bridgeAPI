from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.main import app


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
async def client(mock_db: AsyncMock) -> AsyncClient:
    async def override_db():
        yield mock_db

    async def override_redis():
        yield None  # desabilita rate limiting nos testes não-rate-limit

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
