"""Integration tests for the client lifecycle.

Exercises what mocked unit tests can't reach: the unique-email constraint
enforced by Postgres, real status transitions persisted across requests,
and the full register → approve → login chain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import create_access_token, hash_password
from app.domains.clients.models import Client, ClientStatus

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


def _admin_headers() -> dict[str, str]:
    token = create_access_token("admin@bridge.com", role="admin")
    return {"Authorization": f"Bearer {token}"}


async def test_email_unique_constraint_is_enforced_by_postgres(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        Client(name="Acme", email="dup@example.com", password_hash=hash_password("x"))
    )
    await db_session.commit()

    db_session.add(
        Client(name="Acme 2", email="dup@example.com", password_hash=hash_password("y"))
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_duplicate_registration_returns_409(client: AsyncClient) -> None:
    payload = {
        "name": "Acme",
        "email": "acme@example.com",
        "password": "hunter2",
    }
    first = await client.post("/clients/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/clients/register", json=payload)
    assert second.status_code == 409


async def test_register_then_login_then_approve_then_login_flow(
    client: AsyncClient,
) -> None:
    register = await client.post(
        "/clients/register",
        json={"name": "Acme", "email": "acme@example.com", "password": "hunter2"},
    )
    assert register.status_code == 201
    client_id = register.json()["id"]
    assert register.json()["status"] == ClientStatus.PENDING.value

    pending_login = await client.post(
        "/clients/login",
        json={"email": "acme@example.com", "password": "hunter2"},
    )
    assert pending_login.status_code == 403

    approve = await client.patch(
        f"/clients/{client_id}/approve", headers=_admin_headers()
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == ClientStatus.ACTIVE.value

    active_login = await client.post(
        "/clients/login",
        json={"email": "acme@example.com", "password": "hunter2"},
    )
    assert active_login.status_code == 200
    assert active_login.json()["access_token"]


async def test_rejected_client_cannot_login(client: AsyncClient) -> None:
    register = await client.post(
        "/clients/register",
        json={"name": "Nope", "email": "nope@example.com", "password": "hunter2"},
    )
    client_id = register.json()["id"]

    reject = await client.patch(
        f"/clients/{client_id}/reject", headers=_admin_headers()
    )
    assert reject.status_code == 200
    assert reject.json()["status"] == ClientStatus.REJECTED.value

    login = await client.post(
        "/clients/login",
        json={"email": "nope@example.com", "password": "hunter2"},
    )
    assert login.status_code == 403


async def test_admin_list_clients_returns_registered_clients(
    client: AsyncClient,
) -> None:
    for email in ("a@example.com", "b@example.com"):
        await client.post(
            "/clients/register",
            json={"name": email, "email": email, "password": "hunter2"},
        )

    response = await client.get("/clients", headers=_admin_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["email"] for item in body["items"]} == {
        "a@example.com",
        "b@example.com",
    }
