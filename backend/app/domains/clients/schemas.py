from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.domains.clients.models import ClientStatus


class ClientRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class ClientLoginRequest(BaseModel):
    email: EmailStr
    password: str


class ClientResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    status: ClientStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class ClientListResponse(BaseModel):
    items: list[ClientResponse]
    total: int
