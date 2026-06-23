# Autosserviço de proxies do cliente: /client/proxies/* (escopado à conta).
from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.domains.proxies import client_router
from app.domains.proxies.models import Proxy, ProxyPool, ProxyStatus
from app.main import app


@pytest.fixture
def account_id():
    return uuid.uuid4()


@pytest.fixture
def as_client_user(account_id):
    """Sobe-escreve a dependency de capability por uma identidade com account."""

    async def _identity():
        return MagicMock(account_id=account_id)

    app.dependency_overrides[client_router._require] = _identity
    yield account_id
    app.dependency_overrides.pop(client_router._require, None)


def make_pool(account_id, **kw) -> ProxyPool:
    pool = ProxyPool(name=kw.get("name", "mine"))
    pool.id = kw.get("id", uuid.uuid4())
    pool.account_id = account_id
    pool.description = None
    pool.created_at = datetime.datetime.now(datetime.timezone.utc)
    return pool


def make_proxy(account_id, **kw) -> Proxy:
    p = Proxy()
    p.id = uuid.uuid4()
    p.account_id = account_id
    p.pool_id = kw.get("pool_id")
    p.name = "p1"
    p.provider = None
    p.ownership = "client"
    p.type = "datacenter"
    p.scheme = "http"
    p.host = "1.2.3.4"
    p.port = 8080
    p.username_encrypted = None
    p.password_encrypted = None
    p.rotation = "sticky"
    p.session_ttl_s = None
    p.status = ProxyStatus.ACTIVE.value
    p.priority = 100
    p.last_error = None
    p.last_error_at = None
    p.created_at = datetime.datetime.now(datetime.timezone.utc)
    return p


@pytest.mark.asyncio
async def test_requires_capability(client: AsyncClient) -> None:
    # sem override de auth → token ausente vira 403/401 (não 200)
    resp = await client.get("/client/proxies/pools")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_client_create_pool_is_account_scoped(
    client: AsyncClient, as_client_user
) -> None:
    pool = make_pool(as_client_user, name="mine")
    with patch(
        "app.domains.proxies.client_router.create_pool",
        new=AsyncMock(return_value=pool),
    ) as create:
        resp = await client.post("/client/proxies/pools", json={"name": "mine"})
    assert resp.status_code == 201
    assert resp.json()["account_id"] == str(as_client_user)
    # passou o account_id da identidade ao service
    assert create.await_args.kwargs["account_id"] == as_client_user


@pytest.mark.asyncio
async def test_client_create_proxy_forces_account_and_ownership(
    client: AsyncClient, as_client_user
) -> None:
    proxy = make_proxy(as_client_user)
    with patch(
        "app.domains.proxies.client_router.create_proxy",
        new=AsyncMock(return_value=proxy),
    ) as create:
        resp = await client.post(
            "/client/proxies",
            json={"name": "p1", "host": "1.2.3.4", "port": 8080},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["account_id"] == str(as_client_user)
    # o service recebeu o account do cliente e ownership=client
    assert create.await_args.kwargs["account_id"] == as_client_user
    assert create.await_args.args[1].ownership.value == "client"


@pytest.mark.asyncio
async def test_client_list_assignments(client: AsyncClient, as_client_user) -> None:
    api = MagicMock(id=uuid.uuid4())
    api.name = "API X"  # name é kwarg especial do MagicMock; setar depois
    pool_id = uuid.uuid4()
    with patch(
        "app.domains.proxies.client_router.get_account_authorized_apis",
        new=AsyncMock(return_value=[api]),
    ), patch(
        "app.domains.proxies.client_router.get_client_overrides",
        new=AsyncMock(return_value={api.id: pool_id}),
    ):
        resp = await client.get("/client/proxies/assignments")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["api_name"] == "API X"
    assert item["proxy_pool_id"] == str(pool_id)


@pytest.mark.asyncio
async def test_client_set_assignment(client: AsyncClient, as_client_user) -> None:
    api_id = uuid.uuid4()
    pool_id = uuid.uuid4()
    with patch(
        "app.domains.proxies.client_router.set_client_override",
        new=AsyncMock(return_value=pool_id),
    ) as setter:
        resp = await client.put(
            f"/client/proxies/assignments/{api_id}",
            json={"proxy_pool_id": str(pool_id)},
        )
    assert resp.status_code == 200
    assert resp.json()["proxy_pool_id"] == str(pool_id)
    # repassou a conta da identidade
    assert setter.await_args.args[2] == as_client_user
