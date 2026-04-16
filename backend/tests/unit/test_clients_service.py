# RED → GREEN
# Testes unitários para app/domains/clients/service.py.
# A AsyncSession é mockada diretamente para cobrir a lógica de negócio
# sem necessidade de banco de dados real.
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domains.clients.models import Client, ClientStatus
from app.domains.clients.service import (
    ClientNotFoundError,
    DuplicateEmailError,
    InvalidStatusTransitionError,
    approve_client,
    authenticate_client,
    get_client_by_email,
    list_clients,
    register_client,
    reject_client,
)


def make_client(status: ClientStatus = ClientStatus.PENDING) -> Client:
    return Client(
        id=uuid.uuid4(),
        name="Acme Corp",
        email="acme@example.com",
        password_hash="hashed",
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def make_db(scalar_result=None, scalars_result=None, count_result=0) -> AsyncMock:
    """Constrói um mock de AsyncSession com resultado configurável."""
    db = AsyncMock()
    # db.add é síncrono no SQLAlchemy — evita warning de coroutine não aguardada
    db.add = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = scalar_result
    execute_result.scalar_one.return_value = count_result
    execute_result.scalars.return_value.all.return_value = scalars_result or []
    db.execute.return_value = execute_result
    return db


# ---------------------------------------------------------------------------
# register_client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_raises_on_duplicate_email() -> None:
    db = make_db(scalar_result=make_client())  # email já existe
    with pytest.raises(DuplicateEmailError):
        await register_client(db, "Acme", "acme@example.com", "pass")


@pytest.mark.asyncio
async def test_register_creates_and_commits_client() -> None:
    db = make_db(scalar_result=None)  # email livre
    with patch("app.domains.clients.service.hash_password", return_value="hashed"):
        await register_client(db, "Acme", "acme@example.com", "pass")
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once()


# ---------------------------------------------------------------------------
# list_clients
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_clients_returns_clients_and_total() -> None:
    clients = [make_client(), make_client()]
    db = make_db(scalars_result=clients, count_result=2)
    result, total = await list_clients(db)
    assert total == 2
    assert len(result) == 2


# ---------------------------------------------------------------------------
# approve_client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_pending_client_sets_status_active() -> None:
    pending = make_client(ClientStatus.PENDING)
    db = make_db(scalar_result=pending)
    await approve_client(db, str(pending.id))
    assert pending.status == ClientStatus.ACTIVE
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_approve_active_client_raises_invalid_transition() -> None:
    active = make_client(ClientStatus.ACTIVE)
    db = make_db(scalar_result=active)
    with pytest.raises(InvalidStatusTransitionError):
        await approve_client(db, str(active.id))


@pytest.mark.asyncio
async def test_approve_nonexistent_client_raises_not_found() -> None:
    db = make_db(scalar_result=None)
    with pytest.raises(ClientNotFoundError):
        await approve_client(db, str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# reject_client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_pending_client_sets_status_rejected() -> None:
    pending = make_client(ClientStatus.PENDING)
    db = make_db(scalar_result=pending)
    await reject_client(db, str(pending.id))
    assert pending.status == ClientStatus.REJECTED
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_reject_already_rejected_raises_invalid_transition() -> None:
    rejected = make_client(ClientStatus.REJECTED)
    db = make_db(scalar_result=rejected)
    with pytest.raises(InvalidStatusTransitionError):
        await reject_client(db, str(rejected.id))


# ---------------------------------------------------------------------------
# authenticate_client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authenticate_returns_client_on_correct_password() -> None:
    from app.core.security import hash_password

    client = make_client(ClientStatus.ACTIVE)
    client.password_hash = hash_password("correct")
    db = make_db(scalar_result=client)
    result = await authenticate_client(db, "acme@example.com", "correct")
    assert result is client


@pytest.mark.asyncio
async def test_authenticate_returns_none_on_wrong_password() -> None:
    from app.core.security import hash_password

    client = make_client(ClientStatus.ACTIVE)
    client.password_hash = hash_password("correct")
    db = make_db(scalar_result=client)
    result = await authenticate_client(db, "acme@example.com", "wrong")
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_returns_none_on_unknown_email() -> None:
    db = make_db(scalar_result=None)
    result = await authenticate_client(db, "unknown@example.com", "any")
    assert result is None


# ---------------------------------------------------------------------------
# get_client_by_email
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_client_by_email_returns_client_when_found() -> None:
    stored = make_client()
    db = make_db(scalar_result=stored)
    result = await get_client_by_email(db, "acme@example.com")
    assert result is stored


@pytest.mark.asyncio
async def test_get_client_by_email_raises_not_found() -> None:
    db = make_db(scalar_result=None)
    with pytest.raises(ClientNotFoundError):
        await get_client_by_email(db, "missing@example.com")
