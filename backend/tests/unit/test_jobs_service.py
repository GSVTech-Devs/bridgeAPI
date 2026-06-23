# Testes unitários para app/domains/jobs/service.py.
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.jobs.models import JobStatus, ProxyJob
from app.domains.jobs.service import (
    JobNotFoundError,
    complete_job,
    create_job,
    get_job,
    get_job_by_idempotency,
)


def make_job(**kw) -> ProxyJob:
    import datetime
    defaults = dict(
        id=uuid.uuid4(), correlation_id="cid", account_id=uuid.uuid4(),
        api_id=uuid.uuid4(), key_id=uuid.uuid4(), idempotency_key=None,
        status=JobStatus.RUNNING.value, request_snapshot={}, result_body=None,
        result_status_code=None, error_code=None, cost=None, latency_ms=None,
        completed_at=None, expires_at=None,
    )
    defaults.update(kw)
    j = ProxyJob()
    for k, v in defaults.items():
        setattr(j, k, v)
    j.created_at = datetime.datetime.now(datetime.timezone.utc)
    return j


@pytest.mark.asyncio
async def test_create_job_sets_running_and_expiry() -> None:
    db = AsyncMock()
    db.add = MagicMock()
    acc, api = uuid.uuid4(), uuid.uuid4()
    job = await create_job(
        db, correlation_id="cid", account_id=acc, api_id=api, key_id=None,
        idempotency_key="k1", request_snapshot={"path": "x"},
    )
    added = db.add.call_args[0][0]
    assert added.status == JobStatus.RUNNING.value
    assert added.account_id == acc
    assert added.idempotency_key == "k1"
    assert added.expires_at is not None
    db.commit.assert_awaited()
    assert job is added


@pytest.mark.asyncio
async def test_get_job_raises_when_missing() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    with pytest.raises(JobNotFoundError):
        await get_job(db, str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_get_job_by_idempotency_returns_match() -> None:
    job = make_job(idempotency_key="k1")
    result = MagicMock()
    result.scalar_one_or_none.return_value = job
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    out = await get_job_by_idempotency(db, job.account_id, "k1")
    assert out is job


@pytest.mark.asyncio
async def test_complete_job_marks_done_with_cost() -> None:
    job = make_job()
    result = MagicMock()
    result.scalar_one_or_none.return_value = job
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    out = await complete_job(
        db, str(job.id), status=JobStatus.DONE, result_body="ok",
        result_status_code=200, cost=0.05, latency_ms=120.0,
    )
    assert out.status == JobStatus.DONE.value
    assert out.result_status_code == 200
    assert out.cost == 0.05
    assert out.completed_at is not None
