# Testes de autorização das rotas /portal/* (gestão de roles e usuários).
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.domains.accounts.models import AccountType
from app.core.security import create_access_token


def _token(role: str, account_id: uuid.UUID | None = None) -> str:
    claims = {"user_id": str(uuid.uuid4())}
    if account_id is not None:
        claims["account_id"] = str(account_id)
    return create_access_token("user@acme.com", role=role, extra_claims=claims)


def _headers(role: str, account_id: uuid.UUID | None = None) -> dict:
    return {"Authorization": f"Bearer {_token(role, account_id or uuid.uuid4())}"}


def _company():
    return SimpleNamespace(id=uuid.uuid4(), type=AccountType.COMPANY)


def _individual():
    return SimpleNamespace(id=uuid.uuid4(), type=AccountType.INDIVIDUAL)


@pytest.mark.asyncio
async def test_member_without_members_capability_cannot_access_roles(client: AsyncClient) -> None:
    # Membro de empresa sem a capability MEMBERS → bloqueado.
    with (
        patch(
            "app.domains.members.router.get_account_by_id",
            new=AsyncMock(return_value=_company()),
        ),
        patch(
            "app.domains.members.router.resolve_user_capabilities",
            new=AsyncMock(return_value={"catalog", "logs"}),
        ),
    ):
        resp = await client.get("/portal/roles", headers=_headers("member"))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_access_roles(client: AsyncClient) -> None:
    resp = await client.get("/portal/roles", headers=_headers("admin"))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_individual_owner_cannot_access_roles(client: AsyncClient) -> None:
    with patch(
        "app.domains.members.router.get_account_by_id",
        new=AsyncMock(return_value=_individual()),
    ):
        resp = await client.get("/portal/roles", headers=_headers("owner"))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_company_owner_can_list_roles(client: AsyncClient) -> None:
    with (
        patch(
            "app.domains.members.router.get_account_by_id",
            new=AsyncMock(return_value=_company()),
        ),
        patch(
            "app.domains.members.router.list_roles",
            new=AsyncMock(return_value=[]),
        ),
    ):
        resp = await client.get("/portal/roles", headers=_headers("owner"))
    assert resp.status_code == 200
    assert resp.json() == {"items": []}


@pytest.mark.asyncio
async def test_member_with_members_capability_can_list_roles(client: AsyncClient) -> None:
    # Gerente de equipe delegado: membro cuja role tem a capability MEMBERS.
    with (
        patch(
            "app.domains.members.router.get_account_by_id",
            new=AsyncMock(return_value=_company()),
        ),
        patch(
            "app.domains.members.router.resolve_user_capabilities",
            new=AsyncMock(return_value={"members", "catalog"}),
        ),
        patch(
            "app.domains.members.router.list_roles",
            new=AsyncMock(return_value=[]),
        ),
    ):
        resp = await client.get("/portal/roles", headers=_headers("member"))
    assert resp.status_code == 200
    assert resp.json() == {"items": []}


@pytest.mark.asyncio
async def test_member_with_members_capability_can_create_member(client: AsyncClient) -> None:
    fake_member = SimpleNamespace(
        id=uuid.uuid4(),
        email="novo@acme.com",
        role_id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
    )
    with (
        patch(
            "app.domains.members.router.get_account_by_id",
            new=AsyncMock(return_value=_company()),
        ),
        patch(
            "app.domains.members.router.resolve_user_capabilities",
            new=AsyncMock(return_value={"members"}),
        ),
        patch(
            "app.domains.members.router.create_member",
            new=AsyncMock(return_value=fake_member),
        ),
    ):
        resp = await client.post(
            "/portal/members",
            json={"email": "novo@acme.com", "password": "Sup3rSenha!", "role_id": str(uuid.uuid4())},
            headers=_headers("member"),
        )
    assert resp.status_code == 201
    assert resp.json()["email"] == "novo@acme.com"


@pytest.mark.asyncio
async def test_company_owner_can_create_role(client: AsyncClient) -> None:
    fake_role = SimpleNamespace(
        id=uuid.uuid4(),
        name="Financeiro",
        capabilities=["financial", "metrics"],
        created_at=datetime.now(timezone.utc),
    )
    with (
        patch(
            "app.domains.members.router.get_account_by_id",
            new=AsyncMock(return_value=_company()),
        ),
        patch(
            "app.domains.members.router.create_role",
            new=AsyncMock(return_value=fake_role),
        ),
    ):
        resp = await client.post(
            "/portal/roles",
            json={"name": "Financeiro", "capabilities": ["financial", "metrics"]},
            headers=_headers("owner"),
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Financeiro"
    assert set(body["capabilities"]) == {"financial", "metrics"}


@pytest.mark.asyncio
async def test_create_role_rejects_invalid_capability(client: AsyncClient) -> None:
    with patch(
        "app.domains.members.router.get_account_by_id",
        new=AsyncMock(return_value=_company()),
    ):
        resp = await client.post(
            "/portal/roles",
            json={"name": "X", "capabilities": ["bogus"]},
            headers=_headers("owner"),
        )
    assert resp.status_code == 422
