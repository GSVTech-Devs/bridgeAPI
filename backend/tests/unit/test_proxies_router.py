# Camada HTTP do CRUD admin de proxies (aninhado em /apis/{api_id}/proxies) + monitoramento.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.domains.proxies.schemas import ProxyMonitorItem, ProxyResponse


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
        id=uuid.uuid4(), api_id=uuid.uuid4(), account_id=None, name="p1",
        ownership="platform", type="residential", scheme="http", host="1.2.3.4",
        port=8080, username="u", has_password=True, rotation="sticky",
        status="active", priority=10, created_at=datetime.now(timezone.utc),
    )
    base.update(kw)
    return ProxyResponse(**base)


# ------------------------------------------------------------------ auth gate
@pytest.mark.asyncio
async def test_list_proxies_requires_admin(client: AsyncClient) -> None:
    resp = await client.get(f"/apis/{uuid.uuid4()}/proxies", headers=client_headers())
    assert resp.status_code == 403


# --------------------------------------------------------------------- proxies
@pytest.mark.asyncio
async def test_create_proxy_masks_password_in_response(client: AsyncClient) -> None:
    with patch("app.domains.proxies.router.create_proxy", new=AsyncMock()), patch(
        "app.domains.proxies.router.to_response",
        new=MagicMock(return_value=make_proxy_response()),
    ):
        resp = await client.post(
            f"/apis/{uuid.uuid4()}/proxies",
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
    with patch(
        "app.domains.proxies.router.list_api_proxies",
        new=AsyncMock(return_value=["x", "y"]),
    ), patch(
        "app.domains.proxies.router.to_response",
        new=MagicMock(side_effect=lambda p: make_proxy_response(name=str(p))),
    ):
        resp = await client.get(f"/apis/{uuid.uuid4()}/proxies", headers=admin_headers())
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


# ----------------------------------------------------------- monitoramento
@pytest.mark.asyncio
async def test_monitor_proxies(client: AsyncClient) -> None:
    item = ProxyMonitorItem(
        id=uuid.uuid4(), api_id=uuid.uuid4(), api_name="API X", account_id=None,
        name="p1", host="1.2.3.4", port=8080, status="failing", priority=10,
        last_error="boom", last_error_at=datetime.now(timezone.utc),
    )
    with patch(
        "app.domains.proxies.router.monitor_proxies",
        new=AsyncMock(return_value=[item]),
    ):
        resp = await client.get("/monitoring/proxies", headers=admin_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["api_name"] == "API X"
    assert body["items"][0]["status"] == "failing"
