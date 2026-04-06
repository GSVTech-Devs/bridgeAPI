from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.router import get_current_client, get_current_user
from app.domains.auth.schemas import MeResponse
from app.domains.clients.service import get_client_by_email
from app.domains.metrics.schemas import DashboardResponse
from app.domains.metrics.service import get_admin_global_metrics, get_client_dashboard

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
