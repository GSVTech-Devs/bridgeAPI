# RED → GREEN
# Testes para app/domains/auth/service.py — authenticate_user.
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import hash_password
from app.domains.auth.models import User
from app.domains.auth.service import authenticate_user


def _make_db_returning(user: User | None) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
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
