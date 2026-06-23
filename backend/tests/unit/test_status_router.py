# Camada HTTP de status: overview, events, stream (auth) e POST /ingest/status.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token


def admin_headers() -> dict:
    token = create_access_token("admin@bridge.com", role="admin")
    return {"Authorization": f"Bearer {token}"}


def client_headers() -> dict:
    token = create_access_token(
        "acme@example.com",
        role="owner",
        extra_claims={"user_id": str(uuid.uuid4()), "account_id": str(uuid.uuid4())},
    )
    return {"Authorization": f"Bearer {token}"}


def overview_doc(status: str = "healthy") -> dict:
    return {
        "api_id": str(uuid.uuid4()),
        "api_name": "Serasa API",
        "status": status,
        "reported_status": status,
        "sdk_version": "1.0.0",
        "uptime_s": 1234,
        "checks": {"proxy_pool": {"status": "healthy", "available": 8}},
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "stale": False,
    }


# ---------------------------------------------------------------------------
# GET /status/overview
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_overview_requires_admin(client: AsyncClient) -> None:
    resp = await client.get("/status/overview", headers=client_headers())
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_overview_returns_items(client: AsyncClient) -> None:
    with patch(
        "app.domains.status.router.get_overview",
        new=AsyncMock(return_value=[overview_doc("degraded")]),
    ):
        resp = await client.get("/status/overview", headers=admin_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "degraded"
    assert body["items"][0]["checks"]["proxy_pool"]["available"] == 8


# ---------------------------------------------------------------------------
# GET /status/events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_events_requires_admin(client: AsyncClient) -> None:
    resp = await client.get("/status/events", headers=client_headers())
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_events_returns_transitions(client: AsyncClient) -> None:
    ev = {"api_id": str(uuid.uuid4()), "api_name": "X", "from_status": "healthy", "to_status": "down"}
    with patch(
        "app.domains.status.router.get_events",
        new=AsyncMock(return_value=[ev]),
    ):
        resp = await client.get("/status/events", headers=admin_headers())
    assert resp.status_code == 200
    assert resp.json()["items"][0]["to_status"] == "down"


# ---------------------------------------------------------------------------
# GET /status/stream (SSE) — só auth (não consumimos o stream infinito)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_missing_token_is_rejected(client: AsyncClient) -> None:
    resp = await client.get("/status/stream")
    assert resp.status_code == 422  # token é query param obrigatório


@pytest.mark.asyncio
async def test_stream_invalid_token_is_unauthorized(client: AsyncClient) -> None:
    resp = await client.get("/status/stream?token=not-a-jwt")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stream_non_admin_token_forbidden(client: AsyncClient) -> None:
    token = create_access_token(
        "u@e.com", role="owner", extra_claims={"account_id": str(uuid.uuid4())}
    )
    resp = await client.get(f"/status/stream?token={token}")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /ingest/status
# ---------------------------------------------------------------------------


def fake_api():
    api = MagicMock()
    api.id = uuid.uuid4()
    return api


@pytest.mark.asyncio
async def test_ingest_status_requires_service_token(client: AsyncClient) -> None:
    resp = await client.post("/ingest/status", json={"status": "healthy"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ingest_status_accepts_report(client: AsyncClient) -> None:
    async def override_mongo():
        yield MagicMock()

    from app.core.mongo_client import get_mongo_db
    from app.main import app

    app.dependency_overrides[get_mongo_db] = override_mongo
    with (
        patch(
            "app.domains.ingest.router.authenticate_service_token",
            new=AsyncMock(return_value=fake_api()),
        ),
        patch(
            "app.domains.ingest.router.record_status",
            new=AsyncMock(return_value={}),
        ) as mock_record,
    ):
        resp = await client.post(
            "/ingest/status",
            json={"status": "degraded", "sdk_version": "1.0", "checks": {}},
            headers={"X-Service-Token": "brgsvc_good"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "status": "degraded"}
    mock_record.assert_awaited_once()
