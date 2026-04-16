# RED → GREEN
# Testes para get_current_client (dependency usada por rotas de cliente).
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import create_access_token
from app.domains.auth.router import get_current_client


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.mark.asyncio
async def test_get_current_client_accepts_client_token() -> None:
    token = create_access_token("acme@example.com", role="client")

    identity = await get_current_client(_creds(token))

    assert identity.email == "acme@example.com"
    assert identity.role == "client"


@pytest.mark.asyncio
async def test_get_current_client_rejects_admin_token() -> None:
    token = create_access_token("admin@bridge.com", role="admin")

    with pytest.raises(HTTPException) as exc:
        await get_current_client(_creds(token))

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_client_rejects_invalid_token() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_client(_creds("not-a-real-token"))

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_client_rejects_payload_without_sub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Se o JWT decodifica mas não tem 'sub', o KeyError vira 401."""
    from app.domains.auth import router as auth_router

    monkeypatch.setattr(
        auth_router, "decode_access_token", lambda _t: {"role": "client"}
    )

    with pytest.raises(HTTPException) as exc:
        await get_current_client(_creds("any"))

    assert exc.value.status_code == 401
