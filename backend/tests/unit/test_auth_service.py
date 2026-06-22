# RED → GREEN
# Testes para app/domains/auth/service.py — authenticate_user e identidade
# multi-conta (um email, uma senha).
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.security import hash_password, verify_password
from app.domains.auth.models import User
from app.domains.auth.service import (
    InvalidCurrentPasswordError,
    authenticate_user,
    change_user_password,
    get_account_user,
    get_users_by_email,
    set_password_for_email,
)


def _make_db_returning(user: User | None) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    # authenticate_user resolve a identidade via get_users_by_email (lista).
    result.scalars.return_value.all.return_value = [] if user is None else [user]
    db.execute.return_value = result
    return db


@pytest.mark.asyncio
async def test_authenticate_user_returns_user_when_credentials_match() -> None:
    stored = User(
        email="admin@bridge.com",
        password_hash=hash_password("secret123"),
        role="admin",
    )
    db = _make_db_returning(stored)

    result = await authenticate_user(db, "admin@bridge.com", "secret123")

    assert result is stored
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_authenticate_user_returns_none_when_password_wrong() -> None:
    stored = User(
        email="admin@bridge.com",
        password_hash=hash_password("secret123"),
        role="admin",
    )
    db = _make_db_returning(stored)

    result = await authenticate_user(db, "admin@bridge.com", "wrong-password")

    assert result is None


@pytest.mark.asyncio
async def test_authenticate_user_returns_none_when_user_not_found() -> None:
    db = _make_db_returning(None)

    result = await authenticate_user(db, "unknown@bridge.com", "whatever")

    assert result is None


# ---------------------------------------------------------------------------
# Identidade multi-conta: get_users_by_email / set_password_for_email
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_users_by_email_returns_all_rows() -> None:
    rows = [
        User(email="multi@acme.com", password_hash="h", role="owner"),
        User(email="multi@acme.com", password_hash="h", role="member"),
    ]
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    db.execute.return_value = result

    assert await get_users_by_email(db, "multi@acme.com") == rows


@pytest.mark.asyncio
async def test_set_password_for_email_updates_every_row() -> None:
    rows = [
        User(email="multi@acme.com", password_hash="old", role="owner"),
        User(email="multi@acme.com", password_hash="old", role="member"),
    ]
    db = AsyncMock()
    with patch(
        "app.domains.auth.service.get_users_by_email",
        new=AsyncMock(return_value=rows),
    ):
        await set_password_for_email(db, "multi@acme.com", "NovaSenha1!")
    # ambas as linhas recebem o MESMO hash, e nenhuma é o antigo
    assert rows[0].password_hash == rows[1].password_hash != "old"
    assert verify_password("NovaSenha1!", rows[0].password_hash)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_change_user_password_validates_current_and_propagates() -> None:
    user = User(email="multi@acme.com", password_hash=hash_password("Atual123!"), role="owner")
    db = AsyncMock()
    with (
        patch(
            "app.domains.auth.service.get_user_by_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.domains.auth.service.set_password_for_email", new=AsyncMock()
        ) as spfe,
    ):
        await change_user_password(
            db, user_id=user.id, current_password="Atual123!", new_password="Nova123!"
        )
    spfe.assert_awaited_once()
    args, _ = spfe.await_args
    assert args[1] == "multi@acme.com" and args[2] == "Nova123!"


@pytest.mark.asyncio
async def test_change_user_password_wrong_current_raises() -> None:
    user = User(email="multi@acme.com", password_hash=hash_password("Atual123!"), role="owner")
    db = AsyncMock()
    with patch(
        "app.domains.auth.service.get_user_by_id",
        new=AsyncMock(return_value=user),
    ):
        with pytest.raises(InvalidCurrentPasswordError):
            await change_user_password(
                db, user_id=user.id, current_password="errada", new_password="Nova123!"
            )


@pytest.mark.asyncio
async def test_get_account_user_returns_row_for_account() -> None:
    row = User(email="x@acme.com", password_hash="h", role="member")
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    db.execute.return_value = result

    import uuid

    assert await get_account_user(db, uuid.uuid4(), "x@acme.com") is row
