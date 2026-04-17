"""Integration tests for the sliding-window rate limiter.

Validates what mocks can't: the Redis sorted-set pipeline actually enforces
the per-key limit, independent API keys have independent windows, and the
limiter fails open when Redis is unreachable (instead of bringing the
service down).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import httpx
import pytest

from app.core.security import encrypt_value, hash_password
from app.domains.apis.models import APIAuthType, APIStatus, ExternalAPI
from app.domains.clients.models import Client, ClientStatus
from app.domains.keys.service import create_api_key
from app.domains.permissions.models import Permission

if TYPE_CHECKING:
    from httpx import AsyncClient
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def _seed_active_client(db: AsyncSession, email: str) -> Client:
    c = Client(
        name=email.split("@")[0],
        email=email,
        password_hash=hash_password("hunter2"),
        status=ClientStatus.ACTIVE,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _seed_api(db: AsyncSession) -> ExternalAPI:
    api = ExternalAPI(
        name="Stripe",
        base_url="https://api.stripe.test",
        master_key_encrypted=encrypt_value("sk_test"),
        auth_type=APIAuthType.API_KEY,
        status=APIStatus.ACTIVE,
    )
    db.add(api)
    await db.commit()
    await db.refresh(api)
    return api


async def _issue_key_with_limit(db: AsyncSession, email: str, rate_limit: int) -> str:
    key, plaintext = await create_api_key(db, email, "Prod")
    key.rate_limit = rate_limit
    await db.commit()
    return plaintext


def _inject_upstream(handler: Callable[[httpx.Request], httpx.Response]) -> None:
    from app.domains.proxy.router import get_http_client
    from app.main import app

    async def override():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            yield c

    app.dependency_overrides[get_http_client] = override


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={})


async def test_requests_under_limit_all_succeed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_active_client(db_session, "acme@example.com")
    api = await _seed_api(db_session)
    db_session.add(Permission(client_id=acme.id, api_id=api.id))
    await db_session.commit()
    plaintext = await _issue_key_with_limit(db_session, acme.email, rate_limit=5)

    _inject_upstream(_ok)

    for _ in range(5):
        resp = await client.get(
            f"/proxy/{api.id}/v1/ping", headers={"X-Bridge-Key": plaintext}
        )
        assert resp.status_code == 200


async def test_exceeding_limit_returns_429(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_active_client(db_session, "acme@example.com")
    api = await _seed_api(db_session)
    db_session.add(Permission(client_id=acme.id, api_id=api.id))
    await db_session.commit()
    plaintext = await _issue_key_with_limit(db_session, acme.email, rate_limit=2)

    _inject_upstream(_ok)

    first = await client.get(
        f"/proxy/{api.id}/v1/ping", headers={"X-Bridge-Key": plaintext}
    )
    second = await client.get(
        f"/proxy/{api.id}/v1/ping", headers={"X-Bridge-Key": plaintext}
    )
    third = await client.get(
        f"/proxy/{api.id}/v1/ping", headers={"X-Bridge-Key": plaintext}
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


async def test_rate_limit_is_scoped_per_key(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_active_client(db_session, "acme@example.com")
    other = await _seed_active_client(db_session, "other@example.com")
    api = await _seed_api(db_session)
    db_session.add_all(
        [
            Permission(client_id=acme.id, api_id=api.id),
            Permission(client_id=other.id, api_id=api.id),
        ]
    )
    await db_session.commit()

    acme_key = await _issue_key_with_limit(db_session, acme.email, rate_limit=1)
    other_key = await _issue_key_with_limit(db_session, other.email, rate_limit=1)

    _inject_upstream(_ok)

    # Exhaust acme's window
    assert (
        await client.get(f"/proxy/{api.id}/v1/ping", headers={"X-Bridge-Key": acme_key})
    ).status_code == 200
    assert (
        await client.get(f"/proxy/{api.id}/v1/ping", headers={"X-Bridge-Key": acme_key})
    ).status_code == 429
    # Other's window is untouched
    assert (
        await client.get(
            f"/proxy/{api.id}/v1/ping", headers={"X-Bridge-Key": other_key}
        )
    ).status_code == 200


async def test_rate_limit_counter_persists_in_redis(
    client: AsyncClient,
    db_session: AsyncSession,
    redis_client_integration: Redis,
) -> None:
    acme = await _seed_active_client(db_session, "acme@example.com")
    api = await _seed_api(db_session)
    db_session.add(Permission(client_id=acme.id, api_id=api.id))
    await db_session.commit()
    key_obj, plaintext = await create_api_key(db_session, acme.email, "Prod")

    _inject_upstream(_ok)

    await client.get(f"/proxy/{api.id}/v1/ping", headers={"X-Bridge-Key": plaintext})
    await client.get(f"/proxy/{api.id}/v1/ping", headers={"X-Bridge-Key": plaintext})

    count = await redis_client_integration.zcard(f"rate_limit:{key_obj.id}")
    assert count == 2


async def test_fails_open_when_redis_is_unreachable(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """If Redis is dead, requests still succeed — service must not go down."""
    import redis.asyncio as aioredis

    from app.core.redis_client import get_redis
    from app.main import app

    acme = await _seed_active_client(db_session, "acme@example.com")
    api = await _seed_api(db_session)
    db_session.add(Permission(client_id=acme.id, api_id=api.id))
    await db_session.commit()
    plaintext = await _issue_key_with_limit(db_session, acme.email, rate_limit=1)

    # Point Redis at a closed port — simulates an outage
    broken = aioredis.from_url(
        "redis://localhost:1/0", socket_connect_timeout=0.1, decode_responses=False
    )

    async def override_redis():
        yield broken

    app.dependency_overrides[get_redis] = override_redis
    _inject_upstream(_ok)

    try:
        for _ in range(3):
            response = await client.get(
                f"/proxy/{api.id}/v1/ping", headers={"X-Bridge-Key": plaintext}
            )
            assert response.status_code == 200  # fail-open, not 429 or 500
    finally:
        await broken.aclose()
