from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.router import get_current_client, get_current_user
from app.domains.auth.schemas import MeResponse
from app.domains.clients.service import get_client_by_email
from app.domains.metrics.schemas import ApiBreakdownResponse, ClientApiDetailResponse, ClientApiUsageResponse, ClientSummaryResponse, DashboardResponse
from app.domains.metrics.service import get_admin_global_metrics, get_client_api_detail, get_client_dashboard, get_clients_usage_summary, get_metrics_by_api, get_usage_by_client_and_api

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/dashboard", response_model=DashboardResponse)
async def client_dashboard(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    current_client: MeResponse = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    client = await get_client_by_email(db, current_client.email)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    data = await get_client_dashboard(db, client.id, since=since, until=until)
    return DashboardResponse(**data)


@router.get("/admin", response_model=DashboardResponse)
async def admin_metrics(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    _: MeResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    data = await get_admin_global_metrics(db, since=since, until=until)
    return DashboardResponse(**data)


@router.get("/admin/usage", response_model=ClientApiUsageResponse)
async def admin_usage(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    _: MeResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClientApiUsageResponse:
    items = await get_usage_by_client_and_api(db, since=since, until=until)
    return ClientApiUsageResponse(items=items)


@router.get("/admin/clients/summary", response_model=ClientSummaryResponse)
async def admin_clients_summary(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    _: MeResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClientSummaryResponse:
    items = await get_clients_usage_summary(db, since=since, until=until)
    return ClientSummaryResponse(items=items)


@router.get("/admin/clients/{client_id}", response_model=ClientApiDetailResponse)
async def admin_client_detail(
    client_id: str,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    _: MeResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClientApiDetailResponse:
    items = await get_client_api_detail(db, client_id, since=since, until=until)
    total_cost = sum(i["total_cost"] for i in items)
    total_requests = sum(i["total_requests"] for i in items)
    return ClientApiDetailResponse(
        items=items,
        client_id=client_id,
        total_cost=total_cost,
        total_requests=total_requests,
    )


@router.get("/admin/breakdown", response_model=ApiBreakdownResponse)
async def admin_metrics_breakdown(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    _: MeResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiBreakdownResponse:
    items = await get_metrics_by_api(db, since=since, until=until)
    return ApiBreakdownResponse(items=items)
