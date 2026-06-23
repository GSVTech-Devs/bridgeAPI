# Autosserviço de captcha do cliente: /client/apis/{api_id}/captchas.
from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.domains.captcha import client_router
from app.domains.captcha.schemas import CaptchaResponse
from app.main import app


@pytest.fixture
def account_id():
    return uuid.uuid4()


@pytest.fixture
def as_client_user(account_id):
    async def _identity():
        return MagicMock(account_id=account_id)

    app.dependency_overrides[client_router._require] = _identity
    yield account_id
    app.dependency_overrides.pop(client_router._require, None)


def make_captcha_response(account_id, **kw) -> CaptchaResponse:
    base = dict(
        id=uuid.uuid4(), api_id=uuid.uuid4(), account_id=account_id, name="2c",
        provider="2captcha", has_api_key=False, balance_usd=None, priority=100,
        status="active", created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    base.update(kw)
    return CaptchaResponse(**base)


@pytest.mark.asyncio
async def test_requires_capability(client: AsyncClient) -> None:
    resp = await client.get(f"/client/apis/{uuid.uuid4()}/captchas")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_blocked_when_not_managed(client: AsyncClient, as_client_user) -> None:
    perm = MagicMock(captcha_managed_by_client=False)
    with patch(
        "app.domains.captcha.client_router.get_permission",
        new=AsyncMock(return_value=perm),
    ):
        resp = await client.get(f"/client/apis/{uuid.uuid4()}/captchas")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_client_create_when_managed(client: AsyncClient, as_client_user) -> None:
    perm = MagicMock(captcha_managed_by_client=True)
    with patch(
        "app.domains.captcha.client_router.get_permission",
        new=AsyncMock(return_value=perm),
    ), patch(
        "app.domains.captcha.client_router.create_captcha", new=AsyncMock()
    ) as create, patch(
        "app.domains.captcha.client_router.to_response",
        new=MagicMock(return_value=make_captcha_response(as_client_user)),
    ):
        resp = await client.post(
            f"/client/apis/{uuid.uuid4()}/captchas",
            json={"name": "2c", "provider": "2captcha", "api_key": "k"},
        )
    assert resp.status_code == 201
    assert create.await_args.kwargs["account_id"] == as_client_user
