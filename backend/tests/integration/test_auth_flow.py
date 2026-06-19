"""Integration tests for the auth flow (admin + portal).

Exercises the full chain: real bcrypt hash persisted in Postgres, real JWT
signed with settings.app_secret_key, real HTTPBearer parsing, real role gate
and the separation between /auth/login (admin) and /auth/portal/login.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.core.security import hash_password
from app.domains.auth.models import User, UserRole

from ._seed import seed_account

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
        role=UserRole.ADMIN,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# /auth/login  (admin)
# ---------------------------------------------------------------------------


async def test_admin_login_with_valid_credentials_returns_jwt(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_admin(db_session)

    response = await client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_admin_login_with_wrong_password_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_admin(db_session)
    response = await client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"}
    )
    assert response.status_code == 401


async def test_admin_login_unknown_user_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login", json={"email": "ghost@bridge.com", "password": "whatever"}
    )
    assert response.status_code == 401


async def test_admin_token_accepted_by_me(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_admin(db_session)
    login = await client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    token = login.json()["access_token"]

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == ADMIN_EMAIL
    assert body["role"] == "admin"


async def test_me_rejects_missing_and_invalid_token(client: AsyncClient) -> None:
    assert (await client.get("/auth/me")).status_code in {401, 403}
    bad = await client.get(
        "/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert bad.status_code == 401


# ---------------------------------------------------------------------------
# /auth/portal/login  (account)
# ---------------------------------------------------------------------------


async def test_portal_login_returns_token_with_account_scope(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    account, _ = await seed_account(
        db_session, email="owner@acme.com", password="hunter2"
    )

    login = await client.post(
        "/auth/portal/login",
        json={"email": "owner@acme.com", "password": "hunter2"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["account_id"] == str(account.id)
    assert me.json()["role"] == "owner"


async def test_admin_cannot_login_via_portal(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_admin(db_session)
    response = await client.post(
        "/auth/portal/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 401


async def test_account_token_cannot_access_admin_route(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    account, _ = await seed_account(db_session, email="owner@acme.com")
    login = await client.post(
        "/auth/portal/login",
        json={"email": "owner@acme.com", "password": "hunter2"},
    )
    token = login.json()["access_token"]

    # rota admin-only
    response = await client.get(
        "/admin/accounts", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
