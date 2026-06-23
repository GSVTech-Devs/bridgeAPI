"""Finalização em background de um job: aguarda o forward (já iniciado no
dispatch) terminar, persiste o resultado no job, registra métrica/billing e o
request log — tudo com recursos PRÓPRIOS (sessão e cliente HTTP), já que a
request original já respondeu 202 e seus recursos foram fechados."""
from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.database import get_session_factory
from app.core.mongo_client import mongo_database
from app.domains.jobs.models import JobStatus
from app.domains.jobs.service import complete_job
from app.domains.logs.service import write_request_log
from app.domains.metrics.service import record_metric

_RESULT_BODY_MAX = 1_000_000  # 1 MB guardado no job


async def _persist(
    job_id: str,
    meta: dict[str, Any],
    *,
    status: JobStatus,
    metric_status_code: int,
    result_body: str | None = None,
    result_status_code: int | None = None,
    error_code: str | None = None,
    cost: float | None = None,
    latency_ms: float | None = None,
    response_log: dict | None = None,
) -> None:
    async with get_session_factory()() as session:
        await complete_job(
            session,
            job_id,
            status=status,
            result_body=result_body,
            result_status_code=result_status_code,
            error_code=error_code,
            cost=cost,
            latency_ms=latency_ms,
        )
        await record_metric(
            db=session,
            account_id=meta["account_id"],
            api_id=meta["api_id"],
            key_id=meta["key_id"],
            path=meta["path"],
            method=meta["method"],
            status_code=metric_status_code,
            latency_ms=latency_ms or 0.0,
            cost=cost,
        )

    mongo_db = mongo_database()
    if mongo_db is not None and response_log is not None:
        try:
            await write_request_log(mongo_db, {**meta["log_base"], **response_log})
        except Exception:
            pass  # log é best-effort


async def finalize_job(job_id: str, task, meta: dict[str, Any], bg_client: httpx.AsyncClient) -> None:
    latency_ms = (time.monotonic() - meta["start"]) * 1000
    try:
        try:
            resp: httpx.Response = task.result()
        except httpx.TimeoutException:
            await _persist(
                job_id, meta, status=JobStatus.TIMEOUT, metric_status_code=504,
                error_code="TARGET_TIMEOUT", latency_ms=latency_ms,
            )
            return
        except Exception as exc:  # noqa: BLE001
            await _persist(
                job_id, meta, status=JobStatus.FAILED, metric_status_code=502,
                error_code="BRIDGE_ERROR", result_body=str(exc)[:512], latency_ms=latency_ms,
            )
            return

        status_code = resp.status_code
        cost = meta["cost_per_query"] if status_code == 200 else None
        await _persist(
            job_id, meta,
            status=JobStatus.DONE,
            metric_status_code=status_code,
            result_body=resp.text[:_RESULT_BODY_MAX],
            result_status_code=status_code,
            cost=cost,
            latency_ms=latency_ms,
            response_log={
                "status_code": status_code,
                "latency_ms": latency_ms,
                "response_headers": dict(resp.headers),
                "response_body": resp.text[:4096],
            },
        )
    finally:
        await bg_client.aclose()
