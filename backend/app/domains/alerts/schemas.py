from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AlertResponse(BaseModel):
    id: uuid.UUID
    account_id: Optional[uuid.UUID] = None
    api_id: Optional[uuid.UUID] = None
    api_name: Optional[str] = None
    resource_id: Optional[uuid.UUID] = None
    type: str
    severity: str
    status: str
    message: str
    context: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None


class AlertListResponse(BaseModel):
    items: list[AlertResponse]
    total: int
    active_count: int
