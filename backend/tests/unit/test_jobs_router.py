# Camada HTTP dos jobs: GET /jobs/{id} (cliente) e GET /jobs (admin).
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.domains.jobs.schemas import JobResponse


def admin_headers() -> dict:
    return {"Authorization": f"Bearer {create_access_token('admin@bridge.com', role='admin')}"}


def make_job_response(**kw) -> JobResponse:
    base = dict(
        id=uuid.uuid4(), status="done", correlation_id="cid", api_id=uuid.uuid4(),
        result_status_code=200, result_body='{"ok":true}', error_code=None,
        cost=0.05, latency_ms=120.0, created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    base.update(kw)
    return JobResponse(**base)


@pytest.mark.asyncio
async def test_get_job_requires_key(client: AsyncClient) -> None:
    resp = await client.get(f"/jobs/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_job_returns_when_owner(client: AsyncClient) -> None:
    account_id = uuid.uuid4()
    api_key = MagicMock(account_id=account_id)
    job = MagicMock(account_id=account_id)
    with patch(
        "app.domains.jobs.router.authenticate_api_key",
        new=AsyncMock(return_value=api_key),
    ), patch(
        "app.domains.jobs.router.get_job", new=AsyncMock(return_value=job)
    ), patch(
        "app.domains.jobs.router.to_response",
        new=MagicMock(return_value=make_job_response()),
    ):
        resp = await client.get(
            f"/jobs/{uuid.uuid4()}", headers={"X-Bridge-Key": "brg_x"}
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


@pytest.mark.asyncio
async def test_get_job_hides_other_accounts(client: AsyncClient) -> None:
    api_key = MagicMock(account_id=uuid.uuid4())
    job = MagicMock(account_id=uuid.uuid4())  # outra conta
    with patch(
        "app.domains.jobs.router.authenticate_api_key",
        new=AsyncMock(return_value=api_key),
    ), patch(
        "app.domains.jobs.router.get_job", new=AsyncMock(return_value=job)
    ):
        resp = await client.get(
            f"/jobs/{uuid.uuid4()}", headers={"X-Bridge-Key": "brg_x"}
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_jobs_requires_admin(client: AsyncClient) -> None:
    resp = await client.get("/admin/jobs")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_jobs_admin(client: AsyncClient) -> None:
    with patch(
        "app.domains.jobs.router.list_jobs", new=AsyncMock(return_value=([], 0))
    ):
        resp = await client.get("/admin/jobs", headers=admin_headers())
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_admin_get_job(client: AsyncClient) -> None:
    job = MagicMock()
    with patch(
        "app.domains.jobs.router.get_job", new=AsyncMock(return_value=job)
    ), patch(
        "app.domains.jobs.router.to_response",
        new=MagicMock(return_value=make_job_response(status="running")),
    ):
        resp = await client.get(f"/admin/jobs/{uuid.uuid4()}", headers=admin_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


@pytest.mark.asyncio
async def test_admin_get_job_404(client: AsyncClient) -> None:
    from app.domains.jobs.service import JobNotFoundError

    with patch(
        "app.domains.jobs.router.get_job",
        new=AsyncMock(side_effect=JobNotFoundError("nope")),
    ):
        resp = await client.get(f"/admin/jobs/{uuid.uuid4()}", headers=admin_headers())
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stream_job_requires_key(client: AsyncClient) -> None:
    # sem ?key= o endpoint nem chega a abrir o stream
    resp = await client.get(f"/jobs/{uuid.uuid4()}/stream")
    assert resp.status_code == 422  # query param obrigatório


@pytest.mark.asyncio
async def test_stream_job_rejects_other_account(client: AsyncClient) -> None:
    api_key = MagicMock(account_id=uuid.uuid4())
    job = MagicMock(account_id=uuid.uuid4())  # outra conta
    with patch(
        "app.domains.jobs.router.authenticate_api_key",
        new=AsyncMock(return_value=api_key),
    ), patch(
        "app.domains.jobs.router.get_job", new=AsyncMock(return_value=job)
    ):
        resp = await client.get(f"/jobs/{uuid.uuid4()}/stream?key=brg_x")
    assert resp.status_code == 404
