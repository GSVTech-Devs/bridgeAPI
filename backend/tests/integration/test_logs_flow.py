"""Integration tests for request logs against real MongoDB.

Validates what mocks can't: Motor ``insert_one``/``find`` actually round-trip
through Mongo, sensitive headers are masked in the persisted document (not
just in the return value), ``created_at``/``expires_at`` are stored with the
configured TTL, and the ``/logs`` endpoint filters by the authenticated
client plus honors pagination at the query level.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

from app.core.config import settings
from app.core.security import create_access_token
from app.domains.logs.service import (
    COLLECTION,
    generate_correlation_id,
    write_request_log,
)

if TYPE_CHECKING:
    from httpx import AsyncClient
    from motor.motor_asyncio import AsyncIOMotorDatabase

pytestmark = pytest.mark.integration


def _client_headers(email: str) -> dict[str, str]:
    token = create_access_token(email, role="client")
    return {"Authorization": f"Bearer {token}"}


def _log_payload(client_email: str, path: str = "/v1/charges") -> dict:
    return {
        "correlation_id": generate_correlation_id(),
        "client_id": client_email,
        "api_id": "api-uuid",
        "key_id": "key-uuid",
        "path": path,
        "method": "POST",
        "status_code": 200,
        "latency_ms": 42.0,
        "request_headers": {
            "Authorization": "Bearer secret-jwt-xyz",
            "X-Api-Key": "brg_sensitive_key",
            "Content-Type": "application/json",
        },
        "response_headers": {
            "Set-Cookie": "session=abc",
            "X-Request-Id": "rid-123",
        },
    }


async def test_write_request_log_masks_sensitive_and_stores_ttl(
    mongo_db_integration: AsyncIOMotorDatabase,
) -> None:
    before = datetime.now(timezone.utc)
    payload = _log_payload("acme@example.com")

    inserted_id = await write_request_log(mongo_db_integration, payload)

    doc = await mongo_db_integration[COLLECTION].find_one(
        {"_id": _as_object_id(inserted_id)}
    )
    assert doc is not None
    # Sensitive headers replaced — plaintext never touches disk
    assert doc["request_headers"]["Authorization"] == "[MASKED]"
    assert doc["request_headers"]["X-Api-Key"] == "[MASKED]"
    assert doc["request_headers"]["Content-Type"] == "application/json"
    assert doc["response_headers"]["Set-Cookie"] == "[MASKED]"
    assert doc["response_headers"]["X-Request-Id"] == "rid-123"

    # TTL fields present and spaced by configured retention
    assert doc["created_at"] >= before.replace(tzinfo=None) - timedelta(seconds=1)
    delta = doc["expires_at"] - doc["created_at"]
    assert delta == timedelta(hours=settings.log_retention_hours)


async def test_list_logs_returns_only_authenticated_clients_logs(
    client: AsyncClient,
    mongo_db_integration: AsyncIOMotorDatabase,
) -> None:
    await write_request_log(mongo_db_integration, _log_payload("owner@example.com"))
    await write_request_log(mongo_db_integration, _log_payload("owner@example.com"))
    await write_request_log(mongo_db_integration, _log_payload("other@example.com"))

    response = await client.get("/logs", headers=_client_headers("owner@example.com"))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    for item in body["items"]:
        assert item["client_id"] == "owner@example.com"


async def test_list_logs_honors_skip_and_limit_at_query_level(
    client: AsyncClient,
    mongo_db_integration: AsyncIOMotorDatabase,
) -> None:
    for i in range(5):
        await write_request_log(
            mongo_db_integration,
            _log_payload("owner@example.com", path=f"/v1/op/{i}"),
        )

    page_one = await client.get(
        "/logs",
        params={"skip": 0, "limit": 2},
        headers=_client_headers("owner@example.com"),
    )
    page_two = await client.get(
        "/logs",
        params={"skip": 2, "limit": 2},
        headers=_client_headers("owner@example.com"),
    )

    assert page_one.json()["total"] == 2
    assert page_two.json()["total"] == 2
    page_one_paths = {item["path"] for item in page_one.json()["items"]}
    page_two_paths = {item["path"] for item in page_two.json()["items"]}
    assert page_one_paths.isdisjoint(page_two_paths)


async def test_list_logs_empty_when_client_has_none(
    client: AsyncClient,
    mongo_db_integration: AsyncIOMotorDatabase,
) -> None:
    await write_request_log(mongo_db_integration, _log_payload("someone@example.com"))

    response = await client.get(
        "/logs", headers=_client_headers("newcomer@example.com")
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


async def test_write_request_log_is_case_insensitive_for_sensitive_headers(
    mongo_db_integration: AsyncIOMotorDatabase,
) -> None:
    payload = _log_payload("acme@example.com")
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


def _as_object_id(value: str):
    from bson import ObjectId

    return ObjectId(value)
