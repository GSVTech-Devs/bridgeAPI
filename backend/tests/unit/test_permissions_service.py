# RED → GREEN
# Testes unitários para app/domains/permissions/service.py.
# A AsyncSession é mockada diretamente para cobrir a lógica de negócio
# sem necessidade de banco de dados real.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.apis.models import APIAuthType, APIStatus, ExternalAPI
from app.domains.clients.models import Client, ClientStatus
from app.domains.permissions.models import Permission
from app.domains.permissions.service import (
    DuplicatePermissionError,
    PermissionNotFoundError,
    get_client_authorized_apis,
    grant_permission,
    list_permissions,
    revoke_permission,
)


def make_client(status: ClientStatus = ClientStatus.ACTIVE) -> Client:
    return Client(
        id=uuid.uuid4(),
        name="Acme Corp",
        email="acme@example.com",
        password_hash="hashed-password",
        status=status,
        created_at=datetime.now(timezone.utc),
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
    client_id: uuid.UUID | None = None,
    api_id: uuid.UUID | None = None,
    revoked_at: datetime | None = None,
) -> Permission:
    return Permission(
        id=uuid.uuid4(),
        client_id=client_id or uuid.uuid4(),
        api_id=api_id or uuid.uuid4(),
        granted_at=datetime.now(timezone.utc),
        revoked_at=revoked_at,
    )


def make_execute_result(
    scalar_result=None,
    scalars_result=None,
) -> MagicMock:
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
async def test_admin_can_grant_api_access_to_client() -> None:
    client = make_client()
    api = make_api()
    # nenhuma permissão existente → pode criar
    db = make_db(make_execute_result(scalar_result=None))

    permission = await grant_permission(db, str(client.id), str(api.id))

    assert permission.client_id == client.id
    assert permission.api_id == api.id
    assert permission.granted_at is not None
    assert permission.revoked_at is None
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_duplicate_permission_raises_error() -> None:
    client = make_client()
    api = make_api()
    existing = make_permission(client_id=client.id, api_id=api.id)
    # permissão ativa já existe
    db = make_db(make_execute_result(scalar_result=existing))

    with pytest.raises(DuplicatePermissionError):
        await grant_permission(db, str(client.id), str(api.id))


@pytest.mark.asyncio
async def test_grant_permission_stores_correct_ids() -> None:
    client = make_client()
    api = make_api()
    db = make_db(make_execute_result(scalar_result=None))

    await grant_permission(db, str(client.id), str(api.id))

    added: Permission = db.add.call_args[0][0]
    assert added.client_id == client.id
    assert added.api_id == api.id


# ---------------------------------------------------------------------------
# revoke_permission
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_revoke_api_access() -> None:
    client = make_client()
    api = make_api()
    permission = make_permission(client_id=client.id, api_id=api.id)
    db = make_db(make_execute_result(scalar_result=permission))

    revoked = await revoke_permission(db, str(client.id), str(api.id))

    assert revoked.revoked_at is not None
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_revoke_nonexistent_permission_raises_error() -> None:
    db = make_db(make_execute_result(scalar_result=None))

    with pytest.raises(PermissionNotFoundError):
        await revoke_permission(db, str(uuid.uuid4()), str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_revoke_already_revoked_permission_raises_error() -> None:
    permission = make_permission(revoked_at=datetime.now(timezone.utc))
    # query filtra revoked_at IS NULL — nenhum resultado
    db = make_db(make_execute_result(scalar_result=None))

    with pytest.raises(PermissionNotFoundError):
        await revoke_permission(db, str(permission.client_id), str(permission.api_id))


# ---------------------------------------------------------------------------
# get_client_authorized_apis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_sees_only_authorized_apis_in_catalog() -> None:
    acme = make_client()
    api1, api2 = make_api(), make_api()
    db = make_db(
        make_execute_result(scalar_result=acme),
        make_execute_result(scalars_result=[api1, api2]),
    )

    result = await get_client_authorized_apis(db, acme.email)

    assert len(result) == 2


@pytest.mark.asyncio
async def test_revoked_permission_hides_api_from_catalog() -> None:
    # serviço filtra via JOIN onde revoked_at IS NULL — mock retorna lista vazia
    acme = make_client()
    db = make_db(
        make_execute_result(scalar_result=acme),
        make_execute_result(scalars_result=[]),
    )

    result = await get_client_authorized_apis(db, acme.email)

    assert result == []


@pytest.mark.asyncio
async def test_client_with_no_permissions_gets_empty_catalog() -> None:
    acme = make_client()
    db = make_db(
        make_execute_result(scalar_result=acme),
        make_execute_result(scalars_result=[]),
    )

    result = await get_client_authorized_apis(db, acme.email)

    assert result == []


# ---------------------------------------------------------------------------
# list_permissions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_permissions_returns_formatted_rows_with_status() -> None:
    acme_id, stripe_id = uuid.uuid4(), uuid.uuid4()
    other_id, gh_id = uuid.uuid4(), uuid.uuid4()

    active_row = MagicMock(
        client_id=acme_id,
        api_id=stripe_id,
        client_name="Acme Corp",
        api_name="Stripe API",
        revoked_at=None,
    )
    revoked_row = MagicMock(
        client_id=other_id,
        api_id=gh_id,
        client_name="Other Inc",
        api_name="GitHub API",
        revoked_at=datetime.now(timezone.utc),
    )

    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.fetchall.return_value = [active_row, revoked_row]
    db.execute.return_value = execute_result

    result = await list_permissions(db)

    assert len(result) == 2
    assert result[0] == {
        "client_id": str(acme_id),
        "api_id": str(stripe_id),
        "client_name": "Acme Corp",
        "api_name": "Stripe API",
        "status": "active",
    }
    assert result[1]["status"] == "revoked"
