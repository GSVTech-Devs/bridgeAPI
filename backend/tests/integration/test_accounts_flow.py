"""Integration tests for account/user lifecycle (admin-only creation).

Exercises what mocked unit tests can't: the unique-email constraint on users
enforced by Postgres, account + owner persisted across requests, and the full
admin-create → portal-login chain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.domains.accounts.models import Account, AccountStatus, AccountType
from app.domains.auth.models import User, UserRole

from ._seed import admin_headers, seed_account

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_user_email_unique_constraint_is_enforced_by_postgres(
    db_session: AsyncSession,
) -> None:
    account, _ = await seed_account(db_session, email="dup@example.com")

    db_session.add(
        User(
            email="dup@example.com",
            password_hash=hash_password("x"),
            role=UserRole.MEMBER,
            account_id=account.id,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_admin_creates_individual_then_owner_can_portal_login(
    client: AsyncClient,
) -> None:
    created = await client.post(
        "/admin/users",
        json={"name": "Alice", "email": "alice@example.com", "password": "hunter2x"},
        headers=admin_headers(),
    )
    assert created.status_code == 201
    assert created.json()["account"]["type"] == "individual"

    login = await client.post(
        "/auth/portal/login",
        json={"email": "alice@example.com", "password": "hunter2x"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


async def test_admin_creates_company_with_owner(client: AsyncClient) -> None:
    created = await client.post(
        "/admin/companies",
        json={
            "company_name": "Globex",
            "owner_email": "boss@globex.com",
            "owner_password": "hunter2x",
        },
        headers=admin_headers(),
    )
    assert created.status_code == 201
    assert created.json()["account"]["type"] == "company"

    login = await client.post(
        "/auth/portal/login",
        json={"email": "boss@globex.com", "password": "hunter2x"},
    )
    assert login.status_code == 200


async def test_duplicate_email_returns_409(client: AsyncClient) -> None:
    payload = {"name": "Acme", "email": "acme@example.com", "password": "hunter2x"}
    first = await client.post("/admin/users", json=payload, headers=admin_headers())
    assert first.status_code == 201

    second = await client.post("/admin/users", json=payload, headers=admin_headers())
    assert second.status_code == 409


async def test_blocked_account_cannot_portal_login(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_account(
        db_session,
        email="blocked@example.com",
        status=AccountStatus.BLOCKED,
    )

    login = await client.post(
        "/auth/portal/login",
        json={"email": "blocked@example.com", "password": "hunter2"},
    )
    assert login.status_code == 403


async def test_admin_can_block_and_unblock_account(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    account, _ = await seed_account(db_session, email="acme@example.com")

    blocked = await client.patch(
        f"/admin/accounts/{account.id}/block", headers=admin_headers()
    )
    assert blocked.status_code == 200
    assert blocked.json()["status"] == AccountStatus.BLOCKED.value

    unblocked = await client.patch(
        f"/admin/accounts/{account.id}/unblock", headers=admin_headers()
    )
    assert unblocked.status_code == 200
    assert unblocked.json()["status"] == AccountStatus.ACTIVE.value


async def test_admin_list_accounts_returns_created_accounts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_account(
        db_session, name="Acme", email="a@example.com", type_=AccountType.INDIVIDUAL
    )
    await seed_account(
        db_session, name="Globex", email="b@example.com", type_=AccountType.COMPANY
    )

    response = await client.get("/admin/accounts", headers=admin_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["name"] for item in body["items"]} == {"Acme", "Globex"}


async def test_account_persists_with_correct_type(db_session: AsyncSession) -> None:
    account, owner = await seed_account(
        db_session, name="Globex", type_=AccountType.COMPANY
    )
    assert isinstance(account, Account)
    assert account.type == AccountType.COMPANY.value
    assert owner.account_id == account.id
    assert owner.role == UserRole.OWNER.value
