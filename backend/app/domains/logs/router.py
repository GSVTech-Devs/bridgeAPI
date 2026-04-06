from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.mongo_client import get_mongo_db
from app.domains.auth.router import get_current_client
from app.domains.auth.schemas import MeResponse
from app.domains.logs.schemas import LogEntryResponse, LogListResponse
from app.domains.logs.service import get_client_logs

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
