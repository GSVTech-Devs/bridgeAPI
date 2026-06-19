from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.domains.accounts.models import AccountStatus, AccountType


class CreateIndividualRequest(BaseModel):
    """Cria um usuário avulso (account individual + usuário responsável)."""

    name: str
    email: EmailStr
    password: str = Field(min_length=8)


class CreateCompanyRequest(BaseModel):
    """Cria uma empresa (account company) + usuário responsável inicial."""

    company_name: str
    owner_email: EmailStr
    owner_password: str = Field(min_length=8)


class AccountResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: AccountType
    status: AccountStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountWithOwnerResponse(BaseModel):
    account: AccountResponse
    owner_email: str
    owner_id: uuid.UUID


class AccountListResponse(BaseModel):
    items: list[AccountResponse]
    total: int
