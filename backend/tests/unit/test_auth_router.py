# RED → GREEN
# Testes para o router de autenticação — POST /auth/login e GET /auth/me.
# O banco de dados é mockado via dependency override.
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.domains.auth.models import User


def make_user(email: str = "admin@bridge.com") -> User:
    return User(
        email=email,
        password_hash=hash_password("secret123"),
        role="admin",
    )


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_credentials_return_jwt(client: AsyncClient) -> None:
    user = make_user()
    with patch(
        "app.domains.auth.router.authenticate_user", new=AsyncMock(return_value=user)
    ):
        response = await client.post(
            "/auth/login",
            json={"email": "admin@bridge.com", "password": "secret123"},
        )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_invalid_password_returns_401(client: AsyncClient) -> None:
    with patch(
        "app.domains.auth.router.authenticate_user", new=AsyncMock(return_value=None)
    ):
        response = await client.post(
            "/auth/login",
            json={"email": "admin@bridge.com", "password": "wrongpassword"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unknown_email_returns_401(client: AsyncClient) -> None:
    with patch(
        "app.domains.auth.router.authenticate_user", new=AsyncMock(return_value=None)
    ):
        response = await client.post(
            "/auth/login",
            json={"email": "unknown@bridge.com", "password": "any"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_with_missing_fields_returns_422(client: AsyncClient) -> None:
    response = await client.post("/auth/login", json={"email": "admin@bridge.com"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /auth/me  (rota protegida)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_protected_route_without_token_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_invalid_token_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/auth/me", headers={"Authorization": "Bearer invalidtoken"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_valid_token_returns_200(
    client: AsyncClient,
) -> None:
    token = create_access_token("admin@bridge.com")
    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "admin@bridge.com"
