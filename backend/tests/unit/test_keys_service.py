# Testes unitários para app/domains/keys/service.py (escopo por account).
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import hash_password
from app.domains.accounts.models import Account, AccountStatus, AccountType
from app.domains.accounts.service import AccountNotFoundError
from app.domains.keys.models import APIKey, APIKeyStatus
from app.domains.keys.service import (
    APIKeyLimitExceededError,
    APIKeyNotFoundError,
    UnauthorizedApiError,
    authenticate_api_key,
    create_api_key,
    list_api_keys,
    revoke_api_key,
)


def make_account(status: AccountStatus = AccountStatus.ACTIVE) -> Account:
    return Account(
        id=uuid.uuid4(),
        name="Acme Corp",
        type=AccountType.INDIVIDUAL,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def make_api_key(
    account_id: uuid.UUID | None = None,
    api_id: uuid.UUID | None = None,
    status: APIKeyStatus = APIKeyStatus.ACTIVE,
    prefix: str = "abcd1234",
    secret_hash: str = "hashed-secret",
) -> APIKey:
    return APIKey(
        id=uuid.uuid4(),
        account_id=account_id or uuid.uuid4(),
        api_id=api_id,
        name="Production Key",
        key_prefix=prefix,
        key_secret_hash=secret_hash,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def make_execute_result(
    scalar_result=None,
    scalars_result=None,
    scalar_one_result=0,
) -> MagicMock:
    er = MagicMock()
    er.scalar_one_or_none.return_value = scalar_result
    er.scalar_one.return_value = scalar_one_result
    er.scalars.return_value.all.return_value = scalars_result or []
    return er


def make_db(*results: MagicMock) -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.side_effect = list(results)
    return db


def _permission(account_id: uuid.UUID, api_id: uuid.UUID):
    from app.domains.permissions.models import Permission

    return Permission(
        id=uuid.uuid4(),
        account_id=account_id,
        api_id=api_id,
        granted_at=datetime.now(timezone.utc),
        revoked_at=None,
    )


# ---------------------------------------------------------------------------
# create_api_key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_account_can_create_api_key() -> None:
    account = make_account()
    api_id = uuid.uuid4()
    db = make_db(
        make_execute_result(scalar_result=account),  # get_account_by_id
        make_execute_result(scalar_result=_permission(account.id, api_id)),
        make_execute_result(scalar_one_result=0),  # count < limit
    )

    api_key, plain_secret = await create_api_key(
        db, account.id, "Production Key", api_id=api_id
    )

    assert api_key.account_id == account.id
    assert api_key.api_id == api_id
    assert plain_secret.startswith("brg_")
    assert api_key.key_secret_hash != plain_secret
    db.add.assert_called_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_api_key_without_permission_raises() -> None:
    account = make_account()
    db = make_db(
        make_execute_result(scalar_result=account),
        make_execute_result(scalar_result=None),  # sem permissão
    )
    with pytest.raises(UnauthorizedApiError):
        await create_api_key(db, account.id, "Key", api_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_create_api_key_for_inactive_account_raises() -> None:
    blocked = make_account(status=AccountStatus.BLOCKED)
    db = make_db(make_execute_result(scalar_result=blocked))
    with pytest.raises(AccountNotFoundError):
        await create_api_key(db, blocked.id, "Key", api_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_create_api_key_over_limit_raises() -> None:
    account = make_account()
    api_id = uuid.uuid4()
    db = make_db(
        make_execute_result(scalar_result=account),
        make_execute_result(scalar_result=_permission(account.id, api_id)),
        make_execute_result(scalar_one_result=5),  # já no limite
    )
    with pytest.raises(APIKeyLimitExceededError):
        await create_api_key(db, account.id, "Key", api_id=api_id)


# ---------------------------------------------------------------------------
# revoke / list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_account_can_revoke_own_key() -> None:
    account = make_account()
    api_key = make_api_key(account_id=account.id, status=APIKeyStatus.ACTIVE)
    db = make_db(make_execute_result(scalar_result=api_key))

    revoked = await revoke_api_key(db, account.id, str(api_key.id))

    assert revoked.status == APIKeyStatus.REVOKED
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_revoke_missing_key_raises() -> None:
    account = make_account()
    db = make_db(make_execute_result(scalar_result=None))
    with pytest.raises(APIKeyNotFoundError):
        await revoke_api_key(db, account.id, str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_list_api_keys_returns_account_keys() -> None:
    account = make_account()
    keys = [
        make_api_key(account_id=account.id),
        make_api_key(account_id=account.id),
    ]
    db = make_db(make_execute_result(scalars_result=keys))

    result = await list_api_keys(db, account.id)

    assert len(result) == 2
    assert all(k.account_id == account.id for k, _ in result)


# ---------------------------------------------------------------------------
# authenticate_api_key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authenticate_api_key_rejects_non_brg_prefix() -> None:
    db = make_db()
    assert await authenticate_api_key(db, "not-a-bridge-key") is None


@pytest.mark.asyncio
async def test_authenticate_api_key_rejects_malformed_key() -> None:
    db = make_db()
    assert await authenticate_api_key(db, "brg_onlyprefix") is None


@pytest.mark.asyncio
async def test_authenticate_api_key_rejects_revoked_key() -> None:
    plain = "brg_abcd1234_super-secret-value"
    stored = make_api_key(
        status=APIKeyStatus.REVOKED, prefix="abcd1234", secret_hash=hash_password(plain)
    )
    db = make_db(make_execute_result(scalar_result=stored))
    assert await authenticate_api_key(db, plain) is None


@pytest.mark.asyncio
async def test_authenticate_api_key_rejects_wrong_secret() -> None:
    stored = make_api_key(
        status=APIKeyStatus.ACTIVE,
        prefix="abcd1234",
        secret_hash=hash_password("brg_abcd1234_correct"),
    )
    db = make_db(make_execute_result(scalar_result=stored))
    assert await authenticate_api_key(db, "brg_abcd1234_wrong") is None


@pytest.mark.asyncio
async def test_authenticate_api_key_returns_key_on_valid_credentials() -> None:
    plain = "brg_abcd1234_super-secret-value"
    stored = make_api_key(
        status=APIKeyStatus.ACTIVE, prefix="abcd1234", secret_hash=hash_password(plain)
    )
    db = make_db(make_execute_result(scalar_result=stored))
    assert await authenticate_api_key(db, plain) is stored
