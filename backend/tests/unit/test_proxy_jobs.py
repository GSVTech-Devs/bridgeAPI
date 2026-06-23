# Execução híbrida no _dispatch: 202+job ao exceder o limite síncrono, e
# idempotência (repetir com a mesma Idempotency-Key não reprocessa).
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_idempotency_returns_existing_job(client: AsyncClient) -> None:
    aid = uuid.uuid4()
    account = MagicMock(id=uuid.uuid4())
    api = MagicMock(id=aid)
    key = MagicMock(id=uuid.uuid4())
    job = MagicMock(status="done", correlation_id="cid",
                    result_body='{"ok":1}', result_status_code=200)
    job.id = uuid.uuid4()

    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(return_value=(key, account, api)),
    ), patch(
        "app.domains.proxy.router.get_job_by_idempotency",
        new=AsyncMock(return_value=job),
    ), patch(
        "app.domains.proxy.router.forward_to_upstream", new=AsyncMock()
    ) as fwd:
        resp = await client.post(
            f"/proxy/{aid}/q",
            headers={"X-Bridge-Key": "brg_x", "Idempotency-Key": "k1"},
            content=b"{}",
        )
    assert resp.status_code == 200
    assert resp.text == '{"ok":1}'
    fwd.assert_not_called()  # idempotência curto-circuita o forward


@pytest.mark.asyncio
async def test_exceeding_sync_timeout_returns_202_job(client: AsyncClient) -> None:
    aid = uuid.uuid4()
    account = MagicMock(id=uuid.uuid4())
    api = MagicMock(id=aid, cost_per_query=0.05)
    key = MagicMock(id=uuid.uuid4())
    job = MagicMock()
    job.id = uuid.uuid4()

    async def slow_forward(*args, **kwargs):
        await asyncio.sleep(0.2)
        return MagicMock(status_code=200, headers={}, content=b"", text="")

    with patch.object(settings, "sync_timeout_s", 0.02), patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(return_value=(key, account, api)),
    ), patch(
        "app.domains.proxy.router.get_job_by_idempotency",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.domains.proxy.router.build_upstream_headers",
        new=MagicMock(return_value={}),
    ), patch(
        "app.domains.proxy.router.forward_to_upstream", new=slow_forward
    ), patch(
        "app.domains.proxy.router.create_job", new=AsyncMock(return_value=job)
    ), patch(
        "app.domains.proxy.router.finalize_job", new=AsyncMock()
    ) as finalize:
        resp = await client.post(
            f"/proxy/{aid}/q", headers={"X-Bridge-Key": "brg_x"}, content=b"{}"
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["job_id"] == str(job.id)
        assert body["status_url"].endswith(str(job.id))
        assert resp.headers["x-correlation-id"]
        # deixa o forward concluir → dispara o finalize em background
        await asyncio.sleep(0.3)

    finalize.assert_awaited()  # o job é finalizado quando o forward termina


@pytest.mark.asyncio
async def test_invalid_callback_url_rejected(client: AsyncClient) -> None:
    aid = uuid.uuid4()
    account = MagicMock(id=uuid.uuid4())
    api = MagicMock(id=aid, cost_per_query=0.05)
    key = MagicMock(id=uuid.uuid4())

    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(return_value=(key, account, api)),
    ), patch(
        "app.domains.proxy.router.get_job_by_idempotency",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.domains.proxy.router.forward_to_upstream", new=AsyncMock()
    ) as fwd:
        resp = await client.post(
            f"/proxy/{aid}/q",
            headers={"X-Bridge-Key": "brg_x", "X-Bridge-Callback": "ftp://nope"},
            content=b"{}",
        )
    assert resp.status_code == 400
    fwd.assert_not_called()  # nem chega a despachar


@pytest.mark.asyncio
async def test_callback_url_passed_to_job(client: AsyncClient) -> None:
    aid = uuid.uuid4()
    account = MagicMock(id=uuid.uuid4())
    api = MagicMock(id=aid, cost_per_query=0.05)
    key = MagicMock(id=uuid.uuid4())
    job = MagicMock()
    job.id = uuid.uuid4()

    async def slow_forward(*args, **kwargs):
        await asyncio.sleep(0.2)
        return MagicMock(status_code=200, headers={}, content=b"", text="")

    with patch.object(settings, "sync_timeout_s", 0.02), patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(return_value=(key, account, api)),
    ), patch(
        "app.domains.proxy.router.get_job_by_idempotency",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.domains.proxy.router.build_upstream_headers",
        new=MagicMock(return_value={}),
    ), patch(
        "app.domains.proxy.router.forward_to_upstream", new=slow_forward
    ), patch(
        "app.domains.proxy.router.create_job", new=AsyncMock(return_value=job)
    ) as create, patch(
        "app.domains.proxy.router.finalize_job", new=AsyncMock()
    ):
        resp = await client.post(
            f"/proxy/{aid}/q",
            headers={"X-Bridge-Key": "brg_x", "X-Bridge-Callback": "https://hook.example/cb"},
            content=b"{}",
        )
        assert resp.status_code == 202
        await asyncio.sleep(0.3)

    assert create.call_args.kwargs["callback_url"] == "https://hook.example/cb"
