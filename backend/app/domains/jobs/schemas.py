from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class JobResponse(BaseModel):
    id: uuid.UUID
    status: str
    correlation_id: str
    api_id: uuid.UUID
    result_status_code: Optional[int] = None
    result_body: Optional[str] = None
    error_code: Optional[str] = None
    cost: Optional[float] = None
    latency_ms: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class JobListItem(BaseModel):
    id: uuid.UUID
    status: str
    correlation_id: str
    account_id: uuid.UUID
    api_id: uuid.UUID
    result_status_code: Optional[int] = None
    error_code: Optional[str] = None
    cost: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class JobListResponse(BaseModel):
    items: list[JobListItem]
    total: int
