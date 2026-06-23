# Testes da camada HTTP de ingestão (POST /ingest/logs, POST /ingest/apis/{id}/token).
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.mongo_client import get_mongo_db
from app.core.security import create_access_token
from app.domains.apis.service import APINotFoundError
from app.main import app


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


def make_entry() -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "INFO",
        "correlation_id": str(uuid.uuid4()),
        "event": "request.received",
        "message": "hello",
    }


def fake_api():
    api = MagicMock()
    api.id = uuid.uuid4()
    return api


# ---------------------------------------------------------------------------
# POST /ingest/logs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_logs_requires_service_token(client: AsyncClient) -> None:
    resp = await client.post("/ingest/logs", json={"entries": [make_entry()]})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ingest_logs_rejects_invalid_token(client: AsyncClient) -> None:
    with patch(
        "app.domains.ingest.router.authenticate_service_token",
        new=AsyncMock(return_value=None),
    ):
        resp = await client.post(
            "/ingest/logs",
            json={"entries": [make_entry()]},
            headers={"X-Service-Token": "brgsvc_bad_token"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ingest_logs_accepts_valid_batch(client: AsyncClient) -> None:
    async def override_mongo():
        yield MagicMock()

    app.dependency_overrides[get_mongo_db] = override_mongo

    with (
        patch(
            "app.domains.ingest.router.authenticate_service_token",
            new=AsyncMock(return_value=fake_api()),
        ),
        patch(
            "app.domains.ingest.router.write_app_logs",
            new=AsyncMock(return_value=2),
        ),
    ):
        resp = await client.post(
            "/ingest/logs",
            json={"entries": [make_entry(), make_entry()]},
            headers={"X-Service-Token": "brgsvc_good_token"},
        )

    assert resp.status_code == 200
    assert resp.json()["accepted"] == 2


@pytest.mark.asyncio
async def test_ingest_logs_rejects_empty_entries(client: AsyncClient) -> None:
    with patch(
        "app.domains.ingest.router.authenticate_service_token",
        new=AsyncMock(return_value=fake_api()),
    ):
        resp = await client.post(
            "/ingest/logs",
            json={"entries": []},
            headers={"X-Service-Token": "brgsvc_good_token"},
        )
    assert resp.status_code == 422  # validação Pydantic (min_length=1)


# ---------------------------------------------------------------------------
# POST /ingest/apis/{id}/token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_token_requires_admin(client: AsyncClient) -> None:
    api_id = str(uuid.uuid4())
    resp = await client.post(f"/ingest/apis/{api_id}/token", headers=client_headers())
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_generate_token_returns_raw_token(client: AsyncClient) -> None:
    api = fake_api()
    api.service_token_prefix = "abcd1234"
    with patch(
        "app.domains.ingest.router.generate_service_token",
        new=AsyncMock(return_value=(api, "brgsvc_abcd1234_secret")),
    ):
        resp = await client.post(
            f"/ingest/apis/{api.id}/token", headers=admin_headers()
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["service_token"] == "brgsvc_abcd1234_secret"
    assert body["prefix"] == "abcd1234"


@pytest.mark.asyncio
async def test_generate_token_404_for_unknown_api(client: AsyncClient) -> None:
    with patch(
        "app.domains.ingest.router.generate_service_token",
        new=AsyncMock(side_effect=APINotFoundError("nope")),
    ):
        resp = await client.post(
            f"/ingest/apis/{uuid.uuid4()}/token", headers=admin_headers()
        )
    assert resp.status_code == 404
