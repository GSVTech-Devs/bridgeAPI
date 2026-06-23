from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class StatusReportIn(BaseModel):
    """Relatório de readiness enviado por uma API via POST /ingest/status.

    O ``api_id`` NÃO vem no corpo — é derivado do service token autenticado.
    """

    status: str  # healthy | degraded | down
    sdk_version: Optional[str] = None
    uptime_s: Optional[int] = None
    checks: dict[str, Any] = Field(default_factory=dict)


class StatusOverviewItem(BaseModel):
    api_id: str
    api_name: Optional[str] = None
    status: str            # healthy | degraded | down | unknown
    reported_status: Optional[str] = None  # último status reportado (antes de stale)
    sdk_version: Optional[str] = None
    uptime_s: Optional[int] = None
    checks: dict[str, Any] = {}
    last_seen: Optional[Any] = None
    stale: bool = False


class StatusOverviewResponse(BaseModel):
    items: list[StatusOverviewItem]
    total: int


class StatusEventItem(BaseModel):
    api_id: str
    api_name: Optional[str] = None
    from_status: str
    to_status: str
    at: Optional[Any] = None


class StatusEventsResponse(BaseModel):
    items: list[StatusEventItem]
    total: int
