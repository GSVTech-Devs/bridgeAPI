"""Integration tests for metrics aggregation against real Postgres.

Validates what mocks can't: SQL aggregation (COUNT, AVG, SUM with CAST of
boolean) actually executes on Postgres, ``error_rate`` returns a percentage
(not a proportion), ``since``/``until`` filters narrow at the DB level, and
the client dashboard is scoped to the caller while admin sees the global
total.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

from app.core.security import create_access_token, hash_password
from app.domains.apis.models import APIAuthType, APIStatus, ExternalAPI
from app.domains.clients.models import Client, ClientStatus
from app.domains.keys.models import APIKey, APIKeyStatus
from app.domains.metrics.models import RequestMetric

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


def _admin_headers() -> dict[str, str]:
    token = create_access_token("admin@bridge.com", role="admin")
    return {"Authorization": f"Bearer {token}"}


def _client_headers(email: str) -> dict[str, str]:
    token = create_access_token(email, role="client")
    return {"Authorization": f"Bearer {token}"}


async def _seed_client(
    db: AsyncSession,
    email: str = "acme@example.com",
    name: str = "Acme",
) -> Client:
    c = Client(
        name=name,
        email=email,
        password_hash=hash_password("hunter2"),
        status=ClientStatus.ACTIVE,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _seed_api(db: AsyncSession, name: str = "Stripe") -> ExternalAPI:
    api = ExternalAPI(
        name=name,
        base_url=f"https://{name.lower()}.example.com",
        master_key_encrypted="enc",
        auth_type=APIAuthType.API_KEY,
        status=APIStatus.ACTIVE,
    )
    db.add(api)
    await db.commit()
    await db.refresh(api)
    return api


async def _seed_key(db: AsyncSession, client_id: uuid.UUID, prefix: str) -> APIKey:
    key = APIKey(
        client_id=client_id,
        name="test",
        key_prefix=prefix,
        key_secret_hash=hash_password(f"brg_{prefix}_x"),
        status=APIKeyStatus.ACTIVE.value,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return key


async def _insert_metric(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    api_id: uuid.UUID,
    key_id: uuid.UUID,
    status_code: int,
    latency_ms: float,
    cost: float | None,
    created_at: datetime | None = None,
) -> RequestMetric:
    m = RequestMetric(
        client_id=client_id,
        api_id=api_id,
        key_id=key_id,
        path="/v1/test",
        method="GET",
        status_code=status_code,
        latency_ms=latency_ms,
        cost=cost,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(m)
    await db.commit()
    return m


async def test_client_dashboard_aggregates_real_metrics_correctly(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_client(db_session)
    api = await _seed_api(db_session)
    key = await _seed_key(db_session, acme.id, "acmekey1")

    # 10 requests: 8 success (200), 2 server error (500) → error_rate 20%
    # Latencies sum to 1000 → avg 100.0
    # 5 billable rows (cost=0.02 each) → total_cost 0.10, billable 5
    latencies = [50.0, 80.0, 100.0, 120.0, 150.0, 50.0, 80.0, 100.0, 120.0, 150.0]
    for i, latency in enumerate(latencies):
        await _insert_metric(
            db_session,
            client_id=acme.id,
            api_id=api.id,
            key_id=key.id,
            status_code=500 if i >= 8 else 200,
            latency_ms=latency,
            cost=0.02 if i < 5 else None,
        )

    response = await client.get(
        "/metrics/dashboard", headers=_client_headers(acme.email)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_requests"] == 10
    assert body["error_rate"] == 20.0  # percentage, not 0.2
    assert body["avg_latency_ms"] == 100.0
    assert body["total_cost"] == pytest.approx(0.10)
    assert body["billable_requests"] == 5
    assert body["non_billable_requests"] == 5


async def test_client_dashboard_scopes_to_caller_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_client(db_session, email="acme@example.com", name="Acme")
    other = await _seed_client(db_session, email="other@example.com", name="Other")
    api = await _seed_api(db_session)
    acme_key = await _seed_key(db_session, acme.id, "acmeonly")
    other_key = await _seed_key(db_session, other.id, "otheron")

    for _ in range(3):
        await _insert_metric(
            db_session,
            client_id=acme.id,
            api_id=api.id,
            key_id=acme_key.id,
            status_code=200,
            latency_ms=100.0,
            cost=0.01,
        )
    for _ in range(7):
        await _insert_metric(
            db_session,
            client_id=other.id,
            api_id=api.id,
            key_id=other_key.id,
            status_code=500,
            latency_ms=200.0,
            cost=0.05,
        )

    acme_body = (
        await client.get("/metrics/dashboard", headers=_client_headers(acme.email))
    ).json()
    other_body = (
        await client.get("/metrics/dashboard", headers=_client_headers(other.email))
    ).json()

    assert acme_body["total_requests"] == 3
    assert acme_body["error_rate"] == 0.0
    assert other_body["total_requests"] == 7
    assert other_body["error_rate"] == 100.0


async def test_admin_global_metrics_sums_all_clients(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_client(db_session, email="acme@example.com", name="Acme")
    other = await _seed_client(db_session, email="other@example.com", name="Other")
    api = await _seed_api(db_session)
    acme_key = await _seed_key(db_session, acme.id, "adminac")
    other_key = await _seed_key(db_session, other.id, "adminot")

    await _insert_metric(
        db_session,
        client_id=acme.id,
        api_id=api.id,
        key_id=acme_key.id,
        status_code=200,
        latency_ms=100.0,
        cost=0.10,
    )
    await _insert_metric(
        db_session,
        client_id=other.id,
        api_id=api.id,
        key_id=other_key.id,
        status_code=500,
        latency_ms=300.0,
        cost=0.20,
    )

    response = await client.get("/metrics/admin", headers=_admin_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["total_requests"] == 2
    assert body["error_rate"] == 50.0
    assert body["avg_latency_ms"] == 200.0
    assert body["total_cost"] == pytest.approx(0.30)
    assert body["billable_requests"] == 2


async def test_since_until_filters_narrow_window_at_db_level(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_client(db_session)
    api = await _seed_api(db_session)
    key = await _seed_key(db_session, acme.id, "window1")

    now = datetime.now(timezone.utc)
    old = now - timedelta(days=7)
    mid = now - timedelta(days=3)

    for ts in (old, mid, now):
        await _insert_metric(
            db_session,
            client_id=acme.id,
            api_id=api.id,
            key_id=key.id,
            status_code=200,
            latency_ms=100.0,
            cost=0.01,
            created_at=ts,
        )

    cutoff = (now - timedelta(days=5)).isoformat()
    narrow = await client.get(
        "/metrics/dashboard",
        params={"since": cutoff},
        headers=_client_headers(acme.email),
    )
    wide = await client.get("/metrics/dashboard", headers=_client_headers(acme.email))

    assert narrow.json()["total_requests"] == 2  # mid + now only
    assert wide.json()["total_requests"] == 3

    upper = (now - timedelta(days=5)).isoformat()
    capped = await client.get(
        "/metrics/dashboard",
        params={"until": upper},
        headers=_client_headers(acme.email),
    )
    assert capped.json()["total_requests"] == 1  # only old


async def test_empty_metrics_return_zeros_without_division_error(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_client(db_session)

    response = await client.get(
        "/metrics/dashboard", headers=_client_headers(acme.email)
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "total_requests": 0,
        "error_rate": 0.0,
        "avg_latency_ms": 0.0,
        "total_cost": 0.0,
        "billable_requests": 0,
        "non_billable_requests": 0,
    }
