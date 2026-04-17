"""Integration tests for client-issued API keys.

Validates what mocks can't: bcrypt hash actually persisted in Postgres,
key_prefix UNIQUE constraint, and the full lifecycle where plaintext is
returned once at creation and never again — authentication must succeed
via verify_password against the stored hash and fail after revoke.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.domains.clients.models import Client, ClientStatus
from app.domains.keys.models import APIKey, APIKeyStatus
from app.domains.keys.service import authenticate_api_key

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def _seed_active_client(
    db: AsyncSession, email: str = "acme@example.com"
) -> Client:
    client = Client(
        name="Acme",
        email=email,
        password_hash=hash_password("hunter2"),
        status=ClientStatus.ACTIVE,
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client


def _client_token(email: str = "acme@example.com") -> dict[str, str]:
    token = create_access_token(email, role="client")
    return {"Authorization": f"Bearer {token}"}


async def test_create_key_returns_plaintext_once_and_stores_hash(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    seeded = await _seed_active_client(db_session)

    response = await client.post(
        "/keys", json={"name": "Prod"}, headers=_client_token(seeded.email)
    )
    assert response.status_code == 201
    body = response.json()
    plaintext = body["api_key"]
    assert plaintext.startswith("brg_")

    row = await db_session.execute(select(APIKey).where(APIKey.id == body["id"]))
    stored = row.scalar_one()
    assert stored.key_secret_hash != plaintext
    assert stored.key_prefix in plaintext
    assert stored.status == APIKeyStatus.ACTIVE.value


async def test_authenticate_api_key_works_against_persisted_hash(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    seeded = await _seed_active_client(db_session)
    creation = await client.post(
        "/keys", json={"name": "Prod"}, headers=_client_token(seeded.email)
    )
    plaintext = creation.json()["api_key"]

    authenticated = await authenticate_api_key(db_session, plaintext)

    assert authenticated is not None
    assert str(authenticated.client_id) == str(seeded.id)


async def test_revoked_key_fails_authentication(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    seeded = await _seed_active_client(db_session)
    creation = await client.post(
        "/keys", json={"name": "Prod"}, headers=_client_token(seeded.email)
    )
    plaintext = creation.json()["api_key"]
    key_id = creation.json()["id"]

    revoke = await client.patch(
        f"/keys/{key_id}/revoke", headers=_client_token(seeded.email)
    )
    assert revoke.status_code == 200
    assert revoke.json()["status"] == APIKeyStatus.REVOKED.value

    await db_session.commit()  # ensure view sees the revoke before re-querying

    result = await authenticate_api_key(db_session, plaintext)
    assert result is None


async def test_client_cannot_revoke_another_clients_key(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _seed_active_client(db_session, email="owner@example.com")
    other = await _seed_active_client(db_session, email="other@example.com")

    creation = await client.post(
        "/keys", json={"name": "Prod"}, headers=_client_token(owner.email)
    )
    owner_key_id = creation.json()["id"]

    response = await client.patch(
        f"/keys/{owner_key_id}/revoke", headers=_client_token(other.email)
    )
    assert response.status_code == 404


async def test_list_keys_returns_only_current_clients_keys(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _seed_active_client(db_session, email="owner@example.com")
    other = await _seed_active_client(db_session, email="other@example.com")

    await client.post(
        "/keys", json={"name": "Prod"}, headers=_client_token(owner.email)
    )
    await client.post("/keys", json={"name": "Dev"}, headers=_client_token(owner.email))
    await client.post(
        "/keys", json={"name": "Other"}, headers=_client_token(other.email)
    )

    response = await client.get("/keys", headers=_client_token(owner.email))

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert {item["name"] for item in items} == {"Prod", "Dev"}


async def test_key_prefix_is_unique_at_db_level(db_session: AsyncSession) -> None:
    from sqlalchemy.exc import IntegrityError

    owner = await _seed_active_client(db_session)
    db_session.add(
        APIKey(
            client_id=owner.id,
            name="a",
            key_prefix="deadbeef",
            key_secret_hash=hash_password("brg_deadbeef_x"),
        )
    )
    await db_session.commit()

    db_session.add(
        APIKey(
            client_id=owner.id,
            name="b",
            key_prefix="deadbeef",
            key_secret_hash=hash_password("brg_deadbeef_y"),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
