# Autosserviço de proxies do cliente, por API: /client/apis/{api_id}/proxies.
from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.domains.proxies import client_router
from app.domains.proxies.schemas import ProxyResponse
from app.main import app


@pytest.fixture
def account_id():
    return uuid.uuid4()


@pytest.fixture
def as_client_user(account_id):
    async def _identity():
        return MagicMock(account_id=account_id)

    app.dependency_overrides[client_router._require] = _identity
    yield account_id
    app.dependency_overrides.pop(client_router._require, None)


def make_proxy_response(account_id, **kw) -> ProxyResponse:
    base = dict(
        id=uuid.uuid4(), api_id=uuid.uuid4(), account_id=account_id, name="p1",
        ownership="client", type="datacenter", scheme="http", host="1.2.3.4",
        port=8080, username=None, has_password=False, rotation="sticky",
        status="active", priority=100,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    base.update(kw)
    return ProxyResponse(**base)


@pytest.mark.asyncio
async def test_requires_capability(client: AsyncClient) -> None:
    resp = await client.get(f"/client/apis/{uuid.uuid4()}/proxies")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_blocked_when_not_managed(client: AsyncClient, as_client_user) -> None:
    perm = MagicMock(proxy_managed_by_client=False)
    with patch(
        "app.domains.proxies.client_router.get_permission",
        new=AsyncMock(return_value=perm),
    ):
        resp = await client.get(f"/client/apis/{uuid.uuid4()}/proxies")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_client_lists_own_proxies_when_managed(
    client: AsyncClient, as_client_user
) -> None:
    perm = MagicMock(proxy_managed_by_client=True)
    with patch(
        "app.domains.proxies.client_router.get_permission",
        new=AsyncMock(return_value=perm),
    ), patch(
        "app.domains.proxies.client_router.list_api_proxies",
        new=AsyncMock(return_value=["x", "y"]),
    ), patch(
        "app.domains.proxies.client_router.to_response",
        new=MagicMock(side_effect=lambda p: make_proxy_response(as_client_user, name=str(p))),
    ):
        resp = await client.get(f"/client/apis/{uuid.uuid4()}/proxies")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


@pytest.mark.asyncio
async def test_client_create_forces_account_and_ownership(
    client: AsyncClient, as_client_user
) -> None:
    perm = MagicMock(proxy_managed_by_client=True)
    proxy = make_proxy_response(as_client_user)
    with patch(
        "app.domains.proxies.client_router.get_permission",
        new=AsyncMock(return_value=perm),
    ), patch(
        "app.domains.proxies.client_router.create_proxy",
        new=AsyncMock(),
    ) as create, patch(
        "app.domains.proxies.client_router.to_response",
        new=MagicMock(return_value=proxy),
    ):
        resp = await client.post(
            f"/client/apis/{uuid.uuid4()}/proxies",
            json={"name": "p1", "host": "1.2.3.4", "port": 8080},
        )
    assert resp.status_code == 201
    # repassou o account do cliente e ownership=client
    assert create.await_args.kwargs["account_id"] == as_client_user
    assert create.await_args.args[2].ownership.value == "client"
