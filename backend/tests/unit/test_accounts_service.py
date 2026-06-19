# Testes unitários para app/domains/accounts/service.py.
# A AsyncSession é mockada — sem banco real.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domains.accounts.models import Account, AccountStatus, AccountType
from app.domains.accounts.service import (
    AccountNotFoundError,
    InvalidStatusTransitionError,
    block_account,
    create_company,
    create_individual,
    get_account_by_id,
    list_accounts,
    unblock_account,
)
from app.domains.auth.service import DuplicateEmailError


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


def make_db(*scalar_results) -> AsyncMock:
    """AsyncSession mock: cada execute() devolve scalar_one_or_none na ordem dada."""
    db = AsyncMock()
    db.add = MagicMock()
    results = []
    for r in scalar_results:
        er = MagicMock()
        er.scalar_one_or_none.return_value = r
        er.scalar_one.return_value = r if isinstance(r, int) else 0
        results.append(er)
    db.execute.side_effect = results or [MagicMock()]
    return db


# ---------------------------------------------------------------------------
# create_individual / create_company
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_individual_creates_account_and_owner() -> None:
    db = make_db(None)  # get_user_by_email → livre
    with patch("app.domains.accounts.service.hash_password", return_value="hashed"):
        account, owner = await create_individual(
            db, name="Alice", email="alice@example.com", password="supersecret"
        )
    assert account.type == AccountType.INDIVIDUAL
    assert account.status == AccountStatus.ACTIVE
    assert owner.role == "owner"
    assert owner.account_id == account.id
    assert owner.email == "alice@example.com"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_company_creates_company_account() -> None:
    db = make_db(None)
    with patch("app.domains.accounts.service.hash_password", return_value="hashed"):
        account, owner = await create_company(
            db,
            company_name="Globex",
            owner_email="boss@globex.com",
            owner_password="supersecret",
        )
    assert account.type == AccountType.COMPANY
    assert account.name == "Globex"
    assert owner.role == "owner"
    assert owner.account_id == account.id


@pytest.mark.asyncio
async def test_create_individual_rejects_duplicate_email() -> None:
    from app.domains.auth.models import User

    existing = User(email="alice@example.com", password_hash="x", role="owner")
    db = make_db(existing)  # get_user_by_email → já existe
    with pytest.raises(DuplicateEmailError):
        await create_individual(
            db, name="Alice", email="alice@example.com", password="supersecret"
        )


# ---------------------------------------------------------------------------
# get_account_by_id / list_accounts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_account_by_id_raises_when_missing() -> None:
    db = make_db(None)
    with pytest.raises(AccountNotFoundError):
        await get_account_by_id(db, str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_list_accounts_returns_items_and_total() -> None:
    accounts = [make_account(), make_account()]
    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 2
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = accounts
    db.execute.side_effect = [count_result, list_result]

    items, total = await list_accounts(db)

    assert total == 2
    assert len(items) == 2


# ---------------------------------------------------------------------------
# block / unblock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_block_active_account_sets_blocked() -> None:
    account = make_account(status=AccountStatus.ACTIVE)
    db = make_db(account)
    await block_account(db, str(account.id))
    assert account.status == AccountStatus.BLOCKED
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_block_already_blocked_raises() -> None:
    account = make_account(status=AccountStatus.BLOCKED)
    db = make_db(account)
    with pytest.raises(InvalidStatusTransitionError):
        await block_account(db, str(account.id))


@pytest.mark.asyncio
async def test_unblock_blocked_account_sets_active() -> None:
    account = make_account(status=AccountStatus.BLOCKED)
    db = make_db(account)
    await unblock_account(db, str(account.id))
    assert account.status == AccountStatus.ACTIVE


@pytest.mark.asyncio
async def test_unblock_active_account_raises() -> None:
    account = make_account(status=AccountStatus.ACTIVE)
    db = make_db(account)
    with pytest.raises(InvalidStatusTransitionError):
        await unblock_account(db, str(account.id))
