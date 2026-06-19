from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import Feature, get_user_capabilities
from app.core.database import get_db
from app.core.security import create_access_token, decode_access_token
from app.domains.accounts.models import AccountStatus
from app.domains.accounts.service import AccountNotFoundError, get_account_by_id
from app.domains.auth.models import UserRole
from app.domains.auth.schemas import LoginRequest, MeResponse, TokenResponse
from app.domains.auth.service import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])

bearer = HTTPBearer()

_ACCOUNT_ROLES = {UserRole.OWNER.value, UserRole.MEMBER.value}


def _build_identity(credentials: HTTPAuthorizationCredentials) -> MeResponse:
    payload = decode_access_token(credentials.credentials)
    return MeResponse(
        email=payload["sub"],
        role=payload.get("role", UserRole.ADMIN.value),
        user_id=payload.get("user_id"),
        account_id=payload.get("account_id"),
    )


def _decode_or_401(credentials: HTTPAuthorizationCredentials) -> MeResponse:
    try:
        return _build_identity(credentials)
    except (JWTError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_identity(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> MeResponse:
    """Qualquer token válido (admin ou usuário de account)."""
    return _decode_or_401(credentials)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> MeResponse:
    """Exige admin da plataforma."""
    identity = _decode_or_401(credentials)
    if identity.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return identity


async def get_current_account_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> MeResponse:
    """Exige usuário vinculado a uma account (owner ou member)."""
    identity = _decode_or_401(credentials)
    if identity.role not in _ACCOUNT_ROLES or identity.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return identity


def require_feature(feature: Feature):
    """Dependency que exige uma capability de dashboard.

    Seam para o RBAC por membro futuro: hoje deriva do papel.
    """

    async def _dep(
        identity: MeResponse = Depends(get_current_account_user),
    ) -> MeResponse:
        if feature not in get_user_capabilities(identity.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature not allowed: {feature.value}",
            )
        return identity

    return _dep


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Login do admin da plataforma."""
    user = await authenticate_user(db, body.email, body.password)
    if user is None or user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        user.email, role=user.role, extra_claims={"user_id": str(user.id)}
    )
    return TokenResponse(access_token=token)


@router.post("/portal/login", response_model=TokenResponse)
async def portal_login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Login dos usuários de account (responsável/membro)."""
    user = await authenticate_user(db, body.email, body.password)
    if user is None or user.role not in _ACCOUNT_ROLES or user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        account = await get_account_by_id(db, str(user.account_id))
    except AccountNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if account.status != AccountStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {account.status}. Contact the administrator.",
        )
    token = create_access_token(
        user.email,
        role=user.role,
        extra_claims={"user_id": str(user.id), "account_id": str(user.account_id)},
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
async def me(
    current: MeResponse = Depends(get_current_identity),
) -> MeResponse:
    return current
