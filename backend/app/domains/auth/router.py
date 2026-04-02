from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, decode_access_token
from app.domains.auth.schemas import LoginRequest, MeResponse, TokenResponse
from app.domains.auth.service import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])

bearer = HTTPBearer()


def _build_identity(credentials: HTTPAuthorizationCredentials) -> MeResponse:
    payload = decode_access_token(credentials.credentials)
    email = payload["sub"]
    role = payload.get("role", "admin")
    return MeResponse(email=email, role=role)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> MeResponse:
    try:
        identity = _build_identity(credentials)
    except (JWTError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if identity.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return identity


async def get_current_client(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> MeResponse:
    try:
        identity = _build_identity(credentials)
    except (JWTError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if identity.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return identity


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user.email, role=user.role)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
async def me(current_user: MeResponse = Depends(get_current_user)) -> MeResponse:
    return current_user
