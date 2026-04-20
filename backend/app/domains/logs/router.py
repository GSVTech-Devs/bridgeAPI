from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.mongo_client import get_mongo_db
from app.domains.auth.router import get_current_client, get_current_user
from app.domains.auth.schemas import MeResponse
from app.domains.logs.schemas import LogEntryResponse, LogListResponse
from app.domains.logs.service import get_admin_error_logs, get_admin_logs, get_client_logs

router = APIRouter(tags=["logs"])


@router.get("/logs", response_model=LogListResponse)
async def list_logs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    mongo_db=Depends(get_mongo_db),
    current_client: MeResponse = Depends(get_current_client),
) -> LogListResponse:
    logs = await get_client_logs(
        mongo_db,
        client_id=current_client.email,
        skip=skip,
        limit=limit,
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
