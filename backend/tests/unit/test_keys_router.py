# RED → GREEN
# Testes para o domínio keys.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.domains.keys.models import APIKey, APIKeyStatus


def make_api_key(status: APIKeyStatus = APIKeyStatus.ACTIVE) -> APIKey:
    return APIKey(
        id=uuid.uuid4(),
        client_id=uuid.uuid4(),
        name="Production Key",
        key_prefix="abcd1234",
        key_secret_hash="hashed-secret",
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def client_headers() -> dict:
    token = create_access_token("acme@example.com", role="client")
    return {"Authorization": f"Bearer {token}"}


def admin_headers() -> dict:
    token = create_access_token("admin@bridge.com", role="admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_client_can_create_api_key(client: AsyncClient) -> None:
    api_key = make_api_key()
    with patch(
        "app.domains.keys.router.create_api_key",
        new=AsyncMock(return_value=(api_key, "brg_abcd1234_secret-value")),
    ):
        response = await client.post(
            "/keys",
            json={"name": "Production Key"},
            headers=client_headers(),
        )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Production Key"
    assert body["api_key"] == "brg_abcd1234_secret-value"


@pytest.mark.asyncio
async def test_api_key_secret_shown_only_at_creation(client: AsyncClient) -> None:
    api_key = make_api_key()
    with patch(
        "app.domains.keys.router.create_api_key",
        new=AsyncMock(return_value=(api_key, "brg_abcd1234_secret-value")),
    ):
        create_response = await client.post(
            "/keys",
            json={"name": "Production Key"},
            headers=client_headers(),
        )
    with patch(
        "app.domains.keys.router.list_api_keys",
        new=AsyncMock(return_value=[api_key]),
    ):
        list_response = await client.get("/keys", headers=client_headers())
    assert "api_key" in create_response.json()
    assert "api_key" not in list_response.json()["items"][0]


@pytest.mark.asyncio
async def test_client_can_list_own_api_keys(client: AsyncClient) -> None:
    api_keys = [make_api_key(), make_api_key()]
    with patch(
        "app.domains.keys.router.list_api_keys",
        new=AsyncMock(return_value=api_keys),
    ):
        response = await client.get("/keys", headers=client_headers())
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


@pytest.mark.asyncio
async def test_client_can_revoke_own_key(client: AsyncClient) -> None:
    revoked_key = make_api_key(status=APIKeyStatus.REVOKED)
    with patch(
        "app.domains.keys.router.revoke_api_key",
        new=AsyncMock(return_value=revoked_key),
    ):
        response = await client.patch(
            f"/keys/{revoked_key.id}/revoke",
            headers=client_headers(),
        )
    assert response.status_code == 200
    assert response.json()["status"] == "revoked"


@pytest.mark.asyncio
async def test_client_routes_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/keys")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_token_cannot_access_client_keys_routes(
    client: AsyncClient,
) -> None:
    response = await client.get("/keys", headers=admin_headers())
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_revoke_missing_key_returns_404(client: AsyncClient) -> None:
    from app.domains.keys.service import APIKeyNotFoundError

    with patch(
        "app.domains.keys.router.revoke_api_key",
        new=AsyncMock(side_effect=APIKeyNotFoundError),
    ):
        response = await client.patch(
            f"/keys/{uuid.uuid4()}/revoke",
            headers=client_headers(),
        )
    assert response.status_code == 404
