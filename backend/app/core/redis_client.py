from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Optional

import redis.asyncio as redis_asyncio

from app.core.config import settings

_redis: Optional[redis_asyncio.Redis] = None


def _get_client() -> redis_asyncio.Redis:
    global _redis
    if _redis is None:
        _redis = redis_asyncio.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def get_redis() -> AsyncGenerator[Optional[redis_asyncio.Redis], None]:
    """FastAPI dependency que fornece o cliente Redis.

    Yields None se a URL não estiver configurada, permitindo que o código
    downstream trate redis=None como "rate limiting desabilitado".
    """
    try:
        yield _get_client()
    except Exception:
        yield None
