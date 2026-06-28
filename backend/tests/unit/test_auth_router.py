# Testes para o router de autenticação — /auth/login (admin),
# /auth/portal/login (account) e /auth/me.
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.domains.accounts.models import Account, AccountStatus, AccountType
from app.domains.auth.models import User, UserRole
from app.domains.auth.schemas import CompanyOption


def make_admin(email: str = "admin@bridge.com") -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password("secret123"),
        role=UserRole.ADMIN,
    )


def make_owner(account_id: uuid.UUID, email: str = "owner@acme.com") -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password("secret123"),
        role=UserRole.OWNER,
        account_id=account_id,
    )


def make_account(status: AccountStatus = AccountStatus.ACTIVE) -> Account:
    return Account(
        id=uuid.uuid4(), name="Acme", type=AccountType.COMPANY, status=status
    )


# ---------------------------------------------------------------------------
# POST /auth/login  (admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_login_returns_jwt(client: AsyncClient) -> None:
    with patch(
        "app.domains.auth.router.authenticate_user",
        new=AsyncMock(return_value=make_admin()),
    ):
        response = await client.post(
            "/auth/login",
            json={"email": "admin@bridge.com", "password": "secret123"},
        )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_admin_login_invalid_returns_401(client: AsyncClient) -> None:
    with patch(
        "app.domains.auth.router.authenticate_user", new=AsyncMock(return_value=None)
    ):
        response = await client.post(
            "/auth/login",
            json={"email": "admin@bridge.com", "password": "wrong"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_owner_cannot_login_via_admin_endpoint(client: AsyncClient) -> None:
    owner = make_owner(uuid.uuid4())
    with patch(
        "app.domains.auth.router.authenticate_user",
        new=AsyncMock(return_value=owner),
    ):
        response = await client.post(
            "/auth/login",
            json={"email": "owner@acme.com", "password": "secret123"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_login_missing_fields_returns_422(client: AsyncClient) -> None:
    response = await client.post("/auth/login", json={"email": "admin@bridge.com"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/portal/login  (account)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_portal_login_returns_identity_token_and_companies(
    client: AsyncClient,
) -> None:
    account = make_account()
    owner = make_owner(account.id)
    company = CompanyOption(
        account_id=account.id, name="Acme", type="company", role="owner"
    )
    with (
        patch(
            "app.domains.auth.router.authenticate_user",
            new=AsyncMock(return_value=owner),
        ),
        patch(
            "app.domains.auth.router._portal_companies",
            new=AsyncMock(return_value=[company]),
        ),
    ):
        response = await client.post(
            "/auth/portal/login",
            json={"email": "owner@acme.com", "password": "secret123"},
        )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert len(body["companies"]) == 1
    assert body["companies"][0]["account_id"] == str(account.id)


@pytest.mark.asyncio
async def test_portal_login_invalid_credentials_returns_401(
    client: AsyncClient,
) -> None:
    with patch(
        "app.domains.auth.router.authenticate_user",
        new=AsyncMock(return_value=None),
    ):
        response = await client.post(
            "/auth/portal/login",
            json={"email": "owner@acme.com", "password": "wrong"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_portal_login_no_active_company_returns_generic_401(
    client: AsyncClient,
) -> None:
    """Autenticou mas não há empresa ativa: resposta genérica (anti-enumeração).

    Não pode revelar que a credencial era válida — mesma mensagem de email/senha
    inválidos, mesmo status, que uma senha errada."""
    owner = make_owner(uuid.uuid4())
    with (
        patch(
            "app.domains.auth.router.authenticate_user",
            new=AsyncMock(return_value=owner),
        ),
        patch(
            "app.domains.auth.router._portal_companies",
            new=AsyncMock(return_value=[]),
        ),
    ):
        response = await client.post(
            "/auth/portal/login",
            json={"email": "owner@acme.com", "password": "secret123"},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Email ou senha inválidos."


@pytest.mark.asyncio
async def test_admin_cannot_login_via_portal_endpoint(client: AsyncClient) -> None:
    # Admin autentica, mas não tem empresa de portal → resposta genérica 401
    # (não revela que era um admin válido).
    with (
        patch(
            "app.domains.auth.router.authenticate_user",
            new=AsyncMock(return_value=make_admin()),
        ),
        patch(
            "app.domains.auth.router._portal_companies",
            new=AsyncMock(return_value=[]),
        ),
    ):
        response = await client.post(
            "/auth/portal/login",
            json={"email": "admin@bridge.com", "password": "secret123"},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Email ou senha inválidos."


@pytest.mark.asyncio
async def test_portal_companies_lists_accounts(client: AsyncClient) -> None:
    account = make_account()
    company = CompanyOption(
        account_id=account.id, name="Acme", type="company", role="owner"
    )
    token = create_access_token("owner@acme.com", role="portal_identity")
    with (
        patch(
            "app.domains.auth.router.get_users_by_email",
            new=AsyncMock(return_value=[make_owner(account.id)]),
        ),
        patch(
            "app.domains.auth.router._portal_companies",
            new=AsyncMock(return_value=[company]),
        ),
    ):
        response = await client.get(
            "/auth/portal/companies",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert len(response.json()["companies"]) == 1


@pytest.mark.asyncio
async def test_portal_companies_rejects_non_portal_token(client: AsyncClient) -> None:
    # Token cujo email não tem nenhum vínculo de portal → 403.
    token = create_access_token("adm@bridge.com", role="portal_identity")
    with patch(
        "app.domains.auth.router.get_users_by_email",
        new=AsyncMock(return_value=[make_admin("adm@bridge.com")]),
    ):
        response = await client.get(
            "/auth/portal/companies",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_portal_select_issues_account_scoped_token(client: AsyncClient) -> None:
    account = make_account()
    owner = make_owner(account.id)
    token = create_access_token("owner@acme.com", role="portal_identity")
    with (
        patch(
            "app.domains.auth.router.get_users_by_email",
            new=AsyncMock(return_value=[owner]),
        ),
        patch(
            "app.domains.auth.router.get_account_user",
            new=AsyncMock(return_value=owner),
        ),
        patch(
            "app.domains.auth.router.get_account_by_id",
            new=AsyncMock(return_value=account),
        ),
    ):
        response = await client.post(
            "/auth/portal/select",
            json={"account_id": str(account.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_portal_select_without_access_returns_403(client: AsyncClient) -> None:
    account = make_account()
    token = create_access_token("owner@acme.com", role="portal_identity")
    with (
        patch(
            "app.domains.auth.router.get_users_by_email",
            new=AsyncMock(return_value=[make_owner(uuid.uuid4())]),
        ),
        patch(
            "app.domains.auth.router.get_account_user",
            new=AsyncMock(return_value=None),
        ),
    ):
        response = await client.post(
            "/auth/portal/select",
            json={"account_id": str(account.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_me_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_admin_token_returns_identity(client: AsyncClient) -> None:
    token = create_access_token("admin@bridge.com", role="admin")
    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "admin@bridge.com"


@pytest.mark.asyncio
async def test_me_with_account_token_returns_account_scope(client: AsyncClient) -> None:
    account_id = uuid.uuid4()
    token = create_access_token(
        "owner@acme.com",
        role="owner",
        extra_claims={"user_id": str(uuid.uuid4()), "account_id": str(account_id)},
    )
    account = Account(id=account_id, name="Acme", type=AccountType.COMPANY)
    company = CompanyOption(
        account_id=account_id, name="Acme", type="company", role="owner"
    )
    with (
        patch(
            "app.domains.auth.router.get_account_by_id",
            new=AsyncMock(return_value=account),
        ),
        patch(
            "app.domains.auth.router._portal_companies",
            new=AsyncMock(return_value=[company, company]),
        ),
    ):
        response = await client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "owner"
    assert body["account_id"] == str(account_id)
    # owner de empresa: enxerga todas as capabilities e a gestão de usuários
    assert body["is_owner"] is True
    assert body["account_type"] == "company"
    assert "members" in body["capabilities"]
    # account_count reflete quantas empresas o email acessa
    assert body["account_count"] == 2


# ---------------------------------------------------------------------------
# PATCH /auth/portal/password  (self-service)
# ---------------------------------------------------------------------------


def portal_headers() -> dict:
    token = create_access_token(
        "owner@acme.com",
        role="owner",
        extra_claims={"user_id": str(uuid.uuid4()), "account_id": str(uuid.uuid4())},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_portal_user_changes_own_password(client: AsyncClient) -> None:
    with patch(
        "app.domains.auth.router.change_user_password",
        new=AsyncMock(return_value=make_owner(uuid.uuid4())),
    ):
        response = await client.patch(
            "/auth/portal/password",
            json={"current_password": "secret123", "new_password": "Supersecret1!"},
            headers=portal_headers(),
        )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_change_password_wrong_current_returns_400(client: AsyncClient) -> None:
    from app.domains.auth.service import InvalidCurrentPasswordError

    with patch(
        "app.domains.auth.router.change_user_password",
        new=AsyncMock(side_effect=InvalidCurrentPasswordError),
    ):
        response = await client.patch(
            "/auth/portal/password",
            json={"current_password": "wrong", "new_password": "Supersecret1!"},
            headers=portal_headers(),
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_change_password_weak_new_returns_422(client: AsyncClient) -> None:
    response = await client.patch(
        "/auth/portal/password",
        json={"current_password": "secret123", "new_password": "weakpass"},
        headers=portal_headers(),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_change_password_requires_account_user(client: AsyncClient) -> None:
    token = create_access_token("admin@bridge.com", role="admin")
    response = await client.patch(
        "/auth/portal/password",
        json={"current_password": "secret123", "new_password": "Supersecret1!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_change_password_requires_auth(client: AsyncClient) -> None:
    response = await client.patch(
        "/auth/portal/password",
        json={"current_password": "secret123", "new_password": "Supersecret1!"},
    )
    assert response.status_code == 401
