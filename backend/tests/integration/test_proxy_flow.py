"""Integration tests for the proxy dispatch pipeline.

Validates what mocks can't: full pre-flight (key → account → API → permission)
resolves against real Postgres, upstream request is built with the decrypted
master key injected and the bridge key stripped, and the proxy records a
metric plus a log after the round-trip. The upstream server is stubbed via
``httpx.MockTransport``; everything else is real.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import httpx
import pytest

from app.core.security import encrypt_value
from app.domains.accounts.models import AccountStatus
from app.domains.apis.models import APIAuthType, APIStatus, ExternalAPI
from app.domains.keys.models import APIKeyStatus
from app.domains.keys.service import create_api_key
from app.domains.logs.service import COLLECTION
from app.domains.metrics.models import RequestMetric
from app.domains.permissions.models import Permission

from ._seed import seed_account

if TYPE_CHECKING:
    from httpx import AsyncClient
    from motor.motor_asyncio import AsyncIOMotorDatabase
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


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


async def _setup(db: AsyncSession, **api_kwargs):
    """Account ativa + API + permissão + chave (vinculada à API)."""
    account, _ = await seed_account(db)
    api = await _seed_api(db, **api_kwargs)
    db.add(Permission(account_id=account.id, api_id=api.id))
    await db.commit()
    _, plaintext = await create_api_key(db, account.id, "Prod", api_id=api.id)
    return account, api, plaintext


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
    account, api, plaintext = await _setup(db_session)

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
    assert response.headers["x-correlation-id"]
    assert str(calls[0].url) == "https://api.stripe.test/v1/charges"

    from sqlalchemy import select

    rows = (await db_session.execute(select(RequestMetric))).scalars().all()
    assert len(rows) == 1
    assert rows[0].status_code == 200
    assert rows[0].account_id == account.id

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
    account, api, plaintext = await _setup(db_session)
    from sqlalchemy import select

    from app.domains.keys.models import APIKey

    key = (
        await db_session.execute(select(APIKey).where(APIKey.account_id == account.id))
    ).scalar_one()
    key.status = APIKeyStatus.REVOKED.value
    await db_session.commit()

    response = await client.get(
        f"/proxy/{api.id}/v1/anything", headers={"X-Bridge-Key": plaintext}
    )
    assert response.status_code == 401


async def test_inactive_account_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    account, api, plaintext = await _setup(db_session)
    account.status = AccountStatus.BLOCKED
    await db_session.commit()

    response = await client.get(
        f"/proxy/{api.id}/v1/anything", headers={"X-Bridge-Key": plaintext}
    )
    assert response.status_code == 403


async def test_no_permission_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # cria chave com permissão, depois remove a permissão
    account, api, plaintext = await _setup(db_session)
    from sqlalchemy import delete

    await db_session.execute(
        delete(Permission).where(Permission.account_id == account.id)
    )
    await db_session.commit()

    response = await client.get(
        f"/proxy/{api.id}/v1/anything", headers={"X-Bridge-Key": plaintext}
    )
    assert response.status_code == 403


async def test_upstream_5xx_is_returned_as_502(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    account, api, plaintext = await _setup(db_session)

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
    account, api, plaintext = await _setup(
        db_session, master_plain="sk_live_master", auth_type=APIAuthType.API_KEY
    )
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
    account, api, plaintext = await _setup(
        db_session, master_plain="ghp_token", auth_type=APIAuthType.BEARER
    )
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
    account, api, plaintext = await _setup(db_session)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    _inject_upstream(handler)
    await client.get(f"/proxy/{api.id}/v1/ping", headers={"X-Bridge-Key": plaintext})
    assert "x-bridge-key" not in {k.lower() for k in seen[0].headers.keys()}
