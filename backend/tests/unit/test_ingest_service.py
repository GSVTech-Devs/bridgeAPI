# Testes unitários para app/domains/ingest/service.py.
# Service token (geração/autenticação) e escrita em lote de logs estruturados.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domains.apis.models import ExternalAPI
from app.domains.ingest.service import (
    SERVICE_TOKEN_PREFIX,
    authenticate_service_token,
    generate_service_token,
    write_app_logs,
)


def make_api() -> ExternalAPI:
    api = ExternalAPI(name=f"api-{uuid.uuid4()}", base_url="https://up.example.com")
    api.id = uuid.uuid4()
    return api


def make_db_returning(api: ExternalAPI | None) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = api
    db.execute = AsyncMock(return_value=result)
    return db


# ---------------------------------------------------------------------------
# generate_service_token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_service_token_sets_prefix_and_hash() -> None:
    api = make_api()
    db = AsyncMock()
    with patch(
        "app.domains.ingest.service.get_api_by_id",
        new=AsyncMock(return_value=api),
    ):
        returned, raw = await generate_service_token(db, str(api.id))

    assert returned is api
    assert raw.startswith(f"{SERVICE_TOKEN_PREFIX}_")
    assert api.service_token_prefix and api.service_token_prefix in raw
    assert api.service_token_hash is not None
    assert raw not in api.service_token_hash  # token bruto não é persistido
    db.commit.assert_awaited()


# ---------------------------------------------------------------------------
# authenticate_service_token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authenticate_round_trip() -> None:
    api = make_api()
    with patch(
        "app.domains.ingest.service.get_api_by_id",
        new=AsyncMock(return_value=api),
    ):
        _, raw = await generate_service_token(AsyncMock(), str(api.id))

    db = make_db_returning(api)
    resolved = await authenticate_service_token(db, raw)
    assert resolved is api


@pytest.mark.asyncio
async def test_authenticate_rejects_wrong_secret() -> None:
    api = make_api()
    with patch(
        "app.domains.ingest.service.get_api_by_id",
        new=AsyncMock(return_value=api),
    ):
        _, raw = await generate_service_token(AsyncMock(), str(api.id))

    prefix = api.service_token_prefix
    forged = f"{SERVICE_TOKEN_PREFIX}_{prefix}_wrong-secret-value"
    db = make_db_returning(api)
    assert await authenticate_service_token(db, forged) is None


@pytest.mark.asyncio
async def test_authenticate_rejects_malformed_token() -> None:
    db = make_db_returning(None)
    assert await authenticate_service_token(db, "not-a-token") is None
    assert await authenticate_service_token(db, "brgsvc_only") is None


@pytest.mark.asyncio
async def test_authenticate_unknown_prefix_returns_none() -> None:
    db = make_db_returning(None)
    token = f"{SERVICE_TOKEN_PREFIX}_deadbeef_some-secret-value"
    assert await authenticate_service_token(db, token) is None


# ---------------------------------------------------------------------------
# write_app_logs
# ---------------------------------------------------------------------------


def make_mongo_db_mock(inserted: int = 2) -> tuple[MagicMock, MagicMock]:
    collection = MagicMock()
    collection.insert_many = AsyncMock(
        return_value=MagicMock(inserted_ids=list(range(inserted)))
    )
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=collection)
    return db, collection


def make_entry() -> dict:
    return {
        "timestamp": datetime.now(timezone.utc),
        "level": "INFO",
        "correlation_id": str(uuid.uuid4()),
        "event": "request.received",
        "message": "ok",
        "extra": {},
    }


@pytest.mark.asyncio
async def test_write_app_logs_inserts_many_and_returns_count() -> None:
    db, collection = make_mongo_db_mock(inserted=2)
    count = await write_app_logs(db, "api-1", [make_entry(), make_entry()])
    assert count == 2
    collection.insert_many.assert_awaited_once()


@pytest.mark.asyncio
async def test_write_app_logs_stamps_api_id_from_token() -> None:
    db, collection = make_mongo_db_mock(inserted=1)
    await write_app_logs(db, "api-from-token", [make_entry()])
    docs = collection.insert_many.call_args[0][0]
    assert all(d["api_id"] == "api-from-token" for d in docs)
    assert all("created_at" in d and "expires_at" in d for d in docs)


@pytest.mark.asyncio
async def test_write_app_logs_masks_secrets_in_extra() -> None:
    db, collection = make_mongo_db_mock(inserted=1)
    entry = make_entry()
    entry["extra"] = {"key": "brg_abcd1234_super-secret"}
    await write_app_logs(db, "api-1", [entry])
    docs = collection.insert_many.call_args[0][0]
    assert docs[0]["extra"]["key"] == "[MASKED]"


@pytest.mark.asyncio
async def test_write_app_logs_empty_returns_zero() -> None:
    db, collection = make_mongo_db_mock()
    assert await write_app_logs(db, "api-1", []) == 0
    collection.insert_many.assert_not_called()
