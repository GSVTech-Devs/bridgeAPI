from __future__ import annotations

from pydantic import BaseModel


class DashboardResponse(BaseModel):
    total_requests: int
    error_rate: float
    avg_latency_ms: float
    total_cost: float
    billable_requests: int
    non_billable_requests: int


class ApiMetricItem(BaseModel):
    api_id: str
    api_name: str
    total_requests: int
    error_rate: float


class ApiBreakdownResponse(BaseModel):
    items: list[ApiMetricItem]
