# RED → GREEN
# Testes para o domínio permissions.
# Banco mockado via dependency override (conftest.py).
# Serviços mockados via unittest.mock.patch.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.domains.apis.models import APIAuthType, APIStatus, ExternalAPI
from app.domains.permissions.models import Permission


def make_permission(
    client_id: uuid.UUID | None = None,
    api_id: uuid.UUID | None = None,
    revoked_at: datetime | None = None,
) -> Permission:
    return Permission(
        id=uuid.uuid4(),
        client_id=client_id or uuid.uuid4(),
        api_id=api_id or uuid.uuid4(),
        granted_at=datetime.now(timezone.utc),
        revoked_at=revoked_at,
    )


def make_api() -> ExternalAPI:
    return ExternalAPI(
        id=uuid.uuid4(),
        name="Stripe API",
        base_url="https://api.stripe.com",
        master_key_encrypted="encrypted-key",
        auth_type=APIAuthType.API_KEY,
        status=APIStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
    )


def admin_headers() -> dict:
    token = create_access_token("admin@bridge.com", role="admin")
    return {"Authorization": f"Bearer {token}"}


def client_headers() -> dict:
    token = create_access_token("acme@example.com", role="client")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /permissions  (admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_grant_api_access_to_client(client: AsyncClient) -> None:
    client_id = uuid.uuid4()
    api_id = uuid.uuid4()
    permission = make_permission(client_id=client_id, api_id=api_id)

    with patch(
        "app.domains.permissions.router.grant_permission",
        new=AsyncMock(return_value=permission),
    ):
        response = await client.post(
            "/permissions",
            json={"client_id": str(client_id), "api_id": str(api_id)},
            headers=admin_headers(),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["client_id"] == str(client_id)
    assert body["api_id"] == str(api_id)
    assert body["revoked_at"] is None


@pytest.mark.asyncio
async def test_duplicate_permission_returns_409(client: AsyncClient) -> None:
    from app.domains.permissions.service import DuplicatePermissionError

    with patch(
        "app.domains.permissions.router.grant_permission",
        new=AsyncMock(side_effect=DuplicatePermissionError),
    ):
        response = await client.post(
            "/permissions",
            json={"client_id": str(uuid.uuid4()), "api_id": str(uuid.uuid4())},
            headers=admin_headers(),
        )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_grant_permission_requires_admin(client: AsyncClient) -> None:
    response = await client.post(
        "/permissions",
        json={"client_id": str(uuid.uuid4()), "api_id": str(uuid.uuid4())},
        headers=client_headers(),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_grant_permission_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/permissions",
        json={"client_id": str(uuid.uuid4()), "api_id": str(uuid.uuid4())},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /permissions/{client_id}/{api_id}/revoke  (admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_revoke_api_access(client: AsyncClient) -> None:
    client_id = uuid.uuid4()
    api_id = uuid.uuid4()
    revoked = make_permission(
        client_id=client_id,
        api_id=api_id,
        revoked_at=datetime.now(timezone.utc),
    )

    with patch(
        "app.domains.permissions.router.revoke_permission",
        new=AsyncMock(return_value=revoked),
    ):
        response = await client.patch(
            f"/permissions/{client_id}/{api_id}/revoke",
            headers=admin_headers(),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["revoked_at"] is not None


@pytest.mark.asyncio
async def test_revoke_nonexistent_permission_returns_404(client: AsyncClient) -> None:
    from app.domains.permissions.service import PermissionNotFoundError

    with patch(
        "app.domains.permissions.router.revoke_permission",
        new=AsyncMock(side_effect=PermissionNotFoundError),
    ):
        response = await client.patch(
            f"/permissions/{uuid.uuid4()}/{uuid.uuid4()}/revoke",
            headers=admin_headers(),
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_revoke_permission_requires_admin(client: AsyncClient) -> None:
    response = await client.patch(
        f"/permissions/{uuid.uuid4()}/{uuid.uuid4()}/revoke",
        headers=client_headers(),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /catalog  (client)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_sees_only_authorized_apis_in_catalog(
    client: AsyncClient,
) -> None:
    apis = [make_api(), make_api()]

    with patch(
        "app.domains.permissions.router.get_client_authorized_apis",
        new=AsyncMock(return_value=apis),
    ):
        response = await client.get("/catalog", headers=client_headers())

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["total"] == 2


@pytest.mark.asyncio
async def test_revoked_permission_hides_api_from_catalog(
    client: AsyncClient,
) -> None:
    with patch(
        "app.domains.permissions.router.get_client_authorized_apis",
        new=AsyncMock(return_value=[]),
    ):
        response = await client.get("/catalog", headers=client_headers())

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_catalog_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/catalog")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_cannot_access_client_catalog(client: AsyncClient) -> None:
    response = await client.get("/catalog", headers=admin_headers())
    assert response.status_code == 403
