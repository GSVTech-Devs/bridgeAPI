# Testes da camada HTTP dos endpoints admin de logs estruturados e trace.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

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


def make_app_doc(cid: str) -> dict:
    return {
        "correlation_id": cid,
        "api_id": str(uuid.uuid4()),
        "level": "INFO",
        "event": "proxy.acquired",
        "message": "got proxy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /logs/admin/app
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_logs_require_admin(client: AsyncClient) -> None:
    resp = await client.get("/logs/admin/app", headers=client_headers())
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_app_logs_listed_for_admin(client: AsyncClient) -> None:
    cid = str(uuid.uuid4())
    with patch(
        "app.domains.logs.router.get_app_logs",
        new=AsyncMock(return_value=[make_app_doc(cid), make_app_doc(cid)]),
    ):
        resp = await client.get("/logs/admin/app", headers=admin_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["items"][0]["event"] == "proxy.acquired"


@pytest.mark.asyncio
async def test_app_logs_pass_filters_through(client: AsyncClient) -> None:
    with patch(
        "app.domains.logs.router.get_app_logs",
        new=AsyncMock(return_value=[]),
    ) as mock_get:
        await client.get(
            "/logs/admin/app?level=ERROR&error_code=PROXY_AUTH_FAILED",
            headers=admin_headers(),
        )

    kwargs = mock_get.call_args.kwargs
    assert kwargs["level"] == "ERROR"
    assert kwargs["error_code"] == "PROXY_AUTH_FAILED"


# ---------------------------------------------------------------------------
# GET /logs/admin/trace/{correlation_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trace_requires_admin(client: AsyncClient) -> None:
    resp = await client.get(
        f"/logs/admin/trace/{uuid.uuid4()}", headers=client_headers()
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_trace_returns_unified_timeline(client: AsyncClient) -> None:
    cid = str(uuid.uuid4())
    timeline = [
        {"source": "gateway", "correlation_id": cid, "method": "POST"},
        {"source": "app", "correlation_id": cid, "event": "proxy.acquired"},
    ]
    with patch(
        "app.domains.logs.router.get_trace_by_correlation_id",
        new=AsyncMock(return_value=timeline),
    ):
        resp = await client.get(
            f"/logs/admin/trace/{cid}", headers=admin_headers()
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["correlation_id"] == cid
    assert body["total"] == 2
    assert [i["source"] for i in body["items"]] == ["gateway", "app"]
