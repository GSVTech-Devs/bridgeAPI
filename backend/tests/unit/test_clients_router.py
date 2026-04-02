# RED → GREEN
# Testes para o domínio clients.
# Banco mockado via dependency override (conftest.py).
# Serviços mockados via unittest.mock.patch.
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.domains.clients.models import Client, ClientStatus


def make_client(status: ClientStatus = ClientStatus.PENDING) -> Client:
    return Client(
        id=uuid.uuid4(),
        name="Acme Corp",
        email="acme@example.com",
        password_hash="hashed",
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def admin_headers() -> dict:
    token = create_access_token("admin@bridge.com")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /clients/register  (público)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_creates_client_with_pending_status(
    client: AsyncClient,
) -> None:
    with patch(
        "app.domains.clients.router.register_client",
        new=AsyncMock(return_value=make_client(ClientStatus.PENDING)),
    ):
        response = await client.post(
            "/clients/register",
            json={"name": "Acme Corp", "email": "acme@example.com", "password": "pass"},
        )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_register_with_duplicate_email_returns_409(
    client: AsyncClient,
) -> None:
    from app.domains.clients.service import DuplicateEmailError

    with patch(
        "app.domains.clients.router.register_client",
        new=AsyncMock(side_effect=DuplicateEmailError),
    ):
        response = await client.post(
            "/clients/register",
            json={"name": "Acme", "email": "acme@example.com", "password": "pass123"},
        )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_with_missing_fields_returns_422(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/clients/register",
        json={"email": "acme@example.com"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /clients  (admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_clients_returns_paginated_results(
    client: AsyncClient,
) -> None:
    clients_list = [make_client(), make_client()]
    with patch(
        "app.domains.clients.router.list_clients",
        new=AsyncMock(return_value=(clients_list, 2)),
    ):
        response = await client.get("/clients", headers=admin_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_list_clients_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/clients")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /clients/{id}/approve  (admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_approve_pending_client(client: AsyncClient) -> None:
    approved = make_client(ClientStatus.ACTIVE)
    with patch(
        "app.domains.clients.router.approve_client",
        new=AsyncMock(return_value=approved),
    ):
        response = await client.patch(
            f"/clients/{approved.id}/approve", headers=admin_headers()
        )
    assert response.status_code == 200
    assert response.json()["status"] == "active"


@pytest.mark.asyncio
async def test_cannot_approve_already_active_client_returns_409(
    client: AsyncClient,
) -> None:
    from app.domains.clients.service import InvalidStatusTransitionError

    with patch(
        "app.domains.clients.router.approve_client",
        new=AsyncMock(side_effect=InvalidStatusTransitionError),
    ):
        response = await client.patch(
            f"/clients/{uuid.uuid4()}/approve", headers=admin_headers()
        )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_approve_nonexistent_client_returns_404(client: AsyncClient) -> None:
    from app.domains.clients.service import ClientNotFoundError

    with patch(
        "app.domains.clients.router.approve_client",
        new=AsyncMock(side_effect=ClientNotFoundError),
    ):
        response = await client.patch(
            f"/clients/{uuid.uuid4()}/approve", headers=admin_headers()
        )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /clients/{id}/reject  (admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_reject_pending_client(client: AsyncClient) -> None:
    rejected = make_client(ClientStatus.REJECTED)
    with patch(
        "app.domains.clients.router.reject_client",
        new=AsyncMock(return_value=rejected),
    ):
        response = await client.patch(
            f"/clients/{rejected.id}/reject", headers=admin_headers()
        )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


# ---------------------------------------------------------------------------
# POST /clients/login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_active_client_can_login(client: AsyncClient) -> None:
    active = make_client(ClientStatus.ACTIVE)
    with patch(
        "app.domains.clients.router.authenticate_client",
        new=AsyncMock(return_value=active),
    ):
        response = await client.post(
            "/clients/login",
            json={"email": "acme@example.com", "password": "pass123"},
        )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_pending_client_cannot_login(client: AsyncClient) -> None:
    pending = make_client(ClientStatus.PENDING)
    with patch(
        "app.domains.clients.router.authenticate_client",
        new=AsyncMock(return_value=pending),
    ):
        response = await client.post(
            "/clients/login",
            json={"email": "acme@example.com", "password": "pass123"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_rejected_client_cannot_login(client: AsyncClient) -> None:
    rejected = make_client(ClientStatus.REJECTED)
    with patch(
        "app.domains.clients.router.authenticate_client",
        new=AsyncMock(return_value=rejected),
    ):
        response = await client.post(
            "/clients/login",
            json={"email": "acme@example.com", "password": "pass123"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_wrong_credentials_returns_401(client: AsyncClient) -> None:
    with patch(
        "app.domains.clients.router.authenticate_client",
        new=AsyncMock(return_value=None),
    ):
        response = await client.post(
            "/clients/login",
            json={"email": "acme@example.com", "password": "wrong"},
        )
    assert response.status_code == 401
