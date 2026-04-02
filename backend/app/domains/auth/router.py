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


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> MeResponse:
    try:
        payload = decode_access_token(credentials.credentials)
        email: str = payload["sub"]
    except (JWTError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return MeResponse(email=email, role="admin")


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
    token = create_access_token(user.email)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
async def me(current_user: MeResponse = Depends(get_current_user)) -> MeResponse:
    return current_user
