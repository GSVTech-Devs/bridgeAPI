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
    _filter_checks,
    get_client_overview,
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
# _filter_checks
# ---------------------------------------------------------------------------


def test_filter_checks_drops_proxy_when_disabled() -> None:
    checks = {"proxy": {"status": "down"}, "alvo": {"status": "healthy"}}
    out = _filter_checks(checks, uses_proxy=False, uses_captcha=True)
    assert out == {}  # proxy desativado e alvo é interno


def test_filter_checks_drops_captcha_and_mcaptcha_when_disabled() -> None:
    checks = {
        "mcaptcha": {"status": "healthy"},
        "captcha": {"status": "degraded"},
        "alvo": {"status": "healthy"},
    }
    out = _filter_checks(checks, uses_proxy=True, uses_captcha=False)
    assert out == {}  # captcha desativado e alvo é interno


def test_filter_checks_keeps_only_proxy_and_captcha_when_enabled() -> None:
    checks = {
        "proxy": {"status": "healthy"},
        "captcha": {"status": "healthy"},
        "alvo": {"status": "healthy"},
    }
    out = _filter_checks(checks, uses_proxy=True, uses_captcha=True)
    # alvo (check interno) sempre fica de fora, mesmo com tudo habilitado
    assert set(out.keys()) == {"proxy", "captcha"}


def test_filter_checks_always_drops_internal_target_check() -> None:
    out = _filter_checks({"alvo": {"status": "healthy"}}, uses_proxy=True, uses_captcha=True)
    assert out == {}


# ---------------------------------------------------------------------------
# get_client_overview
# ---------------------------------------------------------------------------


def make_api(api_id: str, name: str, uses_proxy=False, uses_captcha=False):
    api = MagicMock()
    api.id = uuid.UUID(api_id)
    api.name = name
    api.uses_proxy = uses_proxy
    api.uses_captcha = uses_captcha
    return api


def make_sa_db_scalars(apis):
    db = AsyncMock()
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = apis
    result.scalars.return_value = scalars
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_client_overview_filters_disabled_checks() -> None:
    aid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db, _ = make_mongo(latest_docs=[{
        "api_id": aid, "status": "healthy", "received_at": now,
        "checks": {"proxy": {"status": "down"}, "mcaptcha": {"status": "healthy"}, "alvo": {"status": "healthy"}},
    }])
    # API não usa proxy nem captcha; "alvo" é interno → nenhum check sobra.
    sa = make_sa_db_scalars([make_api(aid, "DETRAN-PA", uses_proxy=False, uses_captcha=False)])

    items = await get_client_overview(db, sa, uuid.uuid4())
    assert len(items) == 1
    assert items[0]["api_name"] == "DETRAN-PA"
    assert items[0]["checks"] == {}


@pytest.mark.asyncio
async def test_client_overview_api_without_heartbeat_is_unknown() -> None:
    aid = str(uuid.uuid4())
    db, _ = make_mongo(latest_docs=[])  # nenhum status reportado
    sa = make_sa_db_scalars([make_api(aid, "Sem Heartbeat", uses_proxy=True)])

    items = await get_client_overview(db, sa, uuid.uuid4())
    assert items[0]["status"] == "unknown"
    assert items[0]["checks"] == {}
    assert items[0]["uses_proxy"] is True


@pytest.mark.asyncio
async def test_client_overview_empty_when_no_authorized_apis() -> None:
    db, _ = make_mongo(latest_docs=[])
    sa = make_sa_db_scalars([])
    items = await get_client_overview(db, sa, uuid.uuid4())
    assert items == []


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
