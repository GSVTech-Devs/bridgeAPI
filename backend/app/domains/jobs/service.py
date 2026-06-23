from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domains.jobs.models import JobStatus, ProxyJob
from app.domains.jobs.schemas import JobListItem, JobResponse


class JobNotFoundError(Exception):
    pass


def to_response(job: ProxyJob) -> JobResponse:
    return JobResponse(
        id=job.id,
        status=job.status,
        correlation_id=job.correlation_id,
        api_id=job.api_id,
        result_status_code=job.result_status_code,
        result_body=job.result_body,
        error_code=job.error_code,
        cost=job.cost,
        latency_ms=job.latency_ms,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


async def create_job(
    db: AsyncSession,
    *,
    correlation_id: str,
    account_id: uuid.UUID,
    api_id: uuid.UUID,
    key_id: uuid.UUID | None,
    idempotency_key: str | None,
    request_snapshot: dict,
) -> ProxyJob:
    now = datetime.now(timezone.utc)
    job = ProxyJob(
        correlation_id=correlation_id,
        account_id=account_id,
        api_id=api_id,
        key_id=key_id,
        idempotency_key=idempotency_key,
        status=JobStatus.RUNNING.value,
        request_snapshot=request_snapshot,
        created_at=now,
        expires_at=now + timedelta(hours=settings.job_retention_hours),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def get_job(db: AsyncSession, job_id: str) -> ProxyJob:
    result = await db.execute(
        select(ProxyJob).where(ProxyJob.id == uuid.UUID(str(job_id)))
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise JobNotFoundError(f"Job not found: {job_id}")
    return job


async def get_job_by_idempotency(
    db: AsyncSession, account_id: uuid.UUID, idempotency_key: str
) -> ProxyJob | None:
    result = await db.execute(
        select(ProxyJob).where(
            ProxyJob.account_id == account_id,
            ProxyJob.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def complete_job(
    db: AsyncSession,
    job_id: str,
    *,
    status: JobStatus,
    result_body: str | None = None,
    result_status_code: int | None = None,
    error_code: str | None = None,
    cost: float | None = None,
    latency_ms: float | None = None,
) -> ProxyJob:
    job = await get_job(db, job_id)
    job.status = status.value
    job.result_body = result_body
    job.result_status_code = result_status_code
    job.error_code = error_code
    job.cost = cost
    job.latency_ms = latency_ms
    job.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(job)
    return job


async def list_jobs(
    db: AsyncSession, page: int = 1, per_page: int = 20
) -> tuple[list[JobListItem], int]:
    total = (await db.execute(select(func.count()).select_from(ProxyJob))).scalar_one()
    result = await db.execute(
        select(ProxyJob)
        .order_by(ProxyJob.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    items = [
        JobListItem(
            id=j.id,
            status=j.status,
            correlation_id=j.correlation_id,
            account_id=j.account_id,
            api_id=j.api_id,
            result_status_code=j.result_status_code,
            error_code=j.error_code,
            cost=j.cost,
            created_at=j.created_at,
            completed_at=j.completed_at,
        )
        for j in result.scalars().all()
    ]
    return items, total
