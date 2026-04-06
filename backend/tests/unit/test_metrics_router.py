# RED → GREEN
# Testes de integração para app/domains/metrics/router.py
# Usa tokens JWT reais (create_access_token) e patches nos services,
# seguindo o padrão estabelecido nos outros testes de router.
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

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


def client_headers() -> dict:
    token = create_access_token("acme@example.com", role="client")
    return {"Authorization": f"Bearer {token}"}


def admin_headers() -> dict:
    token = create_access_token("admin@bridge.dev", role="admin")
    return {"Authorization": f"Bearer {token}"}


def make_client_obj() -> MagicMock:
    obj = MagicMock()
    obj.id = uuid.uuid4()
    return obj


# ---------------------------------------------------------------------------
# GET /metrics/dashboard — cliente autenticado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_dashboard_returns_200(client: AsyncClient) -> None:
    with (
        patch(
            "app.domains.metrics.router.get_client_by_email",
            new=AsyncMock(return_value=make_client_obj()),
        ),
        patch(
            "app.domains.metrics.router.get_client_dashboard",
            new=AsyncMock(return_value=DASHBOARD_PAYLOAD),
        ),
    ):
        response = await client.get("/metrics/dashboard", headers=client_headers())

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_client_dashboard_returns_correct_payload(client: AsyncClient) -> None:
    with (
        patch(
            "app.domains.metrics.router.get_client_by_email",
            new=AsyncMock(return_value=make_client_obj()),
        ),
        patch(
            "app.domains.metrics.router.get_client_dashboard",
            new=AsyncMock(return_value=DASHBOARD_PAYLOAD),
        ),
    ):
        response = await client.get("/metrics/dashboard", headers=client_headers())

    data = response.json()
    assert data["total_requests"] == 100
    assert data["error_rate"] == 5.0
    assert data["avg_latency_ms"] == 42.0
    assert data["total_cost"] == 1.50


@pytest.mark.asyncio
async def test_client_dashboard_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/metrics/dashboard")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_cannot_access_client_dashboard(client: AsyncClient) -> None:
    response = await client.get("/metrics/dashboard", headers=admin_headers())
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_client_dashboard_accepts_since_filter(client: AsyncClient) -> None:
    with (
        patch(
            "app.domains.metrics.router.get_client_by_email",
            new=AsyncMock(return_value=make_client_obj()),
        ),
        patch(
            "app.domains.metrics.router.get_client_dashboard",
            new=AsyncMock(return_value=DASHBOARD_PAYLOAD),
        ) as mock_svc,
    ):
        response = await client.get(
            "/metrics/dashboard?since=2024-01-01T00:00:00Z",
            headers=client_headers(),
        )

    assert response.status_code == 200
    assert mock_svc.called


@pytest.mark.asyncio
async def test_client_dashboard_accepts_until_filter(client: AsyncClient) -> None:
    with (
        patch(
            "app.domains.metrics.router.get_client_by_email",
            new=AsyncMock(return_value=make_client_obj()),
        ),
        patch(
            "app.domains.metrics.router.get_client_dashboard",
            new=AsyncMock(return_value=DASHBOARD_PAYLOAD),
        ) as mock_svc,
    ):
        response = await client.get(
            "/metrics/dashboard?until=2024-12-31T23:59:59Z",
            headers=client_headers(),
        )

    assert response.status_code == 200
    assert mock_svc.called


@pytest.mark.asyncio
async def test_client_dashboard_response_has_all_keys(client: AsyncClient) -> None:
    with (
        patch(
            "app.domains.metrics.router.get_client_by_email",
            new=AsyncMock(return_value=make_client_obj()),
        ),
        patch(
            "app.domains.metrics.router.get_client_dashboard",
            new=AsyncMock(return_value=DASHBOARD_PAYLOAD),
        ),
    ):
        response = await client.get("/metrics/dashboard", headers=client_headers())

    data = response.json()
    expected_keys = {
        "total_requests",
        "error_rate",
        "avg_latency_ms",
        "total_cost",
        "billable_requests",
        "non_billable_requests",
    }
    assert expected_keys.issubset(data.keys())


# ---------------------------------------------------------------------------
# GET /metrics/admin — admin autenticado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_metrics_returns_200(client: AsyncClient) -> None:
    with patch(
        "app.domains.metrics.router.get_admin_global_metrics",
        new=AsyncMock(return_value=ADMIN_PAYLOAD),
    ):
        response = await client.get("/metrics/admin", headers=admin_headers())

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_metrics_returns_correct_payload(client: AsyncClient) -> None:
    with patch(
        "app.domains.metrics.router.get_admin_global_metrics",
        new=AsyncMock(return_value=ADMIN_PAYLOAD),
    ):
        response = await client.get("/metrics/admin", headers=admin_headers())

    data = response.json()
    assert data["total_requests"] == 5000
    assert data["error_rate"] == 3.0
    assert data["total_cost"] == 120.0


@pytest.mark.asyncio
async def test_admin_metrics_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/metrics/admin")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_client_cannot_access_admin_metrics(client: AsyncClient) -> None:
    response = await client.get("/metrics/admin", headers=client_headers())
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_metrics_accepts_since_filter(client: AsyncClient) -> None:
    with patch(
        "app.domains.metrics.router.get_admin_global_metrics",
        new=AsyncMock(return_value=ADMIN_PAYLOAD),
    ) as mock_svc:
        response = await client.get(
            "/metrics/admin?since=2024-01-01T00:00:00Z",
            headers=admin_headers(),
        )

    assert response.status_code == 200
    assert mock_svc.called
