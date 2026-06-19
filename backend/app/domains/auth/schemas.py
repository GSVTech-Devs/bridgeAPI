import uuid
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator

from app.core.security import validate_password_strength


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    """Troca de senha self-service (usuário do portal altera a própria senha)."""

    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    email: str
    role: str
    user_id: Optional[uuid.UUID] = None
    account_id: Optional[uuid.UUID] = None
