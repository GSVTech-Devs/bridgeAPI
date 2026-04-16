# RED → GREEN
# Testes para app/core/database.py — lazy engine/session + get_db generator.
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core import database


@pytest.fixture(autouse=True)
def _reset_database_globals():
    """Garante isolamento entre testes resetando singletons lazy."""
    database._engine = None
    database._session_factory = None
    yield
    database._engine = None
    database._session_factory = None


def test_get_engine_returns_async_engine_instance() -> None:
    engine = database.get_engine()
    assert isinstance(engine, AsyncEngine)


def test_get_engine_is_singleton() -> None:
    first = database.get_engine()
    second = database.get_engine()
    assert first is second


def test_get_session_factory_returns_async_sessionmaker() -> None:
    factory = database.get_session_factory()
    assert isinstance(factory, async_sessionmaker)


def test_get_session_factory_is_singleton() -> None:
    first = database.get_session_factory()
    second = database.get_session_factory()
    assert first is second


async def test_get_db_yields_async_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_db deve ser um async generator que yields AsyncSession.

    Substituímos o session_factory por um mock para não exigir banco real.
    """
    fake_session = AsyncMock(spec=AsyncSession)

    class FakeFactory:
        def __call__(self):
            return _FakeContext(fake_session)

    class _FakeContext:
        def __init__(self, session):
            self._session = session

        async def __aenter__(self):
            return self._session

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr(database, "get_session_factory", lambda: FakeFactory())

    agen = database.get_db()
    session = await agen.__anext__()
    assert session is fake_session

    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()
