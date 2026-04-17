"""Integration tests for external API registration and master-key encryption.

Validates what mocks can't: Fernet round-trip using the real key from
settings, persisted encrypted value differs from plaintext, enum values
survive a round-trip through Postgres, and the endpoint CRUD flow works
end-to-end.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from app.core.security import create_access_token, decrypt_value
from app.domains.apis.models import APIAuthType, APIStatus, Endpoint, ExternalAPI

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


def _admin_headers() -> dict[str, str]:
    token = create_access_token("admin@bridge.com", role="admin")
    return {"Authorization": f"Bearer {token}"}


async def test_master_key_is_encrypted_at_rest_and_roundtrips(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    plaintext_key = "sk_live_super_secret_master_key"

    response = await client.post(
        "/apis",
        json={
            "name": "Stripe",
            "base_url": "https://api.stripe.com",
            "master_key": plaintext_key,
            "auth_type": "api_key",
        },
        headers=_admin_headers(),
    )
    assert response.status_code == 201

    api_id = response.json()["id"]
    # Response schema never exposes the master key
    assert "master_key" not in response.json()
    assert "master_key_encrypted" not in response.json()

    row = await db_session.execute(select(ExternalAPI).where(ExternalAPI.id == api_id))
    api = row.scalar_one()

    assert api.master_key_encrypted is not None
    assert api.master_key_encrypted != plaintext_key
    assert decrypt_value(api.master_key_encrypted) == plaintext_key


async def test_enum_values_survive_postgres_roundtrip(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/apis",
        json={
            "name": "GitHub",
            "base_url": "https://api.github.com",
            "master_key": "ghp_xxx",
            "auth_type": "bearer",
        },
        headers=_admin_headers(),
    )
    api_id = response.json()["id"]

    row = await db_session.execute(select(ExternalAPI).where(ExternalAPI.id == api_id))
    api = row.scalar_one()

    assert api.auth_type == APIAuthType.BEARER.value
    assert api.status == APIStatus.ACTIVE.value


async def test_duplicate_api_name_returns_409(client: AsyncClient) -> None:
    payload = {
        "name": "Stripe",
        "base_url": "https://api.stripe.com",
        "master_key": "sk_test",
        "auth_type": "api_key",
    }
    first = await client.post("/apis", json=payload, headers=_admin_headers())
    assert first.status_code == 201

    second = await client.post("/apis", json=payload, headers=_admin_headers())
    assert second.status_code == 409


async def test_api_without_master_key_stores_null(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/apis",
        json={
            "name": "Public",
            "base_url": "https://public.example.com",
            "auth_type": "none",
        },
        headers=_admin_headers(),
    )
    assert response.status_code == 201
    api_id = response.json()["id"]

    row = await db_session.execute(select(ExternalAPI).where(ExternalAPI.id == api_id))
    assert row.scalar_one().master_key_encrypted is None


async def test_full_api_crud_flow_with_endpoints(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    create = await client.post(
        "/apis",
        json={
            "name": "Stripe",
            "base_url": "https://api.stripe.com",
            "master_key": "sk_test",
            "auth_type": "api_key",
        },
        headers=_admin_headers(),
    )
    api_id = create.json()["id"]

    add_endpoint = await client.post(
        f"/apis/{api_id}/endpoints",
        json={"method": "POST", "path": "/v1/charges", "cost_rule": 0.01},
        headers=_admin_headers(),
    )
    assert add_endpoint.status_code == 201

    detail = await client.get(f"/apis/{api_id}", headers=_admin_headers())
    assert detail.status_code == 200
    body = detail.json()
    assert len(body["endpoints"]) == 1
    assert body["endpoints"][0]["path"] == "/v1/charges"

    disable = await client.patch(f"/apis/{api_id}/disable", headers=_admin_headers())
    assert disable.status_code == 200
    assert disable.json()["status"] == APIStatus.INACTIVE.value

    enable = await client.patch(f"/apis/{api_id}/enable", headers=_admin_headers())
    assert enable.json()["status"] == APIStatus.ACTIVE.value

    # FK integrity: endpoint still linked to the API
    fk_row = await db_session.execute(select(Endpoint).where(Endpoint.api_id == api_id))
    assert len(fk_row.scalars().all()) == 1
