from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.authz import ASSIGNABLE_FEATURES
from app.core.security import validate_password_strength

_ASSIGNABLE_VALUES = {f.value for f in ASSIGNABLE_FEATURES}


def _validate_capabilities(values: list[str]) -> list[str]:
    invalid = sorted(set(values) - _ASSIGNABLE_VALUES)
    if invalid:
        raise ValueError(f"Capabilities inválidas: {', '.join(invalid)}")
    # remove duplicatas preservando determinismo
    return sorted(set(values))


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    capabilities: list[str] = Field(default_factory=list)

    @field_validator("capabilities")
    @classmethod
    def _check_capabilities(cls, value: list[str]) -> list[str]:
        return _validate_capabilities(value)


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    capabilities: Optional[list[str]] = None

    @field_validator("capabilities")
    @classmethod
    def _check_capabilities(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return value
        return _validate_capabilities(value)

    @model_validator(mode="after")
    def _require_one_field(self) -> "RoleUpdate":
        if self.name is None and self.capabilities is None:
            raise ValueError("Informe name e/ou capabilities para atualizar.")
        return self


class RoleResponse(BaseModel):
    id: uuid.UUID
    name: str
    capabilities: list[str]
    member_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role_id: uuid.UUID

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class MemberUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    role_id: Optional[uuid.UUID] = None

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return validate_password_strength(value)

    @model_validator(mode="after")
    def _require_one_field(self) -> "MemberUpdate":
        if self.email is None and self.password is None and self.role_id is None:
            raise ValueError("Informe ao menos um campo para atualizar.")
        return self


class MemberResponse(BaseModel):
    id: uuid.UUID
    email: str
    role_id: Optional[uuid.UUID] = None
    role_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleListResponse(BaseModel):
    items: list[RoleResponse]


class MemberListResponse(BaseModel):
    items: list[MemberResponse]
