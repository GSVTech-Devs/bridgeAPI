from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DashboardResponse(BaseModel):
    total_requests: int
    error_rate: float
    avg_latency_ms: float
    # Campos de custo/faturamento: ficam ``None`` quando o usuário não tem a
    # capability ``financial`` (não vazamos custo via API).
    total_cost: Optional[float] = None
    billable_requests: Optional[int] = None
    non_billable_requests: Optional[int] = None


class ApiMetricItem(BaseModel):
    api_id: str
    api_name: str
    total_requests: int
    error_rate: float


class ApiBreakdownResponse(BaseModel):
    items: list[ApiMetricItem]


class ClientApiUsageItem(BaseModel):
    client_id: str
    client_name: str
    client_email: str
    api_id: str
    api_name: str
    total_requests: int
    total_cost: float


class ClientApiUsageResponse(BaseModel):
    items: list[ClientApiUsageItem]


class ClientSummaryItem(BaseModel):
    client_id: str
    client_name: str
    client_email: str
    total_requests: int
    error_count: int
    success_count: int
    total_cost: float


class ClientSummaryResponse(BaseModel):
    items: list[ClientSummaryItem]


class ClientApiDetailItem(BaseModel):
    api_id: str
    api_name: str
    total_requests: int
    error_count: int
    success_count: int
    total_cost: float


class ClientApiDetailResponse(BaseModel):
    items: list[ClientApiDetailItem]
    client_id: str
    total_cost: float
    total_requests: int


class ClientApiBreakdownItem(BaseModel):
    api_id: str
    api_name: str
    total_requests: int
    error_count: int
    success_count: int
    # ``None`` quando o usuário não tem a capability ``financial``.
    total_cost: Optional[float] = None


class ClientApiBreakdownResponse(BaseModel):
    items: list[ClientApiBreakdownItem]


class StatusCodeItem(BaseModel):
    api_id: str
    api_name: str
    status_code: int
    count: int


class ClientStatusCodesResponse(BaseModel):
    items: list[StatusCodeItem]


class KeyBreakdownItem(BaseModel):
    key_id: str
    key_name: str
    key_prefix: str
    total_requests: int


class KeyBreakdownResponse(BaseModel):
    items: list[KeyBreakdownItem]
