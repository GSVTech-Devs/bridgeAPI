# Testes unitários para app/domains/captcha/service.py (captcha por API).
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.security import encrypt_value
from app.domains.captcha.models import CaptchaProvider, CaptchaStatus
from app.domains.captcha.schemas import CaptchaCreate, CaptchaReportRequest
from app.domains.captcha.service import (
    CaptchaNotFoundError,
    create_captcha,
    get_captcha_config_for_api,
    report_captcha_failure,
    resolve_owner_for_request,
    to_response,
)


def make_captcha(**kw) -> CaptchaProvider:
    defaults = dict(
        id=uuid.uuid4(), api_id=uuid.uuid4(), account_id=None, name="2c",
        provider="2captcha", api_key_encrypted=None, balance_usd=10.0,
        priority=10, status=CaptchaStatus.ACTIVE.value,
        last_error=None, last_error_at=None,
    )
    defaults.update(kw)
    c = CaptchaProvider()
    for k, v in defaults.items():
        setattr(c, k, v)
    import datetime
    c.created_at = datetime.datetime.now(datetime.timezone.utc)
    return c


def test_to_response_flags_api_key_and_keeps_balance() -> None:
    c = make_captcha(api_key_encrypted=encrypt_value("secret"), balance_usd=4.2)
    resp = to_response(c)
    assert resp.has_api_key is True
    assert resp.balance_usd == 4.2


@pytest.mark.asyncio
async def test_create_captcha_encrypts_key_and_sets_api() -> None:
    api_id = uuid.uuid4()
    db = AsyncMock()
    db.add = MagicMock()
    data = CaptchaCreate(name="2c", provider="2captcha", api_key="abc", balance_usd=5)

    with patch("app.domains.captcha.service.get_api_by_id", new=AsyncMock()):
        await create_captcha(db, str(api_id), data, account_id=None)

    added = db.add.call_args[0][0]
    assert added.api_id == api_id
    from app.core.security import decrypt_value
    assert decrypt_value(added.api_key_encrypted) == "abc"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_resolve_owner_client_managed() -> None:
    api = MagicMock(id=uuid.uuid4())
    client_id = uuid.uuid4()
    perm = MagicMock(captcha_managed_by_client=True)
    with patch(
        "app.domains.captcha.service.get_permission",
        new=AsyncMock(return_value=perm),
    ):
        out = await resolve_owner_for_request(AsyncMock(), api, client_id=client_id)
    assert out == client_id


@pytest.mark.asyncio
async def test_config_empty_when_api_does_not_use_captcha() -> None:
    api = MagicMock(uses_captcha=False)
    cfg = await get_captcha_config_for_api(AsyncMock(), api)
    assert cfg.providers == []


@pytest.mark.asyncio
async def test_config_returns_admin_providers_with_key_and_balance() -> None:
    api = MagicMock(id=uuid.uuid4(), uses_captcha=True)
    c1 = make_captcha(priority=1, api_key_encrypted=encrypt_value("k1"), balance_usd=7.0)
    result = MagicMock()
    result.scalars.return_value.all.return_value = [c1]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    cfg = await get_captcha_config_for_api(db, api, client_id=None)
    assert len(cfg.providers) == 1
    assert cfg.providers[0].api_key == "k1"
    assert cfg.providers[0].balance_usd == 7.0


@pytest.mark.asyncio
async def test_report_marks_failing_and_updates_balance() -> None:
    api_id = uuid.uuid4()
    api = MagicMock(id=api_id)
    captcha = make_captcha(api_id=api_id, account_id=None)
    result = MagicMock()
    result.scalar_one_or_none.return_value = captcha
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    data = CaptchaReportRequest(provider_id=captcha.id, message="bad key", balance_usd=1.0)
    updated = await report_captcha_failure(db, api, data, client_id=None)
    assert updated.status == CaptchaStatus.FAILING.value
    assert updated.balance_usd == 1.0


@pytest.mark.asyncio
async def test_report_rejects_provider_from_another_api() -> None:
    api = MagicMock(id=uuid.uuid4())
    captcha = make_captcha(api_id=uuid.uuid4())  # outra API
    result = MagicMock()
    result.scalar_one_or_none.return_value = captcha
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    data = CaptchaReportRequest(provider_id=captcha.id)
    with pytest.raises(CaptchaNotFoundError):
        await report_captcha_failure(db, api, data, client_id=None)
