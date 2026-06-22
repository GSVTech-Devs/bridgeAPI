# Testes de autorização das rotas /admin/accounts/{id}/* (gestão de roles e
# usuários de uma empresa pelo admin da plataforma).
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.domains.accounts.models import AccountType


def _token(role: str, account_id: uuid.UUID | None = None) -> str:
    claims = {"user_id": str(uuid.uuid4())}
    if account_id is not None:
        claims["account_id"] = str(account_id)
    return create_access_token("user@acme.com", role=role, extra_claims=claims)


def _headers(role: str, account_id: uuid.UUID | None = None) -> dict:
    return {"Authorization": f"Bearer {_token(role, account_id)}"}


def _company():
    return SimpleNamespace(id=uuid.uuid4(), type=AccountType.COMPANY)


def _individual():
    return SimpleNamespace(id=uuid.uuid4(), type=AccountType.INDIVIDUAL)


ACC = uuid.uuid4()
ROLES_URL = f"/admin/accounts/{ACC}/roles"
MEMBERS_URL = f"/admin/accounts/{ACC}/members"


# ---------------------------------------------------------------------------
# Autorização: só admin da plataforma
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_member_cannot_access_admin_roles(client: AsyncClient) -> None:
    resp = await client.get(ROLES_URL, headers=_headers("member", ACC))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_company_owner_cannot_access_admin_roles(client: AsyncClient) -> None:
    # owner do portal não é admin da plataforma → 403
    resp = await client.get(ROLES_URL, headers=_headers("owner", ACC))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_on_individual_account_is_rejected(client: AsyncClient) -> None:
    with patch(
        "app.domains.members.router.get_account_by_id",
        new=AsyncMock(return_value=_individual()),
    ):
        resp = await client.get(ROLES_URL, headers=_headers("admin"))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_admin_on_missing_account_is_404(client: AsyncClient) -> None:
    from app.domains.accounts.service import AccountNotFoundError

    with patch(
        "app.domains.members.router.get_account_by_id",
        new=AsyncMock(side_effect=AccountNotFoundError()),
    ):
        resp = await client.get(ROLES_URL, headers=_headers("admin"))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Caminho feliz: admin gerencia roles/membros de uma empresa
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_can_list_roles(client: AsyncClient) -> None:
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
        resp = await client.get(ROLES_URL, headers=_headers("admin"))
    assert resp.status_code == 200
    assert resp.json() == {"items": []}


@pytest.mark.asyncio
async def test_admin_can_create_role(client: AsyncClient) -> None:
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
        ) as create_mock,
    ):
        resp = await client.post(
            ROLES_URL,
            json={"name": "Financeiro", "capabilities": ["financial", "metrics"]},
            headers=_headers("admin"),
        )
    assert resp.status_code == 201
    # service chamado escopado à account da URL
    assert create_mock.await_args.kwargs["account_id"] == ACC
    body = resp.json()
    assert body["name"] == "Financeiro"
    assert set(body["capabilities"]) == {"financial", "metrics"}


@pytest.mark.asyncio
async def test_admin_create_role_rejects_invalid_capability(client: AsyncClient) -> None:
    with patch(
        "app.domains.members.router.get_account_by_id",
        new=AsyncMock(return_value=_company()),
    ):
        resp = await client.post(
            ROLES_URL,
            json={"name": "X", "capabilities": ["bogus"]},
            headers=_headers("admin"),
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_admin_can_create_member(client: AsyncClient) -> None:
    role_id = uuid.uuid4()
    fake_member = SimpleNamespace(
        id=uuid.uuid4(),
        email="sub@empresa.com",
        role_id=role_id,
        created_at=datetime.now(timezone.utc),
    )
    with (
        patch(
            "app.domains.members.router.get_account_by_id",
            new=AsyncMock(return_value=_company()),
        ),
        patch(
            "app.domains.members.router.create_member",
            new=AsyncMock(return_value=fake_member),
        ) as create_mock,
    ):
        resp = await client.post(
            MEMBERS_URL,
            json={
                "email": "sub@empresa.com",
                "password": "Sup3rSenha!",
                "role_id": str(role_id),
            },
            headers=_headers("admin"),
        )
    assert resp.status_code == 201
    assert create_mock.await_args.kwargs["account_id"] == ACC
    assert resp.json()["email"] == "sub@empresa.com"


@pytest.mark.asyncio
async def test_admin_can_list_members(client: AsyncClient) -> None:
    with (
        patch(
            "app.domains.members.router.get_account_by_id",
            new=AsyncMock(return_value=_company()),
        ),
        patch(
            "app.domains.members.router.list_members",
            new=AsyncMock(return_value=[]),
        ),
    ):
        resp = await client.get(MEMBERS_URL, headers=_headers("admin"))
    assert resp.status_code == 200
    assert resp.json() == {"items": []}
