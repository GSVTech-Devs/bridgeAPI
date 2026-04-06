# RED → GREEN
# Testes unitários para a lógica de rate limiting (sliding window com Redis).
# O cliente Redis é mockado com MagicMock + AsyncMock para isolar o comportamento
# sem necessidade de uma instância Redis real.
from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.proxy.service import RateLimitExceededError, check_rate_limit

# ---------------------------------------------------------------------------
# Helpers para construir mocks do pipeline Redis
# ---------------------------------------------------------------------------


def make_pipeline_mock(zcard_count: int = 0) -> MagicMock:
    """Retorna um mock de pipeline Redis com resultados configuráveis.

    execute() retorna [zremrange_count, zadd_result, zcard_count, expire_result].
    """
    pipe = MagicMock()
    pipe.execute = AsyncMock(return_value=[1, 1, zcard_count, True])
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=None)
    return pipe


def make_redis_mock(zcard_count: int = 0) -> MagicMock:
    redis = MagicMock()
    redis.pipeline.return_value = make_pipeline_mock(zcard_count)
    return redis


def make_redis_error_mock(error: Exception) -> MagicMock:
    """Redis que falha ao entrar no pipeline — simula conexão indisponível."""
    pipe = MagicMock()
    pipe.__aenter__ = AsyncMock(side_effect=error)
    pipe.__aexit__ = AsyncMock(return_value=None)
    redis = MagicMock()
    redis.pipeline.return_value = pipe
    return redis


# ---------------------------------------------------------------------------
# Casos dentro do limite
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_requests_within_limit_are_allowed() -> None:
    key_id = str(uuid.uuid4())
    redis = make_redis_mock(zcard_count=10)

    await check_rate_limit(key_id, rate_limit=60, redis=redis)

    # nenhuma exceção levantada


@pytest.mark.asyncio
async def test_request_exactly_at_limit_is_still_allowed() -> None:
    key_id = str(uuid.uuid4())
    redis = make_redis_mock(zcard_count=60)

    await check_rate_limit(key_id, rate_limit=60, redis=redis)

    # limite inclusive: 60/60 deve passar


@pytest.mark.asyncio
async def test_first_request_ever_is_allowed() -> None:
    key_id = str(uuid.uuid4())
    redis = make_redis_mock(zcard_count=1)  # só o request atual

    await check_rate_limit(key_id, rate_limit=60, redis=redis)


# ---------------------------------------------------------------------------
# Casos acima do limite
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_exceeding_limit_raises_error() -> None:
    key_id = str(uuid.uuid4())
    redis = make_redis_mock(zcard_count=61)

    with pytest.raises(RateLimitExceededError):
        await check_rate_limit(key_id, rate_limit=60, redis=redis)


@pytest.mark.asyncio
async def test_rate_limit_error_message_includes_counts() -> None:
    key_id = str(uuid.uuid4())
    redis = make_redis_mock(zcard_count=101)

    with pytest.raises(RateLimitExceededError, match="101"):
        await check_rate_limit(key_id, rate_limit=100, redis=redis)


# ---------------------------------------------------------------------------
# Algoritmo sliding window
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_uses_sorted_set_pipeline() -> None:
    key_id = str(uuid.uuid4())
    pipe = make_pipeline_mock(zcard_count=5)
    redis = MagicMock()
    redis.pipeline.return_value = pipe

    await check_rate_limit(key_id, rate_limit=60, redis=redis)

    pipe.zremrangebyscore.assert_called_once()
    pipe.zadd.assert_called_once()
    pipe.zcard.assert_called_once()
    pipe.expire.assert_called_once()


@pytest.mark.asyncio
async def test_rate_limit_redis_key_contains_key_id() -> None:
    key_id = str(uuid.uuid4())
    pipe = make_pipeline_mock(zcard_count=1)
    redis = MagicMock()
    redis.pipeline.return_value = pipe

    await check_rate_limit(key_id, rate_limit=60, redis=redis)

    redis_key_used = pipe.zremrangebyscore.call_args[0][0]
    assert key_id in redis_key_used


