# RED → GREEN
# Testes unitários para app/domains/logs/service.py.
# MongoDB é mockado com MagicMock + AsyncMock — nenhuma conexão real.
# Cobre mascaramento de dados sensíveis, gravação de logs e consulta paginada.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.logs.service import (
    SENSITIVE_HEADERS,
    generate_correlation_id,
    get_client_logs,
    mask_sensitive_headers,
    write_request_log,
)

# ---------------------------------------------------------------------------
# Helpers — mock de coleção MongoDB
# ---------------------------------------------------------------------------


def make_collection_mock(docs: list[dict] | None = None) -> AsyncMock:
    """Cria um mock de AsyncIOMotorCollection."""
    collection = MagicMock()
    collection.insert_one = AsyncMock(
        return_value=MagicMock(inserted_id="507f1f77bcf86cd799439011")
    )
    # Encadeia find().skip().limit().to_list()
    cursor = MagicMock()
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=docs or [])
    collection.find.return_value = cursor
    return collection


def make_mongo_db_mock(docs: list[dict] | None = None) -> tuple[MagicMock, MagicMock]:
    collection = make_collection_mock(docs)
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=collection)
    return db, collection


def make_log_data(
    correlation_id: str | None = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    return {
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "client_id": client_id or str(uuid.uuid4()),
        "api_id": str(uuid.uuid4()),
        "key_id": str(uuid.uuid4()),
        "path": "v1/charges",
        "method": "POST",
        "status_code": 200,
        "latency_ms": 42.5,
        "request_headers": {"content-type": "application/json"},
        "request_body": "",
        "response_headers": {"content-type": "application/json"},
        "response_body": '{"id": "ch_123"}',
    }


# ---------------------------------------------------------------------------
# generate_correlation_id
# ---------------------------------------------------------------------------


def test_each_request_gets_unique_correlation_id() -> None:
    id1 = generate_correlation_id()
    id2 = generate_correlation_id()
    assert id1 != id2


def test_correlation_id_is_valid_uuid() -> None:
    cid = generate_correlation_id()
    parsed = uuid.UUID(cid)  # levanta ValueError se inválido
    assert str(parsed) == cid


# ---------------------------------------------------------------------------
# mask_sensitive_headers — casos por header
# ---------------------------------------------------------------------------


def test_mask_sensitive_headers_masks_authorization() -> None:
    headers = {"authorization": "Bearer sk-super-secret"}
    masked = mask_sensitive_headers(headers)
    assert masked["authorization"] == "[MASKED]"


def test_mask_sensitive_headers_masks_x_api_key() -> None:
    headers = {"x-api-key": "sk-plaintext-key"}
    masked = mask_sensitive_headers(headers)
    assert masked["x-api-key"] == "[MASKED]"


def test_mask_sensitive_headers_masks_x_bridge_key() -> None:
    headers = {"x-bridge-key": "brg_abcd_secret"}
    masked = mask_sensitive_headers(headers)
    assert masked["x-bridge-key"] == "[MASKED]"


def test_mask_sensitive_headers_masks_cookie() -> None:
    headers = {"cookie": "session=abc123"}
    masked = mask_sensitive_headers(headers)
    assert masked["cookie"] == "[MASKED]"


def test_mask_sensitive_headers_preserves_non_sensitive_headers() -> None:
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-request-id": "req-abc",
    }
    masked = mask_sensitive_headers(headers)
    assert masked == headers


def test_mask_sensitive_headers_case_insensitive() -> None:
    headers = {"Authorization": "Bearer token", "X-API-KEY": "secret"}
    masked = mask_sensitive_headers(headers)
    assert masked["Authorization"] == "[MASKED]"
    assert masked["X-API-KEY"] == "[MASKED]"


def test_mask_sensitive_headers_masks_brg_key_values() -> None:
    # qualquer valor que começa com brg_ é uma API key e deve ser mascarado
    headers = {"x-custom-header": "brg_abcd1234_super-secret-value"}
    masked = mask_sensitive_headers(headers)
    assert masked["x-custom-header"] == "[MASKED]"


def test_api_key_value_never_appears_in_plain_text() -> None:
    key_value = "brg_abc12345_this-is-the-real-secret"
    headers = {
        "x-bridge-key": key_value,
        "authorization": f"Bearer {key_value}",
        "x-forwarded-for": "127.0.0.1",
    }
    masked = mask_sensitive_headers(headers)
    for v in masked.values():
        assert key_value not in v


