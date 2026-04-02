# RED → GREEN
# Testes para o domínio apis.
# Banco mockado via dependency override (conftest.py).
# Serviços mockados via unittest.mock.patch.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.domains.apis.models import (
    APIAuthType,
    APIStatus,
    Endpoint,
    ExternalAPI,
    HTTPMethod,
)


def make_api(status: APIStatus = APIStatus.ACTIVE) -> ExternalAPI:
    return ExternalAPI(
        id=uuid.uuid4(),
        name="Stripe API",
        base_url="https://api.stripe.com",
        master_key_encrypted="encrypted-key",
        auth_type=APIAuthType.API_KEY,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def make_endpoint(api_id: uuid.UUID | None = None) -> Endpoint:
    return Endpoint(
        id=uuid.uuid4(),
        api_id=api_id or uuid.uuid4(),
        method=HTTPMethod.GET,
        path="/charges",
        status="active",
        cost_rule=None,
        created_at=datetime.now(timezone.utc),
    )


def admin_headers() -> dict:
    token = create_access_token("admin@bridge.com")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /apis  (admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_register_api(client: AsyncClient) -> None:
    api = make_api()
    with patch(
        "app.domains.apis.router.register_api",
        new=AsyncMock(return_value=api),
    ):
        response = await client.post(
            "/apis",
            json={
                "name": "Stripe API",
                "base_url": "https://api.stripe.com",
                "master_key": "sk-secret",
                "auth_type": "api_key",
            },
            headers=admin_headers(),
        )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Stripe API"
    assert "master_key_encrypted" not in body


@pytest.mark.asyncio
async def test_duplicate_api_name_returns_409(client: AsyncClient) -> None:
    from app.domains.apis.service import DuplicateAPINameError

    with patch(
        "app.domains.apis.router.register_api",
        new=AsyncMock(side_effect=DuplicateAPINameError),
    ):
        response = await client.post(
            "/apis",
            json={"name": "Stripe API", "base_url": "https://api.stripe.com"},
            headers=admin_headers(),
        )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_api_with_invalid_base_url_returns_422(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/apis",
        json={"name": "Stripe API", "base_url": "not-a-url"},
        headers=admin_headers(),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_api_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/apis",
        json={"name": "X", "base_url": "https://x.com"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /apis  (admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_apis_returns_paginated_results(client: AsyncClient) -> None:
    apis = [make_api(), make_api()]
    with patch(
        "app.domains.apis.router.list_apis",
        new=AsyncMock(return_value=(apis, 2)),
    ):
        response = await client.get("/apis", headers=admin_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_list_apis_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/apis")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /apis/{id}  (admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_api_still_visible_with_status_indicator(
    client: AsyncClient,
) -> None:
    api = make_api(APIStatus.INACTIVE)
    with patch(
        "app.domains.apis.router.get_api_by_id",
        new=AsyncMock(return_value=api),
    ):
        with patch(
            "app.domains.apis.router.list_endpoints_for_api",
            new=AsyncMock(return_value=[]),
        ):
            response = await client.get(f"/apis/{api.id}", headers=admin_headers())
    assert response.status_code == 200
    assert response.json()["status"] == "inactive"


@pytest.mark.asyncio
async def test_get_api_returns_endpoints_in_detail_response(
    client: AsyncClient,
) -> None:
    api = make_api()
    endpoints = [make_endpoint(api.id), make_endpoint(api.id)]
    with patch(
        "app.domains.apis.router.get_api_by_id",
        new=AsyncMock(return_value=api),
    ):
        with patch(
            "app.domains.apis.router.list_endpoints_for_api",
            new=AsyncMock(return_value=endpoints),
        ):
            response = await client.get(f"/apis/{api.id}", headers=admin_headers())
    assert response.status_code == 200
    assert len(response.json()["endpoints"]) == 2


@pytest.mark.asyncio
async def test_get_api_not_found_returns_404(client: AsyncClient) -> None:
    from app.domains.apis.service import APINotFoundError

    with patch(
        "app.domains.apis.router.get_api_by_id",
        new=AsyncMock(side_effect=APINotFoundError),
    ):
        with patch(
            "app.domains.apis.router.list_endpoints_for_api",
            new=AsyncMock(return_value=[]),
        ):
            response = await client.get(
                f"/apis/{uuid.uuid4()}", headers=admin_headers()
            )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /apis/{id}/endpoints  (admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_add_endpoint_to_api(client: AsyncClient) -> None:
    api = make_api()
    ep = make_endpoint(api.id)
    with patch(
        "app.domains.apis.router.add_endpoint",
        new=AsyncMock(return_value=ep),
    ):
        response = await client.post(
            f"/apis/{api.id}/endpoints",
            json={"method": "GET", "path": "/charges"},
            headers=admin_headers(),
        )
    assert response.status_code == 201
    assert response.json()["method"] == "GET"
    assert response.json()["path"] == "/charges"


@pytest.mark.asyncio
async def test_add_endpoint_to_missing_api_returns_404(client: AsyncClient) -> None:
    from app.domains.apis.service import APINotFoundError

    with patch(
        "app.domains.apis.router.add_endpoint",
        new=AsyncMock(side_effect=APINotFoundError),
    ):
        response = await client.post(
            f"/apis/{uuid.uuid4()}/endpoints",
            json={"method": "GET", "path": "/charges"},
            headers=admin_headers(),
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_endpoint_with_invalid_http_method_returns_422(
    client: AsyncClient,
) -> None:
    api = make_api()
    response = await client.post(
        f"/apis/{api.id}/endpoints",
        json={"method": "INVALID", "path": "/charges"},
        headers=admin_headers(),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_path_without_leading_slash_returns_422(
    client: AsyncClient,
) -> None:
    api = make_api()
    response = await client.post(
        f"/apis/{api.id}/endpoints",
        json={"method": "GET", "path": "charges"},
        headers=admin_headers(),
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /apis/{id}/disable  (admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_disable_api(client: AsyncClient) -> None:
    api = make_api(APIStatus.INACTIVE)
    with patch(
        "app.domains.apis.router.disable_api",
        new=AsyncMock(return_value=api),
    ):
        response = await client.patch(
            f"/apis/{api.id}/disable", headers=admin_headers()
        )
    assert response.status_code == 200
    assert response.json()["status"] == "inactive"


@pytest.mark.asyncio
async def test_disable_missing_api_returns_404(client: AsyncClient) -> None:
    from app.domains.apis.service import APINotFoundError

    with patch(
        "app.domains.apis.router.disable_api",
        new=AsyncMock(side_effect=APINotFoundError),
    ):
        response = await client.patch(
            f"/apis/{uuid.uuid4()}/disable", headers=admin_headers()
        )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /apis/{id}/enable  (admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_enable_api(client: AsyncClient) -> None:
    api = make_api(APIStatus.ACTIVE)
    with patch(
        "app.domains.apis.router.enable_api",
        new=AsyncMock(return_value=api),
    ):
        response = await client.patch(f"/apis/{api.id}/enable", headers=admin_headers())
    assert response.status_code == 200
    assert response.json()["status"] == "active"


@pytest.mark.asyncio
async def test_enable_missing_api_returns_404(client: AsyncClient) -> None:
    from app.domains.apis.service import APINotFoundError

    with patch(
        "app.domains.apis.router.enable_api",
        new=AsyncMock(side_effect=APINotFoundError),
    ):
        response = await client.patch(
            f"/apis/{uuid.uuid4()}/enable", headers=admin_headers()
        )
    assert response.status_code == 404
