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


class AppLogEntryResponse(BaseModel):
    correlation_id: str
    api_id: str
    level: str
    event: str
    message: Optional[str] = None
    timestamp: Optional[Any] = None
    duration_ms: Optional[float] = None
    proxy_id: Optional[str] = None
    captcha_provider: Optional[str] = None
    error_code: Optional[str] = None
    api_version: Optional[str] = None
    sdk_version: Optional[str] = None
    extra: dict[str, Any] = {}
    created_at: Optional[Any] = None


class AppLogListResponse(BaseModel):
    items: list[AppLogEntryResponse]
    total: int


class TraceItem(BaseModel):
    """Item normalizado da timeline unificada (gateway + app)."""

    source: str  # "gateway" | "app"
    correlation_id: str
    timestamp: Optional[Any] = None
    created_at: Optional[Any] = None
    # campos do gateway (request_logs)
    path: Optional[str] = None
    method: Optional[str] = None
    status_code: Optional[int] = None
    latency_ms: Optional[float] = None
    # campos da app (app_logs)
    level: Optional[str] = None
    event: Optional[str] = None
    message: Optional[str] = None
    error_code: Optional[str] = None
    proxy_id: Optional[str] = None
    captcha_provider: Optional[str] = None


class TraceResponse(BaseModel):
    correlation_id: str
    items: list[TraceItem]
    total: int
