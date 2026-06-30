# Testes para o domínio permissions (camada HTTP).
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.domains.apis.models import APIAuthType, APIStatus, ExternalAPI
from app.domains.permissions.models import Permission


def make_permission(
    account_id: uuid.UUID | None = None,
    api_id: uuid.UUID | None = None,
    revoked_at: datetime | None = None,
) -> Permission:
    return Permission(
        id=uuid.uuid4(),
        account_id=account_id or uuid.uuid4(),
        api_id=api_id or uuid.uuid4(),
        granted_at=datetime.now(timezone.utc),
        revoked_at=revoked_at,
        proxy_managed_by_client=False,
        captcha_managed_by_client=False,
    )


def make_api() -> ExternalAPI:
    return ExternalAPI(
        id=uuid.uuid4(),
        name="Stripe API",
        base_url="https://api.stripe.com",
        master_key_encrypted="encrypted-key",
        auth_type=APIAuthType.API_KEY,
        status=APIStatus.ACTIVE,
        uses_proxy=False,
        uses_captcha=False,
        created_at=datetime.now(timezone.utc),
    )


def admin_headers() -> dict:
    token = create_access_token("admin@bridge.com", role="admin")
    return {"Authorization": f"Bearer {token}"}


def account_headers() -> dict:
    token = create_access_token(
        "acme@example.com",
        role="owner",
        extra_claims={"user_id": str(uuid.uuid4()), "account_id": str(uuid.uuid4())},
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /permissions  (admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_list_permissions(client: AsyncClient) -> None:
    items = [
        {
            "account_id": str(uuid.uuid4()),
            "api_id": str(uuid.uuid4()),
            "account_name": "Acme Corp",
            "api_name": "Stripe API",
            "status": "active",
        },
    ]
    with patch(
        "app.domains.permissions.router.list_permissions",
        new=AsyncMock(return_value=items),
    ):
        response = await client.get("/permissions", headers=admin_headers())

    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "active"


@pytest.mark.asyncio
async def test_list_permissions_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/permissions")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /permissions  (admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_grant_api_access(client: AsyncClient) -> None:
    account_id, api_id = uuid.uuid4(), uuid.uuid4()
    permission = make_permission(account_id=account_id, api_id=api_id)

    with patch(
        "app.domains.permissions.router.grant_permission",
        new=AsyncMock(return_value=permission),
    ):
        response = await client.post(
            "/permissions",
            json={"account_id": str(account_id), "api_id": str(api_id)},
            headers=admin_headers(),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["account_id"] == str(account_id)
    assert body["revoked_at"] is None


@pytest.mark.asyncio
async def test_duplicate_permission_returns_409(client: AsyncClient) -> None:
    from app.domains.permissions.service import DuplicatePermissionError

    with patch(
        "app.domains.permissions.router.grant_permission",
        new=AsyncMock(side_effect=DuplicatePermissionError),
    ):
        response = await client.post(
            "/permissions",
            json={"account_id": str(uuid.uuid4()), "api_id": str(uuid.uuid4())},
            headers=admin_headers(),
        )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_grant_permission_requires_admin(client: AsyncClient) -> None:
    response = await client.post(
        "/permissions",
        json={"account_id": str(uuid.uuid4()), "api_id": str(uuid.uuid4())},
        headers=account_headers(),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /permissions/{account_id}/{api_id}/revoke  (admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_revoke_api_access(client: AsyncClient) -> None:
    account_id, api_id = uuid.uuid4(), uuid.uuid4()
    revoked = make_permission(
        account_id=account_id, api_id=api_id, revoked_at=datetime.now(timezone.utc)
    )

    with patch(
        "app.domains.permissions.router.revoke_permission",
        new=AsyncMock(return_value=revoked),
    ):
        response = await client.patch(
            f"/permissions/{account_id}/{api_id}/revoke",
            headers=admin_headers(),
        )

    assert response.status_code == 200
    assert response.json()["revoked_at"] is not None


@pytest.mark.asyncio
async def test_revoke_nonexistent_permission_returns_404(client: AsyncClient) -> None:
    from app.domains.permissions.service import PermissionNotFoundError

    with patch(
        "app.domains.permissions.router.revoke_permission",
        new=AsyncMock(side_effect=PermissionNotFoundError),
    ):
        response = await client.patch(
            f"/permissions/{uuid.uuid4()}/{uuid.uuid4()}/revoke",
            headers=admin_headers(),
        )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /catalog  (account user)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_account_sees_only_authorized_apis_in_catalog(
    client: AsyncClient,
) -> None:
    apis = [make_api(), make_api()]
    with (
        patch(
            "app.domains.permissions.router.get_account_authorized_apis",
            new=AsyncMock(return_value=apis),
        ),
        patch(
            "app.domains.permissions.router.api_ids_with_visible_docs",
            new=AsyncMock(return_value=set()),
        ),
    ):
        response = await client.get("/catalog", headers=account_headers())

    assert response.status_code == 200
    assert response.json()["total"] == 2


@pytest.mark.asyncio
async def test_catalog_marks_has_docs_for_apis_with_visible_docs(
    client: AsyncClient,
) -> None:
    apis = [make_api(), make_api()]
    with (
        patch(
            "app.domains.permissions.router.get_account_authorized_apis",
            new=AsyncMock(return_value=apis),
        ),
        patch(
            "app.domains.permissions.router.api_ids_with_visible_docs",
            new=AsyncMock(return_value={apis[0].id}),
        ),
    ):
        response = await client.get("/catalog", headers=account_headers())

    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["items"]}
    assert items[str(apis[0].id)]["has_docs"] is True
    assert items[str(apis[1].id)]["has_docs"] is False


@pytest.mark.asyncio
async def test_catalog_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/catalog")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_cannot_access_account_catalog(client: AsyncClient) -> None:
    response = await client.get("/catalog", headers=admin_headers())
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /catalog/{api_id}/docs  (account user)
# ---------------------------------------------------------------------------


def make_doc_op(api_id: uuid.UUID, visible: bool = True):
    from app.domains.apis.models import ApiDocOperation

    return ApiDocOperation(
        id=uuid.uuid4(),
        api_id=api_id,
        method="GET",
        path="/people",
        summary="List",
        description=None,
        operation_json='{"parameters": [], "request_example": null, "responses": []}',
        visible=visible,
        sort_order=0,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_user_docs_returns_only_visible_operations(client: AsyncClient) -> None:
    api = make_api()
    visible_rows = [make_doc_op(api.id, visible=True)]
    with (
        patch(
            "app.domains.permissions.router.get_permission",
            new=AsyncMock(return_value=make_permission(api_id=api.id)),
        ),
        patch(
            "app.domains.permissions.router.get_api_by_id",
            new=AsyncMock(return_value=api),
        ),
        patch(
            "app.domains.permissions.router.list_doc_operations",
            new=AsyncMock(return_value=visible_rows),
        ) as mock_list,
    ):
        response = await client.get(
            f"/catalog/{api.id}/docs", headers=account_headers()
        )
    assert response.status_code == 200
    body = response.json()
    assert body["api_name"] == api.name
    assert len(body["operations"]) == 1
    # gating: só operações visíveis são pedidas ao service
    assert mock_list.await_args.kwargs.get("only_visible") is True


@pytest.mark.asyncio
async def test_user_docs_without_permission_returns_404(client: AsyncClient) -> None:
    with patch(
        "app.domains.permissions.router.get_permission",
        new=AsyncMock(return_value=None),
    ):
        response = await client.get(
            f"/catalog/{uuid.uuid4()}/docs", headers=account_headers()
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_docs_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(f"/catalog/{uuid.uuid4()}/docs")
    assert response.status_code == 401