@pytest.mark.asyncio
async def test_rate_limit_window_is_60_seconds() -> None:
    key_id = str(uuid.uuid4())
    pipe = make_pipeline_mock(zcard_count=1)
    redis = MagicMock()
    redis.pipeline.return_value = pipe
    before = time.time()

    await check_rate_limit(key_id, rate_limit=60, redis=redis)

    _key, _min, window_end = pipe.zremrangebyscore.call_args[0]
    after = time.time()
    # window_end é o timestamp de corte (now - 60)
    assert before - 60 - 1 <= window_end <= after - 60 + 1


@pytest.mark.asyncio
async def test_rate_limit_resets_after_window() -> None:
    # Após expirar a janela, contador volta a 1 (só o request atual)
    key_id = str(uuid.uuid4())
    redis = make_redis_mock(zcard_count=1)

    await check_rate_limit(key_id, rate_limit=60, redis=redis)

    # zcard=1 → dentro do limite, sem exceção


@pytest.mark.asyncio
async def test_rate_limit_ttl_set_to_60_seconds() -> None:
    key_id = str(uuid.uuid4())
    pipe = make_pipeline_mock(zcard_count=1)
    redis = MagicMock()
    redis.pipeline.return_value = pipe

    await check_rate_limit(key_id, rate_limit=60, redis=redis)

    _key, ttl = pipe.expire.call_args[0]
    assert ttl == 60


# ---------------------------------------------------------------------------
# Isolamento por chave (não por cliente)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_is_per_key_not_per_client() -> None:
    key1_id = str(uuid.uuid4())
    key2_id = str(uuid.uuid4())

    pipe1 = make_pipeline_mock(zcard_count=55)
    pipe2 = make_pipeline_mock(zcard_count=55)
    redis1 = MagicMock()
    redis1.pipeline.return_value = pipe1
    redis2 = MagicMock()
    redis2.pipeline.return_value = pipe2

    await check_rate_limit(key1_id, rate_limit=60, redis=redis1)
    await check_rate_limit(key2_id, rate_limit=60, redis=redis2)

    key1_used = pipe1.zremrangebyscore.call_args[0][0]
    key2_used = pipe2.zremrangebyscore.call_args[0][0]
    assert key1_used != key2_used
    assert key1_id in key1_used
    assert key2_id in key2_used


@pytest.mark.asyncio
async def test_different_keys_have_independent_counters() -> None:
    # key1 no limite, key2 dentro → key1 bloqueada, key2 passa
    key1_id = str(uuid.uuid4())
    key2_id = str(uuid.uuid4())

    redis_over = make_redis_mock(zcard_count=61)
    redis_under = make_redis_mock(zcard_count=10)

    with pytest.raises(RateLimitExceededError):
        await check_rate_limit(key1_id, rate_limit=60, redis=redis_over)

    await check_rate_limit(key2_id, rate_limit=60, redis=redis_under)
    # key2 não levanta exceção


# ---------------------------------------------------------------------------
# Fallback quando Redis está indisponível (fail open)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_unavailable_falls_back_gracefully() -> None:
    key_id = str(uuid.uuid4())
    redis = make_redis_error_mock(ConnectionError("Redis unreachable"))

    # não deve levantar exceção — fail open para não derrubar o serviço
    await check_rate_limit(key_id, rate_limit=60, redis=redis)


@pytest.mark.asyncio
async def test_redis_timeout_falls_back_gracefully() -> None:
    key_id = str(uuid.uuid4())
    redis = make_redis_error_mock(TimeoutError("Redis timeout"))

    await check_rate_limit(key_id, rate_limit=60, redis=redis)


@pytest.mark.asyncio
async def test_redis_none_always_allows_request() -> None:
    # redis=None → sem verificação, sempre permite
    key_id = str(uuid.uuid4())

    await check_rate_limit(key_id, rate_limit=60, redis=None)

    # nenhuma exceção, nenhuma chamada Redis
