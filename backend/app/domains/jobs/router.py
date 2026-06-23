from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.router import get_current_user
from app.domains.auth.schemas import MeResponse
from app.domains.jobs.schemas import JobListResponse, JobResponse
from app.domains.jobs.service import (
    JobNotFoundError,
    get_job,
    list_jobs,
    to_response,
)
from app.domains.proxy.service import authenticate_api_key

router = APIRouter(tags=["jobs"])


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs_route(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> JobListResponse:
    """Lista de jobs (admin)."""
    items, total = await list_jobs(db, page, per_page)
    return JobListResponse(items=items, total=total)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_route(
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Status/resultado de um job. O cliente autentica com a mesma X-Bridge-Key
    da consulta; só vê jobs da própria conta."""
    presented_key = request.headers.get("x-bridge-key")
    if not presented_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Bridge-Key header"
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
    # Não vaza job de outra conta — trata como inexistente.
    if api_key.account_id != job.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return to_response(job)
