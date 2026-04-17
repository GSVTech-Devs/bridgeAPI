"""Integration tests for permissions + client catalog.

Validates what mocks can't: the JOIN with revoked_at IS NULL actually
hides revoked permissions from /catalog, grant+revoke+re-grant
transitions work end-to-end, and list_permissions correctly labels
status by joining across three tables.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.core.security import create_access_token, hash_password
from app.domains.apis.models import APIStatus, ExternalAPI
from app.domains.clients.models import Client, ClientStatus

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
        auth_type="api_key",
        status=APIStatus.ACTIVE,
    )
    db.add(api)
    await db.commit()
    await db.refresh(api)
    return api


async def test_catalog_reflects_grant_revoke_regrant_cycle(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_client(db_session)
    api = await _seed_api(db_session)

    empty = await client.get("/catalog", headers=_client_headers(acme.email))
    assert empty.status_code == 200
    assert empty.json()["total"] == 0

    grant = await client.post(
        "/permissions",
        json={"client_id": str(acme.id), "api_id": str(api.id)},
        headers=_admin_headers(),
    )
    assert grant.status_code == 201

    after_grant = await client.get("/catalog", headers=_client_headers(acme.email))
    assert after_grant.json()["total"] == 1
    assert after_grant.json()["items"][0]["name"] == "Stripe"

    revoke = await client.patch(
        f"/permissions/{acme.id}/{api.id}/revoke", headers=_admin_headers()
    )
    assert revoke.status_code == 200
    assert revoke.json()["revoked_at"] is not None

    after_revoke = await client.get("/catalog", headers=_client_headers(acme.email))
    assert after_revoke.json()["total"] == 0

    # Re-granting after revoke reactivates the existing row (clears
    # revoked_at); the (client_id, api_id) UNIQUE constraint forbids a
    # second row.
    regrant = await client.post(
        "/permissions",
        json={"client_id": str(acme.id), "api_id": str(api.id)},
        headers=_admin_headers(),
    )
    assert regrant.status_code == 201

    after_regrant = await client.get("/catalog", headers=_client_headers(acme.email))
    assert after_regrant.json()["total"] == 1


async def test_duplicate_active_grant_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_client(db_session)
    api = await _seed_api(db_session)
    payload = {"client_id": str(acme.id), "api_id": str(api.id)}

    first = await client.post("/permissions", json=payload, headers=_admin_headers())
    assert first.status_code == 201

    second = await client.post("/permissions", json=payload, headers=_admin_headers())
    assert second.status_code == 409


async def test_revoke_nonexistent_permission_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_client(db_session)
    api = await _seed_api(db_session)

    response = await client.patch(
        f"/permissions/{acme.id}/{api.id}/revoke", headers=_admin_headers()
    )
    assert response.status_code == 404


async def test_catalog_scopes_apis_per_client(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_client(db_session, email="acme@example.com", name="Acme")
    other = await _seed_client(db_session, email="other@example.com", name="Other")
    stripe = await _seed_api(db_session, name="Stripe")
    github = await _seed_api(db_session, name="GitHub")

    for client_obj, api in ((acme, stripe), (other, github)):
        await client.post(
            "/permissions",
            json={"client_id": str(client_obj.id), "api_id": str(api.id)},
            headers=_admin_headers(),
        )

    acme_catalog = await client.get("/catalog", headers=_client_headers(acme.email))
    other_catalog = await client.get("/catalog", headers=_client_headers(other.email))

    assert [i["name"] for i in acme_catalog.json()["items"]] == ["Stripe"]
    assert [i["name"] for i in other_catalog.json()["items"]] == ["GitHub"]


async def test_admin_list_permissions_joins_and_labels_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    acme = await _seed_client(db_session, email="acme@example.com", name="Acme")
    other = await _seed_client(db_session, email="other@example.com", name="Other")
    stripe = await _seed_api(db_session, name="Stripe")
    github = await _seed_api(db_session, name="GitHub")

    await client.post(
        "/permissions",
        json={"client_id": str(acme.id), "api_id": str(stripe.id)},
        headers=_admin_headers(),
    )
    await client.post(
        "/permissions",
        json={"client_id": str(other.id), "api_id": str(github.id)},
        headers=_admin_headers(),
    )
    await client.patch(
        f"/permissions/{other.id}/{github.id}/revoke", headers=_admin_headers()
    )

    response = await client.get("/permissions", headers=_admin_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    by_client = {item["client_name"]: item for item in body["items"]}
    assert by_client["Acme"]["api_name"] == "Stripe"
    assert by_client["Acme"]["status"] == "active"
    assert by_client["Acme"]["client_name"] == "Acme"
    other_row = next(i for i in body["items"] if i["api_name"] == "GitHub")
    assert other_row["status"] == "revoked"
