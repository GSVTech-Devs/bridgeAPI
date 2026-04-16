# RED → GREEN
# Testes para app/core/redis_client.py — lazy client + dependency generator.
import pytest
import redis.asyncio as redis_asyncio

from app.core import redis_client


@pytest.fixture(autouse=True)
def _reset_redis_global():
    redis_client._redis = None
    yield
    redis_client._redis = None


def test_get_client_returns_redis_instance() -> None:
    client = redis_client._get_client()
    assert isinstance(client, redis_asyncio.Redis)


def test_get_client_is_singleton() -> None:
    first = redis_client._get_client()
    second = redis_client._get_client()
    assert first is second


async def test_get_redis_yields_client() -> None:
    agen = redis_client.get_redis()
    client = await agen.__anext__()
    assert isinstance(client, redis_asyncio.Redis)
    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()


async def test_get_redis_yields_none_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise() -> None:
        raise RuntimeError("redis down")

    monkeypatch.setattr(redis_client, "_get_client", _raise)

    agen = redis_client.get_redis()
    value = await agen.__anext__()
    assert value is None
