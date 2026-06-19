from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.security import validate_password_strength
from app.domains.accounts.models import AccountStatus, AccountType


class CreateIndividualRequest(BaseModel):
    """Cria um usuário avulso (account individual + usuário responsável)."""

    name: str
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class CreateCompanyRequest(BaseModel):
    """Cria uma empresa (account company) + usuário responsável inicial."""

    company_name: str
    owner_email: EmailStr
    owner_password: str = Field(min_length=8)

    @field_validator("owner_password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UpdateAccountCredentialsRequest(BaseModel):
    """Atualiza email e/ou senha de acesso do responsável da account.

    Vale tanto para empresas quanto para usuários avulsos — ambos têm um
    usuário responsável (owner) cujas credenciais são o acesso à plataforma.
    """

    email: EmailStr | None = None
    password: str | None = None

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_password_strength(value)

    @model_validator(mode="after")
    def _require_one_field(self) -> "UpdateAccountCredentialsRequest":
        if self.email is None and self.password is None:
            raise ValueError("Informe email e/ou senha para atualizar.")
        return self


class AccountResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: AccountType
    status: AccountStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountListItem(AccountResponse):
    owner_email: str | None = None
    owner_id: uuid.UUID | None = None


class AccountWithOwnerResponse(BaseModel):
    account: AccountResponse
    owner_email: str
    owner_id: uuid.UUID


class AccountCredentialsResponse(BaseModel):
    account_id: uuid.UUID
    owner_id: uuid.UUID
    owner_email: str


class AccountListResponse(BaseModel):
    items: list[AccountListItem]
    total: int
