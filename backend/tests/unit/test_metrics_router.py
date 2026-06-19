# Testes para app/domains/metrics/router.py.
# Tokens JWT reais; services mockados via patch.
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token

DASHBOARD_PAYLOAD = {
    "total_requests": 100,
    "error_rate": 5.0,
    "avg_latency_ms": 42.0,
    "total_cost": 1.50,
    "billable_requests": 80,
    "non_billable_requests": 20,
}

ADMIN_PAYLOAD = {
    "total_requests": 5000,
    "error_rate": 3.0,
    "avg_latency_ms": 60.0,
    "total_cost": 120.0,
    "billable_requests": 4500,
    "non_billable_requests": 500,
}


def account_headers() -> dict:
    token = create_access_token(
        "acme@example.com",
        role="owner",
        extra_claims={"user_id": str(uuid.uuid4()), "account_id": str(uuid.uuid4())},
    )
    return {"Authorization": f"Bearer {token}"}


def admin_headers() -> dict:
    token = create_access_token("admin@bridge.dev", role="admin")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /metrics/dashboard — usuário de account
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_account_dashboard_returns_payload(client: AsyncClient) -> None:
    with patch(
        "app.domains.metrics.router.get_client_dashboard",
        new=AsyncMock(return_value=DASHBOARD_PAYLOAD),
    ):
        response = await client.get("/metrics/dashboard", headers=account_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["total_requests"] == 100
    assert data["total_cost"] == 1.50


@pytest.mark.asyncio
async def test_dashboard_uses_account_id_from_token(client: AsyncClient) -> None:
    mock_svc = AsyncMock(return_value=DASHBOARD_PAYLOAD)
    with patch("app.domains.metrics.router.get_client_dashboard", new=mock_svc):
        await client.get("/metrics/dashboard", headers=account_headers())
    # o account_id (2º argumento posicional) deve ser um UUID vindo do token
    args = mock_svc.call_args.args
    assert isinstance(args[1], uuid.UUID)


@pytest.mark.asyncio
async def test_dashboard_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/metrics/dashboard")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_cannot_access_account_dashboard(client: AsyncClient) -> None:
    response = await client.get("/metrics/dashboard", headers=admin_headers())
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_dashboard_accepts_date_filters(client: AsyncClient) -> None:
    with patch(
        "app.domains.metrics.router.get_client_dashboard",
        new=AsyncMock(return_value=DASHBOARD_PAYLOAD),
    ) as mock_svc:
        response = await client.get(
            "/metrics/dashboard?since=2024-01-01T00:00:00Z&until=2024-12-31T23:59:59Z",
            headers=account_headers(),
        )
    assert response.status_code == 200
    assert mock_svc.called


# ---------------------------------------------------------------------------
# GET /metrics/admin — admin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_metrics_returns_payload(client: AsyncClient) -> None:
    with patch(
        "app.domains.metrics.router.get_admin_global_metrics",
        new=AsyncMock(return_value=ADMIN_PAYLOAD),
    ):
        response = await client.get("/metrics/admin", headers=admin_headers())

    assert response.status_code == 200
    assert response.json()["total_requests"] == 5000


@pytest.mark.asyncio
async def test_admin_metrics_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/metrics/admin")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_account_user_cannot_access_admin_metrics(client: AsyncClient) -> None:
    response = await client.get("/metrics/admin", headers=account_headers())
    assert response.status_code == 403
