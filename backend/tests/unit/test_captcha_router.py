# HTTP do CRUD admin de captcha (/apis/{id}/captchas), ingest e monitoramento.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.domains.captcha.schemas import (
    CaptchaConfigItem,
    CaptchaConfigResponse,
    CaptchaMonitorItem,
    CaptchaResponse,
)


def admin_headers() -> dict:
    return {"Authorization": f"Bearer {create_access_token('admin@bridge.com', role='admin')}"}


def client_headers() -> dict:
    token = create_access_token(
        "acme@example.com", role="owner",
        extra_claims={"user_id": str(uuid.uuid4()), "account_id": str(uuid.uuid4())},
    )
    return {"Authorization": f"Bearer {token}"}


def make_captcha_response(**kw) -> CaptchaResponse:
    base = dict(
        id=uuid.uuid4(), api_id=uuid.uuid4(), account_id=None, name="2c",
        provider="2captcha", has_api_key=True, balance_usd=9.0, priority=10,
        status="active", created_at=datetime.now(timezone.utc),
    )
    base.update(kw)
    return CaptchaResponse(**base)


def fake_api():
    api = MagicMock()
    api.id = uuid.uuid4()
    return api


@pytest.mark.asyncio
async def test_list_requires_admin(client: AsyncClient) -> None:
    resp = await client.get(f"/apis/{uuid.uuid4()}/captchas", headers=client_headers())
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_masks_api_key(client: AsyncClient) -> None:
    with patch("app.domains.captcha.router.create_captcha", new=AsyncMock()), patch(
        "app.domains.captcha.router.to_response",
        new=MagicMock(return_value=make_captcha_response()),
    ):
        resp = await client.post(
            f"/apis/{uuid.uuid4()}/captchas",
            json={"name": "2c", "provider": "2captcha", "api_key": "secret"},
            headers=admin_headers(),
        )
    assert resp.status_code == 201
    body = resp.json()
    assert "api_key" not in body
    assert body["has_api_key"] is True


@pytest.mark.asyncio
async def test_monitor_captchas(client: AsyncClient) -> None:
    item = CaptchaMonitorItem(
        id=uuid.uuid4(), api_id=uuid.uuid4(), api_name="API X", account_id=None,
        name="2c", provider="2captcha", balance_usd=2.0, status="failing", priority=10,
        last_error="bad key", last_error_at=datetime.now(timezone.utc),
    )
    with patch(
        "app.domains.captcha.router.monitor_captchas",
        new=AsyncMock(return_value=[item]),
    ):
        resp = await client.get("/monitoring/captchas", headers=admin_headers())
    assert resp.status_code == 200
    assert resp.json()["items"][0]["balance_usd"] == 2.0


# ------------------------------------------------------------------ ingest
@pytest.mark.asyncio
async def test_ingest_captcha_returns_config(client: AsyncClient) -> None:
    cfg = CaptchaConfigResponse(
        providers=[
            CaptchaConfigItem(
                id=uuid.uuid4(), name="2c", provider="2captcha",
                api_key="secret", balance_usd=5.0, priority=1,
            )
        ]
    )
    with patch(
        "app.domains.ingest.router.authenticate_service_token",
        new=AsyncMock(return_value=fake_api()),
    ), patch(
        "app.domains.ingest.router.get_captcha_config_for_api", new=AsyncMock(return_value=cfg)
    ) as spy:
        resp = await client.get(
            "/ingest/captcha",
            headers={"X-Service-Token": "brgsvc_good", "X-Bridge-Client": "acc-1"},
        )
    assert resp.status_code == 200
    assert resp.json()["providers"][0]["api_key"] == "secret"
    assert spy.await_args.kwargs["client_id"] == "acc-1"


@pytest.mark.asyncio
async def test_ingest_captcha_report(client: AsyncClient) -> None:
    captcha = MagicMock()
    captcha.id = uuid.uuid4()
    captcha.status = "failing"
    with patch(
        "app.domains.ingest.router.authenticate_service_token",
        new=AsyncMock(return_value=fake_api()),
    ), patch(
        "app.domains.ingest.router.report_captcha_failure",
        new=AsyncMock(return_value=captcha),
    ):
        resp = await client.post(
            "/ingest/captcha/report",
            json={"provider_id": str(captcha.id), "status": "failing", "balance_usd": 0.0},
            headers={"X-Service-Token": "brgsvc_good"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "failing"
