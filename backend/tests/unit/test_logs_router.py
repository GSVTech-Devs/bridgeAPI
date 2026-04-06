# RED → GREEN
# Testes para o domínio logs — camada HTTP.
# get_client_logs é mockado via patch; mongo_db é neutralizado no conftest.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token


def client_headers() -> dict:
    token = create_access_token("acme@example.com", role="client")
    return {"Authorization": f"Bearer {token}"}


def admin_headers() -> dict:
    token = create_access_token("admin@bridge.com", role="admin")
    return {"Authorization": f"Bearer {token}"}


def make_log_doc(client_id: str | None = None) -> dict:
    return {
        "correlation_id": str(uuid.uuid4()),
        "client_id": client_id or str(uuid.uuid4()),
        "api_id": str(uuid.uuid4()),
        "key_id": str(uuid.uuid4()),
        "path": "v1/charges",
        "method": "GET",
        "status_code": 200,
        "latency_ms": 38.2,
        "request_headers": {"content-type": "application/json"},
        "request_body": "",
        "response_headers": {"content-type": "application/json"},
        "response_body": '{"id": "ch_1"}',
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /logs  (client)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_can_list_own_logs(client: AsyncClient) -> None:
    logs = [make_log_doc(), make_log_doc()]

    with patch(
        "app.domains.logs.router.get_client_logs",
        new=AsyncMock(return_value=logs),
    ):
        response = await client.get("/logs", headers=client_headers())

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["total"] == 2


@pytest.mark.asyncio
async def test_logs_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/logs")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_cannot_access_client_logs_route(client: AsyncClient) -> None:
    response = await client.get("/logs", headers=admin_headers())
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_logs_response_includes_correlation_id(client: AsyncClient) -> None:
    cid = str(uuid.uuid4())
    logs = [make_log_doc()]
    logs[0]["correlation_id"] = cid

    with patch(
        "app.domains.logs.router.get_client_logs",
        new=AsyncMock(return_value=logs),
    ):
        response = await client.get("/logs", headers=client_headers())

    items = response.json()["items"]
    assert items[0]["correlation_id"] == cid


@pytest.mark.asyncio
async def test_empty_log_list_returns_empty_items(client: AsyncClient) -> None:
    with patch(
        "app.domains.logs.router.get_client_logs",
        new=AsyncMock(return_value=[]),
    ):
        response = await client.get("/logs", headers=client_headers())

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_logs_are_paginated_with_skip_and_limit(client: AsyncClient) -> None:
    with patch(
        "app.domains.logs.router.get_client_logs",
        new=AsyncMock(return_value=[]),
    ) as mock_get:
        await client.get("/logs?skip=10&limit=5", headers=client_headers())

    call_kwargs = mock_get.call_args.kwargs
    assert call_kwargs["skip"] == 10
    assert call_kwargs["limit"] == 5
