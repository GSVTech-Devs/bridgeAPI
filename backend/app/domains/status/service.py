from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domains.apis.models import ExternalAPI

LATEST = "api_status_latest"      # um doc por api_id (estado atual)
HISTORY = "api_status_history"    # série temporal com TTL
EVENTS = "status_events"          # transições de status (alertas) com TTL

UNKNOWN = "unknown"


def _as_aware(dt: Any) -> datetime | None:
    if not isinstance(dt, datetime):
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def _api_name_map(db: AsyncSession, api_ids: list[str]) -> dict[str, str]:
    uuids: list[uuid.UUID] = []
    for raw in api_ids:
        try:
            uuids.append(uuid.UUID(str(raw)))
        except (ValueError, AttributeError, TypeError):
            continue
    if not uuids:
        return {}
    result = await db.execute(
        select(ExternalAPI.id, ExternalAPI.name).where(ExternalAPI.id.in_(uuids))
    )
    return {str(row.id): row.name for row in result.fetchall()}


async def record_status(
    mongo_db: Any,
    api_id: str,
    report: dict[str, Any],
) -> dict[str, Any]:
    """Persiste o status reportado por uma API: atualiza o estado atual, grava
    no histórico (TTL) e registra a transição se o status mudou."""
    now = datetime.now(timezone.utc)
    new_status = report.get("status", UNKNOWN)

    previous = await mongo_db[LATEST].find_one({"api_id": api_id})

    doc = {
        "api_id": api_id,
        "status": new_status,
        "sdk_version": report.get("sdk_version"),
        "uptime_s": report.get("uptime_s"),
        "checks": report.get("checks", {}),
        "received_at": now,
    }

    expires_at = now + timedelta(days=settings.status_history_retention_days)
    await mongo_db[HISTORY].insert_one({**doc, "expires_at": expires_at})
    await mongo_db[LATEST].replace_one({"api_id": api_id}, doc, upsert=True)

    if previous is not None and previous.get("status") != new_status:
        await mongo_db[EVENTS].insert_one(
            {
                "api_id": api_id,
                "from_status": previous.get("status", UNKNOWN),
                "to_status": new_status,
                "at": now,
                "expires_at": expires_at,
            }
        )

    return doc


async def get_overview(mongo_db: Any, db: AsyncSession) -> list[dict[str, Any]]:
    """Estado atual de todas as APIs que já reportaram, com nome e flag de
    defasagem (sem heartbeat recente → status efetivo 'unknown')."""
    docs = await mongo_db[LATEST].find({}).to_list(length=1000)
    names = await _api_name_map(db, [d["api_id"] for d in docs])
    now = datetime.now(timezone.utc)
    stale_after = settings.status_stale_after_seconds

    items: list[dict[str, Any]] = []
    for d in docs:
        last_seen = _as_aware(d.get("received_at"))
        stale = bool(last_seen and (now - last_seen).total_seconds() > stale_after)
        reported = d.get("status", UNKNOWN)
        items.append(
            {
                "api_id": d["api_id"],
                "api_name": names.get(d["api_id"]),
                "status": UNKNOWN if stale else reported,
                "reported_status": reported,
                "sdk_version": d.get("sdk_version"),
                "uptime_s": d.get("uptime_s"),
                "checks": d.get("checks", {}),
                "last_seen": d.get("received_at"),
                "stale": stale,
            }
        )
    items.sort(key=lambda i: (i["api_name"] or i["api_id"]).lower())
    return items


async def get_events(
    mongo_db: Any, db: AsyncSession, skip: int = 0, limit: int = 50
) -> list[dict[str, Any]]:
    """Transições de status recentes (saúde mudou) — superfície de alertas."""
    cursor = mongo_db[EVENTS].find({}).sort("at", -1)
    docs = await cursor.skip(skip).limit(limit).to_list(length=limit)
    names = await _api_name_map(db, [d["api_id"] for d in docs])
    return [{**d, "api_name": names.get(d["api_id"])} for d in docs]
