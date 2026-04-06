from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PermissionCreateRequest(BaseModel):
    client_id: uuid.UUID
    api_id: uuid.UUID


class PermissionResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    api_id: uuid.UUID
    granted_at: datetime
    revoked_at: Optional[datetime]

    model_config = {"from_attributes": True}


class PermissionListItem(BaseModel):
    client_id: str
    api_id: str
    client_name: str
    api_name: str
    status: str


class PermissionListResponse(BaseModel):
    items: list[PermissionListItem]
    total: int


class CatalogResponse(BaseModel):
    items: list[dict]
    total: int
