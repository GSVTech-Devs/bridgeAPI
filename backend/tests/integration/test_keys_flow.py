"""Integration tests for account-issued API keys.

Validates what mocks can't: bcrypt hash persisted in Postgres, key_prefix
UNIQUE constraint, and the lifecycle where plaintext is returned once at
creation and authentication succeeds via verify_password and fails after revoke.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.domains.apis.models import APIAuthType, APIStatus, ExternalAPI
from app.domains.keys.models import APIKey, APIKeyStatus
from app.domains.keys.service import authenticate_api_key
from app.domains.permissions.models import Permission

from ._seed import account_headers, seed_account

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


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


async def _grant(db: AsyncSession, account_id, api_id) -> None:
    db.add(Permission(account_id=account_id, api_id=api_id))
    await db.commit()


async def _setup(db: AsyncSession, email: str = "acme@example.com"):
    account, _ = await seed_account(db, email=email)
    api = await _seed_api(db)
    await _grant(db, account.id, api.id)
    return account, api


async def test_create_key_returns_plaintext_once_and_stores_hash(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    account, api = await _setup(db_session)

    response = await client.post(
        "/keys",
        json={"name": "Prod", "api_id": str(api.id)},
        headers=account_headers(account.id),
    )
    assert response.status_code == 201
    body = response.json()
    plaintext = body["api_key"]
    assert plaintext.startswith("brg_")

    row = await db_session.execute(select(APIKey).where(APIKey.id == body["id"]))
    stored = row.scalar_one()
    assert stored.key_secret_hash != plaintext
    assert stored.key_prefix in plaintext
    assert stored.account_id == account.id


async def test_authenticate_api_key_works_against_persisted_hash(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    account, api = await _setup(db_session)
    creation = await client.post(
        "/keys",
        json={"name": "Prod", "api_id": str(api.id)},
        headers=account_headers(account.id),
    )
    plaintext = creation.json()["api_key"]

    authenticated = await authenticate_api_key(db_session, plaintext)

    assert authenticated is not None
    assert str(authenticated.account_id) == str(account.id)


async def test_revoked_key_fails_authentication(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    account, api = await _setup(db_session)
    creation = await client.post(
        "/keys",
        json={"name": "Prod", "api_id": str(api.id)},
        headers=account_headers(account.id),
    )
    plaintext = creation.json()["api_key"]
    key_id = creation.json()["id"]

    revoke = await client.patch(
        f"/keys/{key_id}/revoke", headers=account_headers(account.id)
    )
    assert revoke.status_code == 200
    assert revoke.json()["status"] == APIKeyStatus.REVOKED.value

    await db_session.commit()
    assert await authenticate_api_key(db_session, plaintext) is None


async def test_account_cannot_revoke_another_accounts_key(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, api = await _setup(db_session, email="owner@example.com")
    other, _ = await seed_account(db_session, email="other@example.com")

    creation = await client.post(
        "/keys",
        json={"name": "Prod", "api_id": str(api.id)},
        headers=account_headers(owner.id),
    )
    owner_key_id = creation.json()["id"]

    response = await client.patch(
        f"/keys/{owner_key_id}/revoke", headers=account_headers(other.id)
    )
    assert response.status_code == 404


async def test_list_keys_returns_only_current_accounts_keys(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, api = await _setup(db_session, email="owner@example.com")
    other, _ = await seed_account(db_session, email="other@example.com")
    await _grant(db_session, other.id, api.id)

    await client.post(
        "/keys",
        json={"name": "Prod", "api_id": str(api.id)},
        headers=account_headers(owner.id),
    )
    await client.post(
        "/keys",
        json={"name": "Dev", "api_id": str(api.id)},
        headers=account_headers(owner.id),
    )
    await client.post(
        "/keys",
        json={"name": "Other", "api_id": str(api.id)},
        headers=account_headers(other.id),
    )

    response = await client.get("/keys", headers=account_headers(owner.id))

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert {item["name"] for item in items} == {"Prod", "Dev"}


async def test_create_key_without_permission_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    account, _ = await seed_account(db_session)
    api = await _seed_api(db_session)  # no grant

    response = await client.post(
        "/keys",
        json={"name": "Prod", "api_id": str(api.id)},
        headers=account_headers(account.id),
    )
    assert response.status_code == 403


async def test_key_prefix_is_unique_at_db_level(db_session: AsyncSession) -> None:
    from sqlalchemy.exc import IntegrityError

    account, _ = await seed_account(db_session)
    db_session.add(
        APIKey(
            account_id=account.id,
            name="a",
            key_prefix="deadbeef",
            key_secret_hash=hash_password("brg_deadbeef_x"),
        )
    )
    await db_session.commit()

    db_session.add(
        APIKey(
            account_id=account.id,
            name="b",
            key_prefix="deadbeef",
            key_secret_hash=hash_password("brg_deadbeef_y"),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
