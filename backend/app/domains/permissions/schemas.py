from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PermissionCreateRequest(BaseModel):
    account_id: uuid.UUID
    api_id: uuid.UUID
    proxy_managed_by_client: bool = False
    captcha_managed_by_client: bool = False


class PermissionConfigRequest(BaseModel):
    proxy_managed_by_client: Optional[bool] = None
    captcha_managed_by_client: Optional[bool] = None


class PermissionResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    api_id: uuid.UUID
    granted_at: datetime
    revoked_at: Optional[datetime]
    proxy_managed_by_client: bool = False
    captcha_managed_by_client: bool = False

    model_config = {"from_attributes": True}


class PermissionListItem(BaseModel):
    account_id: str
    api_id: str
    account_name: str
    api_name: str
    status: str
    proxy_managed_by_client: bool = False
    captcha_managed_by_client: bool = False


class PermissionListResponse(BaseModel):
    items: list[PermissionListItem]
    total: int


class CatalogResponse(BaseModel):
    items: list[dict]
    total: int
