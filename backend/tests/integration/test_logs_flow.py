"""Integration tests for request logs against real MongoDB.

Validates what mocks can't: Motor insert_one/find round-trip through Mongo,
sensitive headers are masked in the persisted document, created_at/expires_at
are stored with the configured TTL, and /logs filters by the authenticated
account plus honors pagination at the query level.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

from app.core.config import settings
from app.domains.logs.service import (
    COLLECTION,
    generate_correlation_id,
    write_request_log,
)

from ._seed import account_headers, seed_account

if TYPE_CHECKING:
    from httpx import AsyncClient
    from motor.motor_asyncio import AsyncIOMotorDatabase
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


def _log_payload(account_id: str, path: str = "/v1/charges") -> dict:
    return {
        "correlation_id": generate_correlation_id(),
        "client_id": account_id,
        "api_id": str(uuid.uuid4()),
        "key_id": str(uuid.uuid4()),
        "path": path,
        "method": "POST",
        "status_code": 200,
        "latency_ms": 42.0,
        "request_headers": {
            "Authorization": "Bearer secret-jwt-xyz",
            "X-Api-Key": "brg_sensitive_key",
            "Content-Type": "application/json",
        },
        "response_headers": {"Set-Cookie": "session=abc", "X-Request-Id": "rid-123"},
    }


def _as_object_id(value: str):
    from bson import ObjectId

    return ObjectId(value)


async def test_write_request_log_masks_sensitive_and_stores_ttl(
    mongo_db_integration: AsyncIOMotorDatabase,
) -> None:
    before = datetime.now(timezone.utc)
    inserted_id = await write_request_log(mongo_db_integration, _log_payload("acc-1"))

    doc = await mongo_db_integration[COLLECTION].find_one(
        {"_id": _as_object_id(inserted_id)}
    )
    assert doc is not None
    assert doc["request_headers"]["Authorization"] == "[MASKED]"
    assert doc["request_headers"]["X-Api-Key"] == "[MASKED]"
    assert doc["request_headers"]["Content-Type"] == "application/json"
    assert doc["response_headers"]["Set-Cookie"] == "[MASKED]"

    assert doc["created_at"] >= before.replace(tzinfo=None) - timedelta(seconds=1)
    delta = doc["expires_at"] - doc["created_at"]
    assert delta == timedelta(hours=settings.log_retention_hours)


async def test_list_logs_returns_only_authenticated_accounts_logs(
    client: AsyncClient,
    db_session: AsyncSession,
    mongo_db_integration: AsyncIOMotorDatabase,
) -> None:
    owner, _ = await seed_account(db_session, email="owner@example.com")
    other, _ = await seed_account(db_session, email="other@example.com")

    await write_request_log(mongo_db_integration, _log_payload(str(owner.id)))
    await write_request_log(mongo_db_integration, _log_payload(str(owner.id)))
    await write_request_log(mongo_db_integration, _log_payload(str(other.id)))

    response = await client.get("/logs", headers=account_headers(owner.id))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    for item in body["items"]:
        assert item["client_id"] == str(owner.id)


async def test_list_logs_honors_skip_and_limit_at_query_level(
    client: AsyncClient,
    db_session: AsyncSession,
    mongo_db_integration: AsyncIOMotorDatabase,
) -> None:
    owner, _ = await seed_account(db_session, email="owner@example.com")
    # created_at distinto e decrescente garante ordenação determinística entre páginas
    base = datetime.now(timezone.utc)
    for i in range(5):
        doc = _log_payload(str(owner.id), path=f"/v1/op/{i}")
        doc["created_at"] = base - timedelta(seconds=i)
        await mongo_db_integration[COLLECTION].insert_one(doc)

    page_one = await client.get(
        "/logs", params={"skip": 0, "limit": 2}, headers=account_headers(owner.id)
    )
    page_two = await client.get(
        "/logs", params={"skip": 2, "limit": 2}, headers=account_headers(owner.id)
    )

    assert page_one.json()["total"] == 2
    assert page_two.json()["total"] == 2
    p1 = {item["path"] for item in page_one.json()["items"]}
    p2 = {item["path"] for item in page_two.json()["items"]}
    assert p1.isdisjoint(p2)


async def test_list_logs_empty_when_account_has_none(
    client: AsyncClient,
    db_session: AsyncSession,
    mongo_db_integration: AsyncIOMotorDatabase,
) -> None:
    someone, _ = await seed_account(db_session, email="someone@example.com")
    newcomer, _ = await seed_account(db_session, email="newcomer@example.com")
    await write_request_log(mongo_db_integration, _log_payload(str(someone.id)))

    response = await client.get("/logs", headers=account_headers(newcomer.id))

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


async def test_write_request_log_is_case_insensitive_for_sensitive_headers(
    mongo_db_integration: AsyncIOMotorDatabase,
) -> None:
    payload = _log_payload("acc-x")
    payload["request_headers"] = {
        "AUTHORIZATION": "Bearer x",
        "cookie": "sessionid=abc",
        "X-Trace": "plain-value",
    }

    inserted_id = await write_request_log(mongo_db_integration, payload)

    doc = await mongo_db_integration[COLLECTION].find_one(
        {"_id": _as_object_id(inserted_id)}
    )
    assert doc["request_headers"]["AUTHORIZATION"] == "[MASKED]"
    assert doc["request_headers"]["cookie"] == "[MASKED]"
    assert doc["request_headers"]["X-Trace"] == "plain-value"
