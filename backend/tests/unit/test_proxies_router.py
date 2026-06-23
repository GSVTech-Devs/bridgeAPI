# Camada HTTP do CRUD admin de proxies/pools e dos endpoints de ingest.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.domains.proxies.models import ProxyPool
from app.domains.proxies.schemas import ProxyResponse


def admin_headers() -> dict:
    return {"Authorization": f"Bearer {create_access_token('admin@bridge.com', role='admin')}"}


def client_headers() -> dict:
    token = create_access_token(
        "acme@example.com", role="owner",
        extra_claims={"user_id": str(uuid.uuid4()), "account_id": str(uuid.uuid4())},
    )
    return {"Authorization": f"Bearer {token}"}


def make_proxy_response(**kw) -> ProxyResponse:
    base = dict(
        id=uuid.uuid4(), pool_id=uuid.uuid4(), name="p1", ownership="platform",
        type="residential", scheme="http", host="1.2.3.4", port=8080,
        username="u", has_password=True, rotation="sticky", status="active",
        priority=10, created_at=datetime.now(timezone.utc),
    )
    base.update(kw)
    return ProxyResponse(**base)


# ------------------------------------------------------------------ auth gate
@pytest.mark.asyncio
async def test_list_proxies_requires_admin(client: AsyncClient) -> None:
    resp = await client.get("/proxies", headers=client_headers())
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_pool_requires_admin(client: AsyncClient) -> None:
    resp = await client.post("/proxies/pools", json={"name": "x"}, headers=client_headers())
    assert resp.status_code == 403


# ----------------------------------------------------------------------- pools
@pytest.mark.asyncio
async def test_create_pool(client: AsyncClient) -> None:
    pool = ProxyPool(name="main", description="meu pool")
    pool.id = uuid.uuid4()
    pool.created_at = datetime.now(timezone.utc)
    with patch("app.domains.proxies.router.create_pool", new=AsyncMock(return_value=pool)):
        resp = await client.post(
            "/proxies/pools", json={"name": "main", "description": "meu pool"},
            headers=admin_headers(),
        )
    assert resp.status_code == 201
    assert resp.json()["name"] == "main"


@pytest.mark.asyncio
async def test_list_pools(client: AsyncClient) -> None:
    pool = ProxyPool(name="main")
    pool.id = uuid.uuid4()
    pool.description = None
    pool.created_at = datetime.now(timezone.utc)
    with patch("app.domains.proxies.router.list_pools", new=AsyncMock(return_value=[(pool, 3)])):
        resp = await client.get("/proxies/pools", headers=admin_headers())
    assert resp.status_code == 200
    assert resp.json()["items"][0]["proxy_count"] == 3


# --------------------------------------------------------------------- proxies
@pytest.mark.asyncio
async def test_create_proxy_masks_password_in_response(client: AsyncClient) -> None:
    with patch("app.domains.proxies.router.create_proxy", new=AsyncMock()), patch(
        "app.domains.proxies.router.to_response",
        new=MagicMock(return_value=make_proxy_response()),
    ):
        resp = await client.post(
            "/proxies",
            json={"name": "p1", "host": "1.2.3.4", "port": 8080, "password": "secret"},
            headers=admin_headers(),
        )
    assert resp.status_code == 201
    body = resp.json()
    assert "password" not in body          # senha nunca volta
    assert body["has_password"] is True
    assert body["username"] == "u"


@pytest.mark.asyncio
async def test_list_proxies(client: AsyncClient) -> None:
    with patch("app.domains.proxies.router.list_proxies", new=AsyncMock(return_value=["x", "y"])), patch(
        "app.domains.proxies.router.to_response",
        new=MagicMock(side_effect=lambda p: make_proxy_response(name=str(p))),
    ):
        resp = await client.get("/proxies", headers=admin_headers())
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


# ------------------------------------------------------- atribuição à API
@pytest.mark.asyncio
async def test_assign_pool_to_api(client: AsyncClient) -> None:
    pool_id = uuid.uuid4()
    api = MagicMock()
    api.id = uuid.uuid4()
    api.proxy_pool_id = pool_id
    with patch("app.domains.proxies.router.assign_pool_to_api", new=AsyncMock(return_value=api)):
        resp = await client.put(
            f"/proxies/assignments/{api.id}",
            json={"proxy_pool_id": str(pool_id)},
            headers=admin_headers(),
        )
    assert resp.status_code == 200
    assert resp.json()["proxy_pool_id"] == str(pool_id)
