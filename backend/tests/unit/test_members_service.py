# Testes para o domínio members: resolução de capabilities e validação de schemas.
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.domains.auth.service import DuplicateEmailError
from app.domains.members.schemas import MemberCreate, RoleCreate
from app.domains.members.service import (
    PasswordRequiredError,
    SharedIdentityError,
    create_member,
    resolve_user_capabilities,
    update_member,
)


@pytest.mark.asyncio
async def test_resolve_capabilities_owner_has_everything() -> None:
    identity = SimpleNamespace(role="owner", user_id=uuid.uuid4())
    caps = await resolve_user_capabilities(None, identity)
    assert "members" in caps
    assert "api_keys" in caps
    assert "financial" in caps


@pytest.mark.asyncio
async def test_resolve_capabilities_admin_is_empty() -> None:
    identity = SimpleNamespace(role="admin", user_id=None)
    assert await resolve_user_capabilities(None, identity) == set()


@pytest.mark.asyncio
async def test_resolve_capabilities_member_merges_role_caps() -> None:
    identity = SimpleNamespace(role="member", user_id=uuid.uuid4())
    user = SimpleNamespace(role_id=uuid.uuid4())
    role = SimpleNamespace(capabilities=["logs", "metrics"])
    db = AsyncMock()
    db.get = AsyncMock(return_value=role)
    with patch(
        "app.domains.members.service.get_user_by_id",
        new=AsyncMock(return_value=user),
    ):
        caps = await resolve_user_capabilities(db, identity)
    # baseline (catalog) + capabilities da role
    assert "catalog" in caps
    assert "logs" in caps
    assert "metrics" in caps
    # nunca herda gestão de usuários
    assert "members" not in caps


@pytest.mark.asyncio
async def test_resolve_capabilities_member_without_role_is_baseline() -> None:
    identity = SimpleNamespace(role="member", user_id=uuid.uuid4())
    user = SimpleNamespace(role_id=None)
    db = AsyncMock()
    with patch(
        "app.domains.members.service.get_user_by_id",
        new=AsyncMock(return_value=user),
    ):
        caps = await resolve_user_capabilities(db, identity)
    assert caps == {"catalog", "docs"}


def test_role_create_rejects_invalid_capability() -> None:
    with pytest.raises(ValidationError):
        RoleCreate(name="Financeiro", capabilities=["financial", "bogus"])


def test_role_create_accepts_members_capability() -> None:
    # 'members' é atribuível: permite delegar gestão de usuários a uma role.
    role = RoleCreate(name="Gerente", capabilities=["members"])
    assert role.capabilities == ["members"]


def test_role_create_accepts_valid_capabilities() -> None:
    role = RoleCreate(name="Dev", capabilities=["api_keys", "keys_rotate"])
    assert set(role.capabilities) == {"api_keys", "keys_rotate"}


def test_member_create_rejects_weak_password() -> None:
    with pytest.raises(ValidationError):
        MemberCreate(email="dev@acme.com", password="weak", role_id=uuid.uuid4())


def test_member_create_allows_omitting_password() -> None:
    # Email já existente é convidado sem senha (reusa a credencial da identidade).
    member = MemberCreate(email="dev@acme.com", role_id=uuid.uuid4())
    assert member.password is None


# ---------------------------------------------------------------------------
# create_member — reuso de identidade / senha por email
# ---------------------------------------------------------------------------
def _member_db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.mark.asyncio
async def test_create_member_reuses_existing_identity_password() -> None:
    """Email já existente em OUTRA empresa: reusa a senha e ignora a enviada."""
    account_id = uuid.uuid4()
    existing = SimpleNamespace(
        account_id=uuid.uuid4(), role="member", password_hash="reused-hash"
    )
    with (
        patch(
            "app.domains.members.service._get_role_for_account",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "app.domains.members.service.get_users_by_email",
            new=AsyncMock(return_value=[existing]),
        ),
        patch("app.domains.members.service.hash_password") as hp,
    ):
        member = await create_member(
            _member_db(),
            account_id=account_id,
            email="dev@acme.com",
            password="QualquerIgnorada1!",
            role_id=uuid.uuid4(),
        )
    assert member.password_hash == "reused-hash"
    hp.assert_not_called()  # não gera hash novo


