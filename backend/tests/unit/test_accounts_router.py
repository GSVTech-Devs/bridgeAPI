# Testes para o router admin de accounts (/admin/*).
# Banco mockado via dependency override; serviços mockados via patch.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.domains.accounts.models import Account, AccountStatus, AccountType
from app.domains.auth.models import User, UserRole


def make_account(
    type_: AccountType = AccountType.INDIVIDUAL,
    status: AccountStatus = AccountStatus.ACTIVE,
) -> Account:
    return Account(
        id=uuid.uuid4(),
        name="Acme Corp",
        type=type_,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def make_owner(account_id: uuid.UUID) -> User:
    return User(
        id=uuid.uuid4(),
        email="owner@example.com",
        password_hash="hashed",
        role=UserRole.OWNER,
        account_id=account_id,
    )


def admin_headers() -> dict:
    token = create_access_token("admin@bridge.com", role="admin")
    return {"Authorization": f"Bearer {token}"}


def owner_headers() -> dict:
    token = create_access_token(
        "owner@example.com",
        role="owner",
        extra_claims={"user_id": str(uuid.uuid4()), "account_id": str(uuid.uuid4())},
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /admin/users  (usuário avulso)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_creates_individual_user(client: AsyncClient) -> None:
    account = make_account(type_=AccountType.INDIVIDUAL)
    owner = make_owner(account.id)
    with patch(
        "app.domains.accounts.router.create_individual",
        new=AsyncMock(return_value=(account, owner)),
    ):
        response = await client.post(
            "/admin/users",
            json={
                "name": "Alice",
                "email": "owner@example.com",
                "password": "supersecret",
            },
            headers=admin_headers(),
        )
    assert response.status_code == 201
    body = response.json()
    assert body["account"]["type"] == "individual"
    assert body["owner_email"] == "owner@example.com"


@pytest.mark.asyncio
async def test_create_individual_requires_admin(client: AsyncClient) -> None:
    response = await client.post(
        "/admin/users",
        json={"name": "Alice", "email": "a@b.com", "password": "supersecret"},
        headers=owner_headers(),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_individual_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/admin/users",
        json={"name": "Alice", "email": "a@b.com", "password": "supersecret"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_individual_short_password_returns_422(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/admin/users",
        json={"name": "Alice", "email": "a@b.com", "password": "short"},
        headers=admin_headers(),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_individual_duplicate_email_returns_409(
    client: AsyncClient,
) -> None:
    from app.domains.auth.service import DuplicateEmailError

    with patch(
        "app.domains.accounts.router.create_individual",
        new=AsyncMock(side_effect=DuplicateEmailError),
    ):
        response = await client.post(
            "/admin/users",
            json={"name": "Alice", "email": "dup@b.com", "password": "supersecret"},
            headers=admin_headers(),
        )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# POST /admin/companies  (empresa + responsável)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_creates_company_with_owner(client: AsyncClient) -> None:
    account = make_account(type_=AccountType.COMPANY)
    owner = make_owner(account.id)
    with patch(
        "app.domains.accounts.router.create_company",
        new=AsyncMock(return_value=(account, owner)),
    ):
        response = await client.post(
            "/admin/companies",
            json={
                "company_name": "Globex",
                "owner_email": "owner@example.com",
                "owner_password": "supersecret",
            },
            headers=admin_headers(),
        )
    assert response.status_code == 201
    body = response.json()
    assert body["account"]["type"] == "company"
    assert body["owner_email"] == "owner@example.com"


@pytest.mark.asyncio
async def test_create_company_requires_admin(client: AsyncClient) -> None:
    response = await client.post(
        "/admin/companies",
        json={
            "company_name": "Globex",
            "owner_email": "o@b.com",
            "owner_password": "supersecret",
        },
        headers=owner_headers(),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /admin/accounts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_list_accounts(client: AsyncClient) -> None:
    accounts = [make_account(), make_account()]
    with patch(
        "app.domains.accounts.router.list_accounts",
        new=AsyncMock(return_value=(accounts, 2)),
    ):
        response = await client.get("/admin/accounts", headers=admin_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_list_accounts_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/admin/accounts")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /admin/accounts/{id}/block | /unblock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_block_account(client: AsyncClient) -> None:
    blocked = make_account(status=AccountStatus.BLOCKED)
    with patch(
        "app.domains.accounts.router.block_account",
        new=AsyncMock(return_value=blocked),
    ):
        response = await client.patch(
            f"/admin/accounts/{blocked.id}/block", headers=admin_headers()
        )
    assert response.status_code == 200
    assert response.json()["status"] == "blocked"


@pytest.mark.asyncio
async def test_block_nonexistent_account_returns_404(client: AsyncClient) -> None:
    from app.domains.accounts.service import AccountNotFoundError

    with patch(
        "app.domains.accounts.router.block_account",
        new=AsyncMock(side_effect=AccountNotFoundError),
    ):
        response = await client.patch(
            f"/admin/accounts/{uuid.uuid4()}/block", headers=admin_headers()
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unblock_active_account_returns_409(client: AsyncClient) -> None:
    from app.domains.accounts.service import InvalidStatusTransitionError

    with patch(
        "app.domains.accounts.router.unblock_account",
        new=AsyncMock(side_effect=InvalidStatusTransitionError("already active")),
    ):
        response = await client.patch(
            f"/admin/accounts/{uuid.uuid4()}/unblock", headers=admin_headers()
        )
    assert response.status_code == 409
