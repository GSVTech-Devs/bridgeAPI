# Testes unitários para app/domains/status/service.py.
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.status.service import (
    EVENTS,
    HISTORY,
    LATEST,
    get_events,
    get_overview,
    record_status,
)


def make_mongo(previous=None, latest_docs=None, event_docs=None):
    latest = MagicMock()
    latest.find_one = AsyncMock(return_value=previous)
    latest.replace_one = AsyncMock()
    lcur = MagicMock()
    lcur.to_list = AsyncMock(return_value=latest_docs or [])
    latest.find.return_value = lcur

    history = MagicMock()
    history.insert_one = AsyncMock()

    events = MagicMock()
    events.insert_one = AsyncMock()
    ecur = MagicMock()
    ecur.sort.return_value = ecur
    ecur.skip.return_value = ecur
    ecur.limit.return_value = ecur
    ecur.to_list = AsyncMock(return_value=event_docs or [])
    events.find.return_value = ecur

    mapping = {LATEST: latest, HISTORY: history, EVENTS: events}
    db = MagicMock()
    db.__getitem__ = MagicMock(side_effect=lambda n: mapping[n])
    return db, mapping


def make_sa_db(name_rows=None):
    db = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = name_rows or []
    db.execute = AsyncMock(return_value=result)
    return db


def name_row(api_id: str, name: str):
    row = MagicMock()
    row.id = uuid.UUID(api_id)
    row.name = name
    return row


# ---------------------------------------------------------------------------
# record_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_status_writes_history_and_latest() -> None:
    db, m = make_mongo(previous=None)
    await record_status(db, "api-1", {"status": "healthy", "sdk_version": "1.0", "checks": {}})

    m[HISTORY].insert_one.assert_awaited_once()
    m[LATEST].replace_one.assert_awaited_once()
    assert m[LATEST].replace_one.call_args.kwargs.get("upsert") is True
    m[EVENTS].insert_one.assert_not_called()  # sem estado anterior, sem transição


@pytest.mark.asyncio
async def test_record_status_logs_transition_event() -> None:
    db, m = make_mongo(previous={"status": "healthy"})
    await record_status(db, "api-1", {"status": "down"})

    m[EVENTS].insert_one.assert_awaited_once()
    event = m[EVENTS].insert_one.call_args[0][0]
    assert event["from_status"] == "healthy"
    assert event["to_status"] == "down"


@pytest.mark.asyncio
async def test_record_status_no_event_when_unchanged() -> None:
    db, m = make_mongo(previous={"status": "healthy"})
    await record_status(db, "api-1", {"status": "healthy"})
    m[EVENTS].insert_one.assert_not_called()


# ---------------------------------------------------------------------------
# get_overview
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_overview_marks_recent_as_not_stale() -> None:
    aid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db, _ = make_mongo(latest_docs=[{"api_id": aid, "status": "healthy", "received_at": now, "checks": {}}])
    sa = make_sa_db([name_row(aid, "Serasa API")])

    items = await get_overview(db, sa)
    assert len(items) == 1
    assert items[0]["api_name"] == "Serasa API"
    assert items[0]["status"] == "healthy"
    assert items[0]["stale"] is False


@pytest.mark.asyncio
async def test_overview_marks_old_heartbeat_as_stale_unknown() -> None:
    aid = str(uuid.uuid4())
    old = datetime.now(timezone.utc) - timedelta(seconds=10_000)
    db, _ = make_mongo(latest_docs=[{"api_id": aid, "status": "healthy", "received_at": old, "checks": {}}])
    sa = make_sa_db([name_row(aid, "X")])

    items = await get_overview(db, sa)
    assert items[0]["stale"] is True
    assert items[0]["status"] == "unknown"
    assert items[0]["reported_status"] == "healthy"


# ---------------------------------------------------------------------------
# get_events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_events_enriches_names() -> None:
    aid = str(uuid.uuid4())
    db, m = make_mongo(event_docs=[{"api_id": aid, "from_status": "healthy", "to_status": "down"}])
    sa = make_sa_db([name_row(aid, "Y API")])

    events = await get_events(db, sa)
    assert events[0]["api_name"] == "Y API"
    m[EVENTS].find.return_value.sort.assert_called_once_with("at", -1)
