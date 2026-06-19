# Testes para as dependencies de autenticação/autorização.
import uuid

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.authz import Feature
from app.core.security import create_access_token
from app.domains.auth.router import (
    get_current_account_user,
    get_current_user,
    require_feature,
)
from app.domains.auth.schemas import MeResponse


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _owner_token(account_id: uuid.UUID | None = None, role: str = "owner") -> str:
    return create_access_token(
        "acme@example.com",
        role=role,
        extra_claims={
            "user_id": str(uuid.uuid4()),
            "account_id": str(account_id or uuid.uuid4()),
        },
    )


# ---------------------------------------------------------------------------
# get_current_user (admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_accepts_admin_token() -> None:
    token = create_access_token("admin@bridge.com", role="admin")
    identity = await get_current_user(_creds(token))
    assert identity.role == "admin"


@pytest.mark.asyncio
async def test_get_current_user_rejects_owner_token() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_creds(_owner_token()))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_token() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_creds("not-a-real-token"))
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_account_user (owner/member)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_account_user_accepts_owner_token() -> None:
    account_id = uuid.uuid4()
    identity = await get_current_account_user(_creds(_owner_token(account_id)))
    assert identity.role == "owner"
    assert identity.account_id == account_id


@pytest.mark.asyncio
async def test_get_current_account_user_rejects_admin_token() -> None:
    token = create_access_token("admin@bridge.com", role="admin")
    with pytest.raises(HTTPException) as exc:
        await get_current_account_user(_creds(token))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_account_user_rejects_owner_without_account_id() -> None:
    # token de owner sem account_id no payload → não autorizado
    token = create_access_token("acme@example.com", role="owner")
    with pytest.raises(HTTPException) as exc:
        await get_current_account_user(_creds(token))
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# require_feature
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_feature_allows_when_capability_present() -> None:
    dep = require_feature(Feature.API_KEYS)
    identity = MeResponse(
        email="o@x.com", role="owner", user_id=uuid.uuid4(), account_id=uuid.uuid4()
    )
    result = await dep(identity=identity)
    assert result is identity


@pytest.mark.asyncio
async def test_require_feature_denies_when_capability_missing() -> None:
    dep = require_feature(Feature.MEMBERS)
    identity = MeResponse(
        email="m@x.com", role="member", user_id=uuid.uuid4(), account_id=uuid.uuid4()
    )
    with pytest.raises(HTTPException) as exc:
        await dep(identity=identity)
    assert exc.value.status_code == 403
