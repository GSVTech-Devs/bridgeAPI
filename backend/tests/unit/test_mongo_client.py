# RED → GREEN
# Testes para app/core/mongo_client.py — lazy Motor client + get_mongo_db.
import pytest
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core import mongo_client
from app.core.config import settings


@pytest.fixture(autouse=True)
def _reset_mongo_global():
    mongo_client._client = None
    yield
    mongo_client._client = None


def test_get_client_returns_motor_client() -> None:
    client = mongo_client._get_client()
    assert isinstance(client, AsyncIOMotorClient)


def test_get_client_is_singleton() -> None:
    first = mongo_client._get_client()
    second = mongo_client._get_client()
    assert first is second


async def test_get_mongo_db_yields_database_with_configured_name() -> None:
    agen = mongo_client.get_mongo_db()
    db = await agen.__anext__()
    assert isinstance(db, AsyncIOMotorDatabase)
    assert db.name == settings.mongo_db
    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()
