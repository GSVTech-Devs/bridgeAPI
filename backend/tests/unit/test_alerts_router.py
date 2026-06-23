# HTTP dos alertas: /admin/alerts (admin) e /client/alerts (cliente, escopado).
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.domains.alerts.schemas import AlertListResponse, AlertResponse
from app.domains.auth.router import get_current_account_user, get_current_user
from app.main import app


@pytest.fixture
def as_admin():
    async def _identity():
        return MagicMock(role="admin", account_id=None)

    app.dependency_overrides[get_current_user] = _identity
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def account_id():
    return uuid.uuid4()


@pytest.fixture
def as_client_user(account_id):
    async def _identity():
        return MagicMock(role="owner", account_id=account_id)

    app.dependency_overrides[get_current_account_user] = _identity
    yield account_id
    app.dependency_overrides.pop(get_current_account_user, None)


def make_alert(**kw) -> AlertResponse:
    base = dict(
        id=uuid.uuid4(), account_id=None, api_id=uuid.uuid4(), api_name="API X",
        resource_id=None, type="api_down", severity="critical", status="active",
        message="down", context=None, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc), resolved_at=None,
    )
    base.update(kw)
    return AlertResponse(**base)


@pytest.mark.asyncio
async def test_admin_list_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/admin/alerts")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_list_alerts(client: AsyncClient, as_admin) -> None:
    payload = AlertListResponse(items=[make_alert()], total=1, active_count=1)
    with patch(
        "app.domains.alerts.router.list_alerts", new=AsyncMock(return_value=payload)
    ) as listed:
        resp = await client.get("/admin/alerts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_count"] == 1 and body["total"] == 1
    # admin enxerga tudo
    assert listed.await_args.kwargs["is_admin"] is True


@pytest.mark.asyncio
async def test_admin_ack_alert(client: AsyncClient, as_admin) -> None:
    with patch(
        "app.domains.alerts.router.acknowledge_alert", new=AsyncMock(return_value=MagicMock())
    ), patch(
        "app.domains.alerts.router.to_response",
        new=MagicMock(return_value=make_alert(status="acknowledged")),
    ):
        resp = await client.post(f"/admin/alerts/{uuid.uuid4()}/ack")
    assert resp.status_code == 200
    assert resp.json()["status"] == "acknowledged"


@pytest.mark.asyncio
async def test_client_list_is_scoped_to_account(client: AsyncClient, as_client_user) -> None:
    account_id = as_client_user
    payload = AlertListResponse(items=[], total=0, active_count=0)
    with patch(
        "app.domains.alerts.router.list_alerts", new=AsyncMock(return_value=payload)
    ) as listed:
        resp = await client.get("/client/alerts")
    assert resp.status_code == 200
    # cliente: escopo da própria conta, nunca admin
    assert listed.await_args.kwargs["is_admin"] is False
    assert listed.await_args.kwargs["account_id"] == account_id


@pytest.mark.asyncio
async def test_client_list_requires_account_user(client: AsyncClient) -> None:
    resp = await client.get("/client/alerts")
    assert resp.status_code in (401, 403)
