from __future__ import annotations

import asyncio
import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db, get_session_factory
from app.domains.auth.router import get_current_user
from app.domains.auth.schemas import MeResponse
from app.domains.jobs.models import JobStatus
from app.domains.jobs.schemas import JobListResponse, JobResponse
from app.domains.jobs.service import (
    JobNotFoundError,
    get_job,
    list_jobs,
    to_response,
)
from app.domains.proxy.service import authenticate_api_key

router = APIRouter(tags=["jobs"])

_TERMINAL = {JobStatus.DONE.value, JobStatus.FAILED.value, JobStatus.TIMEOUT.value}


# ------------------------------------------------------------------- admin
@router.get("/admin/jobs", response_model=JobListResponse)
async def list_jobs_route(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> JobListResponse:
    items, total = await list_jobs(db, page, per_page)
    return JobListResponse(items=items, total=total)


@router.get("/admin/jobs/{job_id}", response_model=JobResponse)
async def admin_get_job_route(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> JobResponse:
    try:
        job = await get_job(db, str(job_id))
    except JobNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return to_response(job)


# ------------------------------------------------------------------- cliente
async def _authorized_job(db: AsyncSession, presented_key: str | None, job_id: uuid.UUID):
    """Resolve o job garantindo que a X-Bridge-Key pertence à conta dona."""
    if not presented_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Bridge-Key"
        )
    api_key = await authenticate_api_key(db, presented_key)
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key"
        )
    try:
        job = await get_job(db, str(job_id))
    except JobNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if api_key.account_id != job.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_route(
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Status/resultado de um job (polling). Autentica com a mesma X-Bridge-Key."""
    job = await _authorized_job(db, request.headers.get("x-bridge-key"), job_id)
    return to_response(job)


@router.get("/jobs/{job_id}/stream")
async def stream_job_route(
    job_id: uuid.UUID,
    key: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream SSE do job até o estado terminal. EventSource não envia headers,
    então a X-Bridge-Key vai por ``?key=``."""
    await _authorized_job(db, key, job_id)  # autoriza antes de abrir o stream
    interval = settings.job_stream_interval_seconds
    deadline = time.monotonic() + settings.job_stream_max_seconds

    async def gen():
        while True:
            async with get_session_factory()() as session:
                job = await get_job(session, str(job_id))
                payload = to_response(job).model_dump()
            yield f"data: {json.dumps(payload, default=str)}\n\n"
            if job.status in _TERMINAL or time.monotonic() > deadline:
                break
            await asyncio.sleep(interval)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
