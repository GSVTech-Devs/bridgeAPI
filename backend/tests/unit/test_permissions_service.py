# Testes unitários para app/domains/permissions/service.py (escopo por account).
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.apis.models import APIAuthType, APIStatus, ExternalAPI
from app.domains.permissions.models import Permission
from app.domains.permissions.service import (
    DuplicatePermissionError,
    PermissionNotFoundError,
    get_account_authorized_apis,
    grant_permission,
    list_permissions,
    revoke_permission,
)


def make_api(status: APIStatus = APIStatus.ACTIVE) -> ExternalAPI:
    return ExternalAPI(
        id=uuid.uuid4(),
        name="Stripe API",
        base_url="https://api.stripe.com",
        master_key_encrypted="encrypted-key",
        auth_type=APIAuthType.API_KEY,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def make_permission(
    account_id: uuid.UUID | None = None,
    api_id: uuid.UUID | None = None,
    revoked_at: datetime | None = None,
) -> Permission:
    return Permission(
        id=uuid.uuid4(),
        account_id=account_id or uuid.uuid4(),
        api_id=api_id or uuid.uuid4(),
        granted_at=datetime.now(timezone.utc),
        revoked_at=revoked_at,
    )


def make_execute_result(scalar_result=None, scalars_result=None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_result
    result.scalars.return_value.all.return_value = scalars_result or []
    return result


def make_db(*results: MagicMock) -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.side_effect = list(results)
    return db


# ---------------------------------------------------------------------------
# grant_permission
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_grant_api_access_to_account() -> None:
    account_id, api_id = uuid.uuid4(), uuid.uuid4()
    db = make_db(make_execute_result(scalar_result=None))

    permission = await grant_permission(db, str(account_id), str(api_id))

    assert permission.account_id == account_id
    assert permission.api_id == api_id
    assert permission.revoked_at is None
    db.add.assert_called_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_duplicate_permission_raises_error() -> None:
    account_id, api_id = uuid.uuid4(), uuid.uuid4()
    existing = make_permission(account_id=account_id, api_id=api_id)
    db = make_db(make_execute_result(scalar_result=existing))

    with pytest.raises(DuplicatePermissionError):
        await grant_permission(db, str(account_id), str(api_id))


@pytest.mark.asyncio
async def test_grant_permission_reactivates_revoked_row() -> None:
    account_id, api_id = uuid.uuid4(), uuid.uuid4()
    revoked = make_permission(
        account_id=account_id, api_id=api_id, revoked_at=datetime.now(timezone.utc)
    )
    db = make_db(make_execute_result(scalar_result=revoked))

    result = await grant_permission(db, str(account_id), str(api_id))

    assert result is revoked
    assert result.revoked_at is None
    db.add.assert_not_called()
    db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# revoke_permission
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_revoke_api_access() -> None:
    permission = make_permission()
    db = make_db(make_execute_result(scalar_result=permission))

    revoked = await revoke_permission(
        db, str(permission.account_id), str(permission.api_id)
    )

    assert revoked.revoked_at is not None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_revoke_nonexistent_permission_raises_error() -> None:
    db = make_db(make_execute_result(scalar_result=None))
    with pytest.raises(PermissionNotFoundError):
        await revoke_permission(db, str(uuid.uuid4()), str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# get_account_authorized_apis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_account_sees_only_authorized_apis() -> None:
    db = make_db(make_execute_result(scalars_result=[make_api(), make_api()]))
    result = await get_account_authorized_apis(db, uuid.uuid4())
    assert len(result) == 2


@pytest.mark.asyncio
async def test_account_with_no_permissions_gets_empty_catalog() -> None:
    db = make_db(make_execute_result(scalars_result=[]))
    result = await get_account_authorized_apis(db, uuid.uuid4())
    assert result == []


# ---------------------------------------------------------------------------
# list_permissions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_permissions_returns_formatted_rows_with_status() -> None:
    acme_id, stripe_id = uuid.uuid4(), uuid.uuid4()
    other_id, gh_id = uuid.uuid4(), uuid.uuid4()

    active_row = MagicMock(
        account_id=acme_id,
        api_id=stripe_id,
        account_name="Acme Corp",
        api_name="Stripe API",
        revoked_at=None,
    )
    revoked_row = MagicMock(
        account_id=other_id,
        api_id=gh_id,
        account_name="Other Inc",
        api_name="GitHub API",
        revoked_at=datetime.now(timezone.utc),
    )

    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.fetchall.return_value = [active_row, revoked_row]
    db.execute.return_value = execute_result

    result = await list_permissions(db)

    assert result[0] == {
        "account_id": str(acme_id),
        "api_id": str(stripe_id),
        "account_name": "Acme Corp",
        "api_name": "Stripe API",
        "status": "active",
    }
    assert result[1]["status"] == "revoked"
