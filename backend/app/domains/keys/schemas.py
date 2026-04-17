from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.domains.keys.models import APIKeyStatus


class APIKeyCreateRequest(BaseModel):
    name: str
    api_id: uuid.UUID


class APIKeyResponse(BaseModel):
    id: uuid.UUID
    api_id: Optional[uuid.UUID]
    name: str
    key_prefix: str
    status: APIKeyStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class APIKeyCreateResponse(APIKeyResponse):
    api_key: str


class APIKeyListResponse(BaseModel):
    items: list[APIKeyResponse]
