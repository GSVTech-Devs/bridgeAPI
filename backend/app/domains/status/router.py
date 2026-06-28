from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.mongo_client import get_mongo_db
from app.core.authz import Feature
from app.core.security import decode_access_token
from app.domains.auth.models import UserRole
from app.domains.auth.router import get_current_user, require_feature
from app.domains.auth.schemas import MeResponse
from app.domains.status.schemas import (
    ClientStatusItem,
    ClientStatusResponse,
    StatusEventItem,
    StatusEventsResponse,
    StatusOverviewItem,
    StatusOverviewResponse,
)
from app.domains.status.service import get_client_overview, get_events, get_overview

router = APIRouter(tags=["status"])


def _require_admin_token(token: str) -> None:
    """Valida um JWT de admin vindo por query param (para o stream SSE, já que
    EventSource não envia o header Authorization)."""
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    if payload.get("role") != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )


@router.get("/status/overview", response_model=StatusOverviewResponse)
async def status_overview(
    mongo_db=Depends(get_mongo_db),
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> StatusOverviewResponse:
    docs = await get_overview(mongo_db, db)
    items = [StatusOverviewItem(**d) for d in docs]
    return StatusOverviewResponse(items=items, total=len(items))


@router.get("/client/status", response_model=ClientStatusResponse)
async def client_status(
    mongo_db=Depends(get_mongo_db),
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(require_feature(Feature.CATALOG)),
) -> ClientStatusResponse:
    """Status das APIs liberadas para a conta do cliente. Escopado por permissão;
    checks de proxy/captcha desativados no cadastro são omitidos."""
    docs = await get_client_overview(mongo_db, db, identity.account_id)
    items = [ClientStatusItem(**d) for d in docs]
    return ClientStatusResponse(items=items, total=len(items))


@router.get("/status/events", response_model=StatusEventsResponse)
async def status_events(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    mongo_db=Depends(get_mongo_db),
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> StatusEventsResponse:
    docs = await get_events(mongo_db, db, skip=skip, limit=limit)
    items = [StatusEventItem(**d) for d in docs]
    return StatusEventsResponse(items=items, total=len(items))


@router.get("/status/stream")
async def status_stream(
    request: Request,
    token: str = Query(...),
    mongo_db=Depends(get_mongo_db),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream SSE do overview, atualizado a cada N segundos (painel em tempo real)."""
    _require_admin_token(token)
    interval = settings.status_stream_interval_seconds

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            docs = await get_overview(mongo_db, db)
            payload = json.dumps({"items": docs, "total": len(docs)}, default=str)
            yield f"data: {payload}\n\n"
            await asyncio.sleep(interval)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
