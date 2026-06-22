from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import Feature
from app.core.database import get_db
from app.domains.auth.router import get_current_user, require_feature
from app.domains.auth.schemas import MeResponse
from app.domains.members.service import resolve_user_capabilities
from app.domains.metrics.schemas import (
    ApiBreakdownResponse,
    ClientApiBreakdownResponse,
    ClientApiDetailResponse,
    ClientApiUsageResponse,
    ClientStatusCodesResponse,
    ClientSummaryResponse,
    DashboardResponse,
    KeyBreakdownResponse,
)
from app.domains.metrics.service import (
    get_admin_global_metrics,
    get_client_api_detail,
    get_client_dashboard,
    get_client_requests_by_key,
    get_client_status_codes,
    get_clients_usage_summary,
    get_metrics_by_api,
    get_usage_by_client_and_api,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/dashboard", response_model=DashboardResponse)
async def client_dashboard(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    identity: MeResponse = Depends(require_feature(Feature.METRICS)),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    data = await get_client_dashboard(db, identity.account_id, since=since, until=until)
    capabilities = await resolve_user_capabilities(db, identity)
    if Feature.FINANCIAL.value not in capabilities:
        data = {
            **data,
            "total_cost": None,
            "billable_requests": None,
            "non_billable_requests": None,
        }
    return DashboardResponse(**data)


@router.get("/client/by-api", response_model=ClientApiBreakdownResponse)
async def client_by_api(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    identity: MeResponse = Depends(require_feature(Feature.CLIENT_USAGE)),
    db: AsyncSession = Depends(get_db),
) -> ClientApiBreakdownResponse:
    items = await get_client_api_detail(
        db, str(identity.account_id), since=since, until=until
    )
    capabilities = await resolve_user_capabilities(db, identity)
    if Feature.FINANCIAL.value not in capabilities:
        items = [{**item, "total_cost": None} for item in items]
    return ClientApiBreakdownResponse(items=items)


@router.get("/client/by-key", response_model=KeyBreakdownResponse)
async def client_by_key(
    api_id: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    identity: MeResponse = Depends(require_feature(Feature.CLIENT_USAGE)),
    db: AsyncSession = Depends(get_db),
) -> KeyBreakdownResponse:
    import uuid as _uuid

    api_uuid = _uuid.UUID(api_id) if api_id else None
    items = await get_client_requests_by_key(
        db, identity.account_id, api_id=api_uuid, since=since, until=until
    )
    return KeyBreakdownResponse(items=items)


@router.get("/client/status-codes", response_model=ClientStatusCodesResponse)
async def client_status_codes(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    identity: MeResponse = Depends(require_feature(Feature.CLIENT_USAGE)),
    db: AsyncSession = Depends(get_db),
) -> ClientStatusCodesResponse:
    items = await get_client_status_codes(
        db, identity.account_id, since=since, until=until
    )
    return ClientStatusCodesResponse(items=items)


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