def test_all_expected_sensitive_headers_are_covered() -> None:
    expected = {"authorization", "x-api-key", "x-bridge-key", "cookie", "set-cookie"}
    assert expected.issubset(SENSITIVE_HEADERS)


# ---------------------------------------------------------------------------
# write_request_log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_request_log_inserts_document_to_mongodb() -> None:
    db, collection = make_mongo_db_mock()
    log_data = make_log_data()

    await write_request_log(db, log_data)

    collection.insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_write_request_log_includes_correlation_id() -> None:
    db, collection = make_mongo_db_mock()
    cid = str(uuid.uuid4())
    log_data = make_log_data(correlation_id=cid)

    await write_request_log(db, log_data)

    inserted_doc = collection.insert_one.call_args[0][0]
    assert inserted_doc["correlation_id"] == cid


@pytest.mark.asyncio
async def test_write_request_log_sets_created_at() -> None:
    db, collection = make_mongo_db_mock()
    before = datetime.now(timezone.utc)

    await write_request_log(db, make_log_data())

    inserted_doc = collection.insert_one.call_args[0][0]
    assert "created_at" in inserted_doc
    assert inserted_doc["created_at"] >= before


@pytest.mark.asyncio
async def test_logs_respect_retention_policy() -> None:
    from app.core.config import settings

    db, collection = make_mongo_db_mock()

    await write_request_log(db, make_log_data())

    inserted_doc = collection.insert_one.call_args[0][0]
    assert "expires_at" in inserted_doc
    delta = inserted_doc["expires_at"] - inserted_doc["created_at"]
    assert abs(delta.total_seconds() / 3600 - settings.log_retention_hours) < 1


@pytest.mark.asyncio
async def test_write_request_log_masks_sensitive_headers_before_storing() -> None:
    db, collection = make_mongo_db_mock()
    log_data = make_log_data()
    log_data["request_headers"] = {
        "authorization": "Bearer sk-secret",
        "x-bridge-key": "brg_abc_secret",
        "content-type": "application/json",
    }

    await write_request_log(db, log_data)

    inserted_doc = collection.insert_one.call_args[0][0]
    req_headers = inserted_doc["request_headers"]
    assert req_headers["authorization"] == "[MASKED]"
    assert req_headers["x-bridge-key"] == "[MASKED]"
    assert req_headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_api_key_never_appears_in_stored_log() -> None:
    db, collection = make_mongo_db_mock()
    raw_key = "brg_abcd1234_this-is-the-real-key"
    log_data = make_log_data()
    log_data["request_headers"]["x-bridge-key"] = raw_key

    await write_request_log(db, log_data)

    inserted_doc = collection.insert_one.call_args[0][0]
    doc_str = str(inserted_doc)
    assert raw_key not in doc_str


# ---------------------------------------------------------------------------
# get_client_logs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_client_logs_filters_by_client_id() -> None:
    client_id = str(uuid.uuid4())
    doc = {**make_log_data(client_id=client_id), "correlation_id": "cid-1"}
    db, collection = make_mongo_db_mock(docs=[doc])

    results = await get_client_logs(db, client_id)

    collection.find.assert_called_once_with({"client_id": client_id})
    assert len(results) == 1


@pytest.mark.asyncio
async def test_client_sees_only_own_logs() -> None:
    my_id = str(uuid.uuid4())
    other_id = str(uuid.uuid4())
    my_doc = make_log_data(client_id=my_id)
    db, collection = make_mongo_db_mock(docs=[my_doc])

    await get_client_logs(db, my_id)

    query_filter = collection.find.call_args[0][0]
    assert query_filter["client_id"] == my_id
    assert query_filter["client_id"] != other_id


@pytest.mark.asyncio
async def test_get_client_logs_respects_pagination() -> None:
    db, collection = make_mongo_db_mock()

    await get_client_logs(db, str(uuid.uuid4()), skip=20, limit=10)

    cursor = collection.find.return_value
    cursor.skip.assert_called_once_with(20)
    cursor.limit.assert_called_once_with(10)


@pytest.mark.asyncio
async def test_get_client_logs_returns_empty_for_new_client() -> None:
    db, collection = make_mongo_db_mock(docs=[])

    results = await get_client_logs(db, str(uuid.uuid4()))

    assert results == []
