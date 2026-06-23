# Endpoints consumidos pela SDK: GET /ingest/proxies e POST /ingest/proxies/report.
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.domains.proxies.schemas import ProxyConfigItem, ProxyConfigResponse


def fake_api():
    api = MagicMock()
    api.id = uuid.uuid4()
    return api


@pytest.mark.asyncio
async def test_ingest_proxies_requires_service_token(client: AsyncClient) -> None:
    resp = await client.get("/ingest/proxies")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ingest_proxies_returns_pool_config(client: AsyncClient) -> None:
    pool_id = uuid.uuid4()
    cfg = ProxyConfigResponse(
        pool_id=pool_id,
        pool_name="main",
        proxies=[
            ProxyConfigItem(
                id=uuid.uuid4(), name="p1", scheme="http", host="1.2.3.4",
                port=8080, username="u", password="pw", rotation="sticky",
                session_ttl_s=600, priority=1,
            )
        ],
    )
    with patch(
        "app.domains.ingest.router.authenticate_service_token",
        new=AsyncMock(return_value=fake_api()),
    ), patch(
        "app.domains.ingest.router.get_pool_config_for_api",
        new=AsyncMock(return_value=cfg),
    ):
        resp = await client.get(
            "/ingest/proxies", headers={"X-Service-Token": "brgsvc_good"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["pool_name"] == "main"
    assert body["proxies"][0]["password"] == "pw"  # SDK precisa das credenciais


@pytest.mark.asyncio
async def test_ingest_proxy_report(client: AsyncClient) -> None:
    proxy = MagicMock()
    proxy.id = uuid.uuid4()
    proxy.status = "failing"
    with patch(
        "app.domains.ingest.router.authenticate_service_token",
        new=AsyncMock(return_value=fake_api()),
    ), patch(
        "app.domains.ingest.router.report_proxy_failure",
        new=AsyncMock(return_value=proxy),
    ):
        resp = await client.post(
            "/ingest/proxies/report",
            json={"proxy_id": str(proxy.id), "status": "failing", "error_code": "PROXY_AUTH_FAILED"},
            headers={"X-Service-Token": "brgsvc_good"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "failing"
