# Testes para o domínio members: resolução de capabilities e validação de schemas.
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.domains.members.schemas import MemberCreate, RoleCreate
from app.domains.members.service import resolve_user_capabilities


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


def test_role_create_rejects_members_capability() -> None:
    # 'members' não é atribuível a uma role.
    with pytest.raises(ValidationError):
        RoleCreate(name="Admin", capabilities=["members"])


def test_role_create_accepts_valid_capabilities() -> None:
    role = RoleCreate(name="Dev", capabilities=["api_keys", "keys_rotate"])
    assert set(role.capabilities) == {"api_keys", "keys_rotate"}


def test_member_create_rejects_weak_password() -> None:
    with pytest.raises(ValidationError):
        MemberCreate(email="dev@acme.com", password="weak", role_id=uuid.uuid4())
