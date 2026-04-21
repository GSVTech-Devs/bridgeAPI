from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class LogEntryResponse(BaseModel):
    correlation_id: str
    client_id: str
    api_id: str
    key_id: str
    key_name: Optional[str] = None
    path: str
    method: str
    status_code: int
    latency_ms: float
    request_headers: dict[str, str]
    response_headers: dict[str, str]
    request_body: Optional[str] = None
    response_body: Optional[str] = None
    created_at: Optional[Any] = None
    expires_at: Optional[Any] = None


class LogListResponse(BaseModel):
    items: list[LogEntryResponse]
    total: int
