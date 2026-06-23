# Testes unitários para app/domains/proxies/service.py.
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import encrypt_value
from app.domains.proxies.models import Proxy, ProxyPool, ProxyStatus
from app.domains.proxies.schemas import ProxyCreate, ProxyReportRequest
from app.domains.proxies.service import (
    ProxyNotFoundError,
    create_proxy,
    get_pool_config_for_api,
    report_proxy_failure,
    to_response,
)


def make_proxy(**kw) -> Proxy:
    defaults = dict(
        id=uuid.uuid4(), pool_id=uuid.uuid4(), name="p1", provider="brightdata",
        ownership="platform", type="residential", scheme="http",
        host="1.2.3.4", port=8080, rotation="sticky", session_ttl_s=600,
        status=ProxyStatus.ACTIVE.value, priority=10,
        username_encrypted=None, password_encrypted=None,
        last_error=None, last_error_at=None,
    )
    defaults.update(kw)
    p = Proxy()
    for k, v in defaults.items():
        setattr(p, k, v)
    import datetime
    p.created_at = datetime.datetime.now(datetime.timezone.utc)
    return p


# ---------------------------------------------------------------- to_response
def test_to_response_decrypts_username_and_flags_password() -> None:
    proxy = make_proxy(
        username_encrypted=encrypt_value("myuser"),
        password_encrypted=encrypt_value("mypass"),
    )
    resp = to_response(proxy)
    assert resp.username == "myuser"
    assert resp.has_password is True


def test_to_response_handles_missing_credentials() -> None:
    resp = to_response(make_proxy())
    assert resp.username is None
    assert resp.has_password is False


# ----------------------------------------------------------------- create
@pytest.mark.asyncio
async def test_create_proxy_encrypts_credentials() -> None:
    db = AsyncMock()
    db.add = MagicMock()
    data = ProxyCreate(name="p", host="h", port=1080, username="u", password="pw")

    await create_proxy(db, data)

    added = db.add.call_args[0][0]
    assert added.username_encrypted != "u"
    assert added.password_encrypted is not None
    from app.core.security import decrypt_value
    assert decrypt_value(added.username_encrypted) == "u"
    db.commit.assert_awaited()


# --------------------------------------------------- get_pool_config_for_api
@pytest.mark.asyncio
async def test_pool_config_empty_when_api_has_no_pool() -> None:
    api = MagicMock(proxy_pool_id=None)
    cfg = await get_pool_config_for_api(AsyncMock(), api)
    assert cfg.proxies == []
    assert cfg.pool_id is None


@pytest.mark.asyncio
async def test_pool_config_returns_decrypted_proxies() -> None:
    pool_id = uuid.uuid4()
    api = MagicMock(proxy_pool_id=pool_id)
    pool = ProxyPool(name="main")
    pool.id = pool_id

    p1 = make_proxy(pool_id=pool_id, priority=1, username_encrypted=encrypt_value("u1"),
                    password_encrypted=encrypt_value("pw1"))
    p2 = make_proxy(pool_id=pool_id, priority=2)

    pool_result = MagicMock()
    pool_result.scalar_one_or_none.return_value = pool
    proxies_result = MagicMock()
    proxies_result.scalars.return_value.all.return_value = [p1, p2]

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[pool_result, proxies_result])

    cfg = await get_pool_config_for_api(db, api)
    assert cfg.pool_name == "main"
    assert len(cfg.proxies) == 2
    assert cfg.proxies[0].username == "u1"
    assert cfg.proxies[0].password == "pw1"
    assert cfg.proxies[1].username is None


# ----------------------------------------------------- report_proxy_failure
@pytest.mark.asyncio
async def test_report_marks_proxy_failing() -> None:
    pool_id = uuid.uuid4()
    api = MagicMock(proxy_pool_id=pool_id)
    proxy = make_proxy(pool_id=pool_id)

    result = MagicMock()
    result.scalar_one_or_none.return_value = proxy
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    data = ProxyReportRequest(proxy_id=proxy.id, status=ProxyStatus.FAILING, message="login refused")
    updated = await report_proxy_failure(db, api, data)

    assert updated.status == ProxyStatus.FAILING.value
    assert updated.last_error == "login refused"
    assert updated.last_error_at is not None


@pytest.mark.asyncio
async def test_report_rejects_proxy_from_another_pool() -> None:
    api = MagicMock(proxy_pool_id=uuid.uuid4())
    proxy = make_proxy(pool_id=uuid.uuid4())  # pool diferente

    result = MagicMock()
    result.scalar_one_or_none.return_value = proxy
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    data = ProxyReportRequest(proxy_id=proxy.id)
    with pytest.raises(ProxyNotFoundError):
        await report_proxy_failure(db, api, data)
