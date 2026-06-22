import uuid
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

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


class CompanyOption(BaseModel):
    """Uma empresa/account à qual o email logado tem acesso (para o seletor)."""

    account_id: uuid.UUID
    name: str
    type: str
    role: str


class PortalLoginResponse(BaseModel):
    """Resposta do login do portal.

    ``access_token`` é um token de identidade (sem account selecionada): só
    serve para listar empresas e selecionar uma via ``/auth/portal/select``.
    ``companies`` lista as accounts ativas acessíveis pelo email.
    """

    access_token: str
    token_type: str = "bearer"
    companies: list[CompanyOption]


class SelectCompanyRequest(BaseModel):
    account_id: uuid.UUID


class CompaniesResponse(BaseModel):
    companies: list[CompanyOption]


class MeResponse(BaseModel):
    email: str
    role: str
    user_id: Optional[uuid.UUID] = None
    account_id: Optional[uuid.UUID] = None
    # Preenchidos apenas no endpoint /auth/me (para a UI decidir o que mostrar).
    capabilities: list[str] = Field(default_factory=list)
    account_type: Optional[str] = None
    account_name: Optional[str] = None
    is_owner: bool = False
    # Quantas empresas/accounts este email acessa (para exibir "Trocar empresa").
    account_count: int = 0
