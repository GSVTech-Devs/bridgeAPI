from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.mongo_client import get_mongo_db
from app.domains.auth.router import get_current_client, get_current_user
from app.domains.auth.schemas import MeResponse
from app.domains.clients.service import get_client_by_email
from app.domains.logs.schemas import LogEntryResponse, LogListResponse
from app.domains.logs.service import get_admin_error_logs, get_admin_logs, get_client_logs

router = APIRouter(tags=["logs"])


@router.get("/logs", response_model=LogListResponse)
async def list_logs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    api_id: Optional[str] = Query(default=None),
    mongo_db=Depends(get_mongo_db),
    current_client: MeResponse = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> LogListResponse:
    client = await get_client_by_email(db, current_client.email)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    logs = await get_client_logs(
        mongo_db,
        client_id=str(client.id),
        skip=skip,
        limit=limit,
        api_id=api_id,
    )
    items = [LogEntryResponse(**doc) for doc in logs]
    return LogListResponse(items=items, total=len(items))


@router.get("/logs/admin", response_model=LogListResponse)
async def list_admin_logs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    mongo_db=Depends(get_mongo_db),
    _: MeResponse = Depends(get_current_user),
) -> LogListResponse:
    logs = await get_admin_logs(mongo_db, skip=skip, limit=limit)
    items = [LogEntryResponse(**doc) for doc in logs]
    return LogListResponse(items=items, total=len(items))


@router.get("/logs/admin/errors", response_model=LogListResponse)
async def list_admin_error_logs(
    api_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    mongo_db=Depends(get_mongo_db),
    _: MeResponse = Depends(get_current_user),
) -> LogListResponse:
    logs = await get_admin_error_logs(mongo_db, api_id=api_id, skip=skip, limit=limit)
    items = [LogEntryResponse(**doc) for doc in logs]
    return LogListResponse(items=items, total=len(items))
