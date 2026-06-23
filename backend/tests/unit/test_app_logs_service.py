# Testes para as funções de leitura de logs estruturados e timeline unificada.
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.logs.service import (
    COLLECTION,
    APP_COLLECTION,
    get_app_logs,
    get_trace_by_correlation_id,
    mask_sensitive_values,
)


# ---------------------------------------------------------------------------
# mask_sensitive_values
# ---------------------------------------------------------------------------


def test_mask_sensitive_values_masks_brg_strings() -> None:
    assert mask_sensitive_values("brg_abc_secret") == "[MASKED]"


def test_mask_sensitive_values_recurses_into_dict_and_list() -> None:
    data = {"a": "ok", "b": ["brg_x_y", "fine"], "c": {"d": "brg_z_w"}}
    masked = mask_sensitive_values(data)
    assert masked == {"a": "ok", "b": ["[MASKED]", "fine"], "c": {"d": "[MASKED]"}}


def test_mask_sensitive_values_preserves_non_secrets() -> None:
    assert mask_sensitive_values("hello") == "hello"
    assert mask_sensitive_values(42) == 42


# ---------------------------------------------------------------------------
# get_app_logs
# ---------------------------------------------------------------------------


def make_app_collection(docs: list[dict] | None = None) -> tuple[MagicMock, MagicMock]:
    collection = MagicMock()
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=docs or [])
    collection.find.return_value = cursor
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=collection)
    return db, collection


@pytest.mark.asyncio
async def test_get_app_logs_filters_by_correlation_id() -> None:
    cid = str(uuid.uuid4())
    db, collection = make_app_collection()
    await get_app_logs(db, correlation_id=cid)
    collection.find.assert_called_once()
    assert collection.find.call_args[0][0]["correlation_id"] == cid


@pytest.mark.asyncio
async def test_get_app_logs_filters_by_level_and_error_code() -> None:
    db, collection = make_app_collection()
    await get_app_logs(db, level="ERROR", error_code="PROXY_AUTH_FAILED")
    query = collection.find.call_args[0][0]
    assert query["level"] == "ERROR"
    assert query["error_code"] == "PROXY_AUTH_FAILED"


@pytest.mark.asyncio
async def test_get_app_logs_respects_pagination() -> None:
    db, collection = make_app_collection()
    await get_app_logs(db, skip=15, limit=5)
    cursor = collection.find.return_value
    cursor.skip.assert_called_once_with(15)
    cursor.limit.assert_called_once_with(5)


# ---------------------------------------------------------------------------
# get_trace_by_correlation_id
# ---------------------------------------------------------------------------


def make_trace_db(
    gateway_docs: list[dict], app_docs: list[dict]
) -> MagicMock:
    gw = MagicMock()
    gw_cursor = MagicMock()
    gw_cursor.to_list = AsyncMock(return_value=gateway_docs)
    gw.find.return_value = gw_cursor

    appc = MagicMock()
    app_cursor = MagicMock()
    app_cursor.sort.return_value = app_cursor
    app_cursor.skip.return_value = app_cursor
    app_cursor.limit.return_value = app_cursor
    app_cursor.to_list = AsyncMock(return_value=app_docs)
    appc.find.return_value = app_cursor

    db = MagicMock()
    db.__getitem__ = MagicMock(
        side_effect=lambda name: gw if name == COLLECTION else appc
    )
    return db


@pytest.mark.asyncio
async def test_trace_merges_gateway_and_app_logs() -> None:
    cid = str(uuid.uuid4())
    base = datetime(2026, 6, 23, 12, 0, 0, tzinfo=timezone.utc)
    gateway = [{"correlation_id": cid, "created_at": base, "method": "POST"}]
    app_logs = [
        {"correlation_id": cid, "timestamp": base + timedelta(seconds=1), "event": "x"}
    ]
    db = make_trace_db(gateway, app_logs)

    timeline = await get_trace_by_correlation_id(db, cid)

    assert len(timeline) == 2
    assert {item["source"] for item in timeline} == {"gateway", "app"}


@pytest.mark.asyncio
async def test_trace_is_sorted_chronologically() -> None:
    cid = str(uuid.uuid4())
    base = datetime(2026, 6, 23, 12, 0, 0, tzinfo=timezone.utc)
    # gateway log acontece DEPOIS do primeiro app log
    gateway = [{"correlation_id": cid, "created_at": base + timedelta(seconds=5)}]
    app_logs = [
        {"correlation_id": cid, "timestamp": base + timedelta(seconds=1), "event": "a"},
        {"correlation_id": cid, "timestamp": base + timedelta(seconds=9), "event": "b"},
    ]
    db = make_trace_db(gateway, app_logs)

    timeline = await get_trace_by_correlation_id(db, cid)

    sources = [item["source"] for item in timeline]
    assert sources == ["app", "gateway", "app"]


@pytest.mark.asyncio
async def test_trace_empty_when_no_logs() -> None:
    db = make_trace_db([], [])
    assert await get_trace_by_correlation_id(db, "nope") == []
