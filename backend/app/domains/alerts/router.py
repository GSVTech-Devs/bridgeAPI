"""HTTP dos alertas (Fase 6): admin (`/admin/alerts`) vê todos; cliente
(`/client/alerts`) vê só os da própria conta. Ambos podem dar ack."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.alerts.schemas import AlertListResponse, AlertResponse
from app.domains.alerts.service import (
    AlertNotFoundError,
    acknowledge_alert,
    list_alerts,
    to_response,
)
from app.domains.auth.router import get_current_account_user, get_current_user
from app.domains.auth.schemas import MeResponse

admin_router = APIRouter(tags=["alerts"])
client_router = APIRouter(tags=["alerts"])


# ------------------------------------------------------------------- admin
@admin_router.get("/admin/alerts", response_model=AlertListResponse)
async def admin_list_alerts(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> AlertListResponse:
    return await list_alerts(
        db, account_id=None, is_admin=True, status=status, page=page, per_page=per_page
    )


@admin_router.post("/admin/alerts/{alert_id}/ack", response_model=AlertResponse)
async def admin_ack_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> AlertResponse:
    try:
        alert = await acknowledge_alert(db, str(alert_id), account_id=None, is_admin=True)
    except AlertNotFoundError:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return to_response(alert)


# ------------------------------------------------------------------- cliente
@client_router.get("/client/alerts", response_model=AlertListResponse)
async def client_list_alerts(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(get_current_account_user),
) -> AlertListResponse:
    account_id = uuid.UUID(str(identity.account_id))
    return await list_alerts(
        db, account_id=account_id, is_admin=False, status=status, page=page, per_page=per_page
    )


@client_router.post("/client/alerts/{alert_id}/ack", response_model=AlertResponse)
async def client_ack_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(get_current_account_user),
) -> AlertResponse:
    account_id = uuid.UUID(str(identity.account_id))
    try:
        alert = await acknowledge_alert(
            db, str(alert_id), account_id=account_id, is_admin=False
        )
    except AlertNotFoundError:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return to_response(alert)
