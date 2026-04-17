"""Integration tests for the proxy dispatch pipeline.

Validates what mocks can't: full pre-flight (key → client → API → permission)
resolves against real Postgres, upstream request is built with the decrypted
master key injected and the bridge key stripped, and the proxy records a
metric plus a log after the round-trip. The upstream server is stubbed via
``httpx.MockTransport``; everything else is real.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import httpx
import pytest

from app.core.security import encrypt_value, hash_password
from app.domains.apis.models import APIAuthType, APIStatus, ExternalAPI
from app.domains.clients.models import Client, ClientStatus
from app.domains.keys.models import APIKeyStatus
from app.domains.keys.service import create_api_key
from app.domains.logs.service import COLLECTION
from app.domains.metrics.models import RequestMetric
from app.domains.permissions.models import Permission

if TYPE_CHECKING:
    from httpx import AsyncClient
    from motor.motor_asyncio import AsyncIOMotorDatabase
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def _seed_active_client(
    db: AsyncSession, email: str = "acme@example.com"
) -> Client:
    c = Client(
        name="Acme",
        email=email,
        password_hash=hash_password("hunter2"),
        status=ClientStatus.ACTIVE,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _seed_api(
    db: AsyncSession,
    master_plain: str = "sk_live_master",
    auth_type: APIAuthType = APIAuthType.API_KEY,
    status: APIStatus = APIStatus.ACTIVE,
) -> ExternalAPI:
    api = ExternalAPI(
        name="Stripe",
        base_url="https://api.stripe.test",
        master_key_encrypted=encrypt_value(master_plain),
        auth_type=auth_type,
        status=status,
    )
    db.add(api)
    await db.commit()
    await db.refresh(api)
    return api


async def _grant(db: AsyncSession, client_id, api_id) -> None:
    db.add(Permission(client_id=client_id, api_id=api_id))
    await db.commit()


def _inject_upstream(handler: Callable[[httpx.Request], httpx.Response]) -> None:
    from app.domains.proxy.router import get_http_client
    from app.main import app

    async def override():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            yield c

    app.dependency_overrides[get_http_client] = override


async def test_successful_proxy_forwards_and_records_metric_and_log(
    client: AsyncClient,
    db_session: AsyncSession,
    mongo_db_integration: AsyncIOMotorDatabase,
) -> None:
    acme = await _seed_active_client(db_session)
    api = await _seed_api(db_session)
    await _grant(db_session, acme.id, api.id)
    _, plaintext = await create_api_key(db_session, acme.email, "Prod")

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200, json={"charge": "ch_1"}, headers={"X-Upstream": "yes"}
        )

    _inject_upstream(handler)

    response = await client.post(
        f"/proxy/{api.id}/v1/charges",
        headers={"X-Bridge-Key": plaintext, "X-Trace": "abc"},
        json={"amount": 100},
    )

    assert response.status_code == 200
    assert response.json() == {"charge": "ch_1"}
    assert response.headers["x-upstream"] == "yes"
    assert response.headers["x-correlation-id"]
    # Upstream URL assembled from base_url + path
    assert str(calls[0].url) == "https://api.stripe.test/v1/charges"

    # Metric persisted against real Postgres
    from sqlalchemy import select

    rows = (await db_session.execute(select(RequestMetric))).scalars().all()
    assert len(rows) == 1
    assert rows[0].status_code == 200
    assert rows[0].client_id == acme.id

    # Log persisted in Mongo
    logs = await mongo_db_integration[COLLECTION].find({}).to_list(length=10)
    assert len(logs) == 1
    assert logs[0]["path"] == "v1/charges"


async def test_missing_bridge_key_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    api = await _seed_api(db_session)

    response = await client.get(f"/proxy/{api.id}/v1/anything")

    assert response.status_code == 401


async def test_invalid_bridge_key_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    api = await _seed_api(db_session)

    response = await client.get(
        f"/proxy/{api.id}/v1/anything",
        headers={"X-Bridge-Key": "brg_deadbeef_not-a-real-key"},
    )

    assert response.status_code == 401


async def test_revoked_key_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_active_client(db_session)
    api = await _seed_api(db_session)
    await _grant(db_session, acme.id, api.id)
    key, plaintext = await create_api_key(db_session, acme.email, "Prod")
    key.status = APIKeyStatus.REVOKED.value
    await db_session.commit()

    response = await client.get(
        f"/proxy/{api.id}/v1/anything", headers={"X-Bridge-Key": plaintext}
    )

    assert response.status_code == 401


async def test_inactive_client_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_active_client(db_session)
    api = await _seed_api(db_session)
    await _grant(db_session, acme.id, api.id)
    _, plaintext = await create_api_key(db_session, acme.email, "Prod")

    acme.status = ClientStatus.PENDING
    await db_session.commit()

    response = await client.get(
        f"/proxy/{api.id}/v1/anything", headers={"X-Bridge-Key": plaintext}
    )

    assert response.status_code == 403


async def test_disabled_api_returns_503(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_active_client(db_session)
    api = await _seed_api(db_session, status=APIStatus.INACTIVE)
    await _grant(db_session, acme.id, api.id)
    _, plaintext = await create_api_key(db_session, acme.email, "Prod")

    response = await client.get(
        f"/proxy/{api.id}/v1/anything", headers={"X-Bridge-Key": plaintext}
    )

    assert response.status_code == 503


async def test_no_permission_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_active_client(db_session)
    api = await _seed_api(db_session)
    # No _grant call — permission missing
    _, plaintext = await create_api_key(db_session, acme.email, "Prod")

    response = await client.get(
        f"/proxy/{api.id}/v1/anything", headers={"X-Bridge-Key": plaintext}
    )

    assert response.status_code == 403


async def test_upstream_5xx_is_returned_as_502(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_active_client(db_session)
    api = await _seed_api(db_session)
    await _grant(db_session, acme.id, api.id)
    _, plaintext = await create_api_key(db_session, acme.email, "Prod")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream exploded")

    _inject_upstream(handler)

    response = await client.get(
        f"/proxy/{api.id}/v1/boom", headers={"X-Bridge-Key": plaintext}
    )

    assert response.status_code == 502


async def test_master_key_injected_as_api_key_header(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_active_client(db_session)
    api = await _seed_api(
        db_session, master_plain="sk_live_master", auth_type=APIAuthType.API_KEY
    )
    await _grant(db_session, acme.id, api.id)
    _, plaintext = await create_api_key(db_session, acme.email, "Prod")

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    _inject_upstream(handler)

    await client.get(f"/proxy/{api.id}/v1/ping", headers={"X-Bridge-Key": plaintext})

    assert seen[0].headers["x-api-key"] == "sk_live_master"


async def test_bearer_master_key_becomes_authorization_header(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_active_client(db_session)
    api = await _seed_api(
        db_session, master_plain="ghp_token", auth_type=APIAuthType.BEARER
    )
    await _grant(db_session, acme.id, api.id)
    _, plaintext = await create_api_key(db_session, acme.email, "Prod")

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    _inject_upstream(handler)

    await client.get(f"/proxy/{api.id}/v1/me", headers={"X-Bridge-Key": plaintext})

    assert seen[0].headers["authorization"] == "Bearer ghp_token"


async def test_bridge_key_is_never_forwarded_to_upstream(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_active_client(db_session)
    api = await _seed_api(db_session)
    await _grant(db_session, acme.id, api.id)
    _, plaintext = await create_api_key(db_session, acme.email, "Prod")

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    _inject_upstream(handler)

    await client.get(f"/proxy/{api.id}/v1/ping", headers={"X-Bridge-Key": plaintext})

    assert "x-bridge-key" not in {k.lower() for k in seen[0].headers.keys()}
