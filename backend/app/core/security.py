from __future__ import annotations

import base64
import hashlib
import re
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Requisitos mínimos de senha: 8+ caracteres, ao menos uma letra maiúscula,
# um número e um caractere especial (qualquer não-alfanumérico).
PASSWORD_MIN_LENGTH = 8
PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")
PASSWORD_REQUIREMENTS_MESSAGE = (
    "A senha deve ter no mínimo 8 caracteres e incluir ao menos uma letra "
    "maiúscula, um número e um caractere especial."
)


def validate_password_strength(password: str) -> str:
    """Valida a força da senha; levanta ``ValueError`` se não atender aos
    requisitos mínimos. Retorna a própria senha para uso em validators."""
    if not PASSWORD_PATTERN.match(password):
        raise ValueError(PASSWORD_REQUIREMENTS_MESSAGE)
    return password


def _get_fernet() -> Fernet:
    key_bytes = hashlib.sha256(settings.encryption_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def encrypt_value(plain: str) -> str:
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    return _get_fernet().decrypt(encrypted.encode()).decode()


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(
    subject: str,
    role: str = "admin",
    expires_delta: timedelta | None = None,
    extra_claims: dict | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.jwt_expire_minutes)
    )
    payload = {"sub": subject, "role": role, "exp": expire}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload, settings.app_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token, settings.app_secret_key, algorithms=[settings.jwt_algorithm]
    )
