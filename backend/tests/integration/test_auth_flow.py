"""Integration tests for the admin auth flow.

Exercises the full chain: real bcrypt hash persisted in Postgres, real JWT
signed with settings.app_secret_key, real HTTPBearer parsing, real role gate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.core.security import create_access_token, hash_password
from app.domains.auth.models import User

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

ADMIN_EMAIL = "admin@bridge.com"
ADMIN_PASSWORD = "s3cret-pass"


async def _seed_admin(db: AsyncSession) -> User:
    user = User(
        email=ADMIN_EMAIL,
        password_hash=hash_password(ADMIN_PASSWORD),
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def test_login_with_valid_credentials_returns_jwt(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_admin(db_session)

    response = await client.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_with_wrong_password_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_admin(db_session)

    response = await client.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": "wrong"},
    )

    assert response.status_code == 401


async def test_login_with_unknown_user_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": "ghost@bridge.com", "password": "whatever"},
    )

    assert response.status_code == 401


async def test_issued_token_is_accepted_by_protected_route(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_admin(db_session)

    login = await client.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    token = login.json()["access_token"]

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == ADMIN_EMAIL
    assert body["role"] == "admin"


async def test_protected_route_rejects_missing_token(client: AsyncClient) -> None:
    response = await client.get("/auth/me")
    assert response.status_code in {401, 403}


async def test_protected_route_rejects_invalid_token(client: AsyncClient) -> None:
    response = await client.get(
        "/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert response.status_code == 401


async def test_client_role_token_cannot_access_admin_route(
    client: AsyncClient,
) -> None:
    client_token = create_access_token("acme@example.com", role="client")

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {client_token}"}
    )

    assert response.status_code == 403
