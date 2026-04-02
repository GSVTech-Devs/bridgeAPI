from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.jwt_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(
        payload, settings.app_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token, settings.app_secret_key, algorithms=[settings.jwt_algorithm]
    )
