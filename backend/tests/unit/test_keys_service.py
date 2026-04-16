# RED → GREEN
# Testes unitários para app/domains/keys/service.py.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import hash_password
from app.domains.clients.models import Client, ClientStatus
from app.domains.clients.service import ClientNotFoundError
from app.domains.keys.models import APIKey, APIKeyStatus
from app.domains.keys.service import (
    APIKeyNotFoundError,
    authenticate_api_key,
    create_api_key,
    list_api_keys,
    revoke_api_key,
)


def make_client(
    email: str = "acme@example.com",
    status: ClientStatus = ClientStatus.ACTIVE,
) -> Client:
    return Client(
        id=uuid.uuid4(),
        name="Acme Corp",
        email=email,
        password_hash="hashed-password",
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def make_api_key(
    client_id: uuid.UUID | None = None,
    status: APIKeyStatus = APIKeyStatus.ACTIVE,
    prefix: str = "abcd1234",
    secret_hash: str = "hashed-secret",
) -> APIKey:
    return APIKey(
        id=uuid.uuid4(),
        client_id=client_id or uuid.uuid4(),
        name="Production Key",
        key_prefix=prefix,
        key_secret_hash=secret_hash,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def make_execute_result(
    scalar_result=None,
    scalars_result=None,
) -> MagicMock:
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = scalar_result
    execute_result.scalars.return_value.all.return_value = scalars_result or []
    return execute_result


def make_db(*results: MagicMock) -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.side_effect = list(results)
    return db


@pytest.mark.asyncio
async def test_client_can_create_api_key() -> None:
    client = make_client()
    db = make_db(make_execute_result(scalar_result=client))

    api_key, plain_secret = await create_api_key(db, client.email, "Production Key")

    assert api_key.client_id == client.id
    assert api_key.name == "Production Key"
    assert plain_secret.startswith("brg_")
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_api_key_secret_is_hashed_in_db() -> None:
    client = make_client()
    db = make_db(make_execute_result(scalar_result=client))

    api_key, plain_secret = await create_api_key(db, client.email, "Production Key")

    assert api_key.key_secret_hash != plain_secret


@pytest.mark.asyncio
async def test_key_has_unique_prefix_and_secret() -> None:
    client = make_client()
    db = make_db(
        make_execute_result(scalar_result=client),
        make_execute_result(scalar_result=client),
    )

    first_key, first_secret = await create_api_key(db, client.email, "Key 1")
    second_key, second_secret = await create_api_key(db, client.email, "Key 2")

    assert first_key.key_prefix != second_key.key_prefix
    assert first_secret != second_secret


@pytest.mark.asyncio
async def test_client_can_revoke_own_key() -> None:
    client = make_client()
    api_key = make_api_key(client_id=client.id, status=APIKeyStatus.ACTIVE)
    db = make_db(
        make_execute_result(scalar_result=client),
        make_execute_result(scalar_result=api_key),
    )

    revoked_key = await revoke_api_key(db, client.email, str(api_key.id))

    assert revoked_key.status == APIKeyStatus.REVOKED
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(api_key)


@pytest.mark.asyncio
async def test_client_cannot_access_other_clients_keys() -> None:
    client = make_client()
    db = make_db(
        make_execute_result(scalar_result=client),
        make_execute_result(scalar_result=None),
    )

    with pytest.raises(APIKeyNotFoundError):
        await revoke_api_key(db, client.email, str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_revoked_key_cannot_be_used() -> None:
    plain_secret = "brg_abcd1234_super-secret-value"
    api_key = make_api_key(
        status=APIKeyStatus.REVOKED,
        prefix="abcd1234",
        secret_hash=hash_password(plain_secret),
    )
    db = make_db(make_execute_result(scalar_result=api_key))

    result = await authenticate_api_key(db, plain_secret)

    assert result is None


@pytest.mark.asyncio
async def test_list_api_keys_returns_only_current_client_keys() -> None:
    client = make_client()
    keys = [make_api_key(client_id=client.id), make_api_key(client_id=client.id)]
    db = make_db(
        make_execute_result(scalar_result=client),
        make_execute_result(scalars_result=keys),
    )

    result = await list_api_keys(db, client.email)

    assert len(result) == 2
    assert all(key.client_id == client.id for key in result)


# ---------------------------------------------------------------------------
# create_api_key — cliente inativo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_api_key_for_inactive_client_raises() -> None:
    pending_client = make_client(status=ClientStatus.PENDING)
    db = make_db(make_execute_result(scalar_result=pending_client))

    with pytest.raises(ClientNotFoundError):
        await create_api_key(db, pending_client.email, "Production Key")


# ---------------------------------------------------------------------------
# authenticate_api_key — cenários de rejeição por formato e senha
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authenticate_api_key_rejects_key_without_brg_prefix() -> None:
    db = make_db()
    result = await authenticate_api_key(db, "not-a-bridge-key")
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_api_key_rejects_malformed_key() -> None:
    db = make_db()
    # começa com brg_ mas não tem as 3 partes separadas por "_"
    result = await authenticate_api_key(db, "brg_onlyprefix")
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_api_key_rejects_wrong_secret() -> None:
    stored = make_api_key(
        status=APIKeyStatus.ACTIVE,
        prefix="abcd1234",
        secret_hash=hash_password("brg_abcd1234_correct-secret"),
    )
    db = make_db(make_execute_result(scalar_result=stored))

    result = await authenticate_api_key(db, "brg_abcd1234_wrong-secret")

    assert result is None


@pytest.mark.asyncio
async def test_authenticate_api_key_returns_key_on_valid_credentials() -> None:
    plain_secret = "brg_abcd1234_super-secret-value"
    stored = make_api_key(
        status=APIKeyStatus.ACTIVE,
        prefix="abcd1234",
        secret_hash=hash_password(plain_secret),
    )
    db = make_db(make_execute_result(scalar_result=stored))

    result = await authenticate_api_key(db, plain_secret)

    assert result is stored