@pytest.mark.asyncio
async def test_create_member_new_email_requires_password() -> None:
    with (
        patch(
            "app.domains.members.service._get_role_for_account",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "app.domains.members.service.get_users_by_email",
            new=AsyncMock(return_value=[]),
        ),
    ):
        with pytest.raises(PasswordRequiredError):
            await create_member(
                _member_db(),
                account_id=uuid.uuid4(),
                email="novo@acme.com",
                password=None,
                role_id=uuid.uuid4(),
            )


@pytest.mark.asyncio
async def test_create_member_rejects_duplicate_in_same_account() -> None:
    account_id = uuid.uuid4()
    existing = SimpleNamespace(account_id=account_id, role="member", password_hash="h")
    with (
        patch(
            "app.domains.members.service._get_role_for_account",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "app.domains.members.service.get_users_by_email",
            new=AsyncMock(return_value=[existing]),
        ),
    ):
        with pytest.raises(DuplicateEmailError):
            await create_member(
                _member_db(),
                account_id=account_id,
                email="dev@acme.com",
                password="Senha123!",
                role_id=uuid.uuid4(),
            )


@pytest.mark.asyncio
async def test_create_member_rejects_admin_email() -> None:
    existing = SimpleNamespace(account_id=None, role="admin", password_hash="h")
    with (
        patch(
            "app.domains.members.service._get_role_for_account",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "app.domains.members.service.get_users_by_email",
            new=AsyncMock(return_value=[existing]),
        ),
    ):
        with pytest.raises(DuplicateEmailError):
            await create_member(
                _member_db(),
                account_id=uuid.uuid4(),
                email="adm@bridge.com",
                password="Senha123!",
                role_id=uuid.uuid4(),
            )


# ---------------------------------------------------------------------------
# update_member — guarda de identidade compartilhada
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_member_blocks_password_change_on_shared_identity() -> None:
    account_id = uuid.uuid4()
    member = SimpleNamespace(
        account_id=account_id, email="dev@acme.com", role_id=None, password_hash="h"
    )
    # o email também existe em outra account → identidade compartilhada
    rows = [
        SimpleNamespace(account_id=account_id),
        SimpleNamespace(account_id=uuid.uuid4()),
    ]
    with (
        patch(
            "app.domains.members.service._get_member_for_account",
            new=AsyncMock(return_value=member),
        ),
        patch(
            "app.domains.members.service.get_users_by_email",
            new=AsyncMock(return_value=rows),
        ),
    ):
        with pytest.raises(SharedIdentityError):
            await update_member(
                _member_db(),
                account_id=account_id,
                member_id=uuid.uuid4(),
                password="NovaSenha1!",
            )


@pytest.mark.asyncio
async def test_update_member_allows_role_change_on_shared_identity() -> None:
    account_id = uuid.uuid4()
    new_role = uuid.uuid4()
    member = SimpleNamespace(
        account_id=account_id, email="dev@acme.com", role_id=None, password_hash="h"
    )
    with (
        patch(
            "app.domains.members.service._get_member_for_account",
            new=AsyncMock(return_value=member),
        ),
        patch(
            "app.domains.members.service._get_role_for_account",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "app.domains.members.service.get_users_by_email",
            new=AsyncMock(return_value=[]),
        ),
    ):
        # só troca o papel → não dispara a guarda de credencial
        result = await update_member(
            _member_db(),
            account_id=account_id,
            member_id=uuid.uuid4(),
            role_id=new_role,
        )
    assert result.role_id == new_role
