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
    update_account_credentials,
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
        # get_users_by_email resolve a identidade como lista de linhas.
        er.scalars.return_value.all.return_value = [] if r is None else [r]
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
async def test_create_account_reuses_existing_identity_password() -> None:
    """Um email já existente (em outra conta) é reaproveitado: a nova conta
    nasce com a mesma senha da identidade (um email, uma senha)."""
    from app.domains.auth.models import User

    existing = User(
        email="boss@globex.com", password_hash="reused-hash", role="owner"
    )
    db = make_db(existing)
    account, owner = await create_company(
        db,
        company_name="Globex 2",
        owner_email="boss@globex.com",
        owner_password="ignored-password",
    )
    assert owner.email == "boss@globex.com"
    # reaproveita a credencial da identidade, ignorando a senha enviada
    assert owner.password_hash == "reused-hash"


@pytest.mark.asyncio
async def test_create_account_rejects_admin_email() -> None:
    """Um email de admin da plataforma não pode virar owner de conta."""
    from app.domains.auth.models import User

    existing = User(email="admin@bridge.com", password_hash="x", role="admin")
    db = make_db(existing)
    with pytest.raises(DuplicateEmailError):
        await create_individual(
            db, name="X", email="admin@bridge.com", password="supersecret"
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
    # list_accounts itera result.all() como linhas (account, owner)
    list_result.all.return_value = [(a, None) for a in accounts]
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


# ---------------------------------------------------------------------------
# update_account_credentials — identidade única (propaga senha / renomeia email)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_credentials_password_fans_out_to_email() -> None:
    """Trocar a senha do owner propaga para todas as linhas do email."""
    from app.domains.auth.models import User

    account = make_account()
    owner = User(email="owner@acme.com", password_hash="old", role="owner")
    db = AsyncMock()
    with (
        patch(
            "app.domains.accounts.service.get_account_by_id",
            new=AsyncMock(return_value=account),
        ),
        patch(
            "app.domains.accounts.service.get_account_owner",
            new=AsyncMock(return_value=owner),
        ),
        patch(
            "app.domains.accounts.service.set_password_for_email",
            new=AsyncMock(),
        ) as spfe,
    ):
        await update_account_credentials(db, str(account.id), password="NovaSenha1!")
    spfe.assert_awaited_once()
    # chamado com o email do owner e a nova senha
    args, kwargs = spfe.await_args
    assert args[1] == "owner@acme.com" and args[2] == "NovaSenha1!"


@pytest.mark.asyncio
async def test_update_credentials_email_rename_fans_out() -> None:
    """Trocar o email renomeia todas as linhas da identidade."""
    from app.domains.auth.models import User

    account = make_account()
    owner = User(email="old@acme.com", password_hash="h", role="owner")
    other = User(email="old@acme.com", password_hash="h", role="member")
    # 1ª chamada: checagem do email novo (livre); 2ª: linhas a renomear
    gube = AsyncMock(side_effect=[[], [owner, other]])
    with (
        patch(
            "app.domains.accounts.service.get_account_by_id",
            new=AsyncMock(return_value=account),
        ),
        patch(
            "app.domains.accounts.service.get_account_owner",
            new=AsyncMock(return_value=owner),
        ),
        patch("app.domains.accounts.service.get_users_by_email", new=gube),
    ):
        await update_account_credentials(db=AsyncMock(), account_id=str(account.id), email="new@acme.com")
    assert owner.email == "new@acme.com"
    assert other.email == "new@acme.com"


@pytest.mark.asyncio
async def test_update_credentials_email_collision_raises() -> None:
    from app.domains.auth.models import User

    account = make_account()
    owner = User(email="old@acme.com", password_hash="h", role="owner")
    # email novo já pertence a outra identidade
    gube = AsyncMock(return_value=[User(email="taken@acme.com", password_hash="x", role="owner")])
    with (
        patch(
            "app.domains.accounts.service.get_account_by_id",
            new=AsyncMock(return_value=account),
        ),
        patch(
            "app.domains.accounts.service.get_account_owner",
            new=AsyncMock(return_value=owner),
        ),
        patch("app.domains.accounts.service.get_users_by_email", new=gube),
    ):
        with pytest.raises(DuplicateEmailError):
            await update_account_credentials(
                db=AsyncMock(), account_id=str(account.id), email="taken@acme.com"
            )
