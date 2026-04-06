from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

_client: Optional[AsyncIOMotorClient] = None


def _get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongo_url)
    return _client


async def get_mongo_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """FastAPI dependency que fornece o banco MongoDB."""
    yield _get_client()[settings.mongo_db]
