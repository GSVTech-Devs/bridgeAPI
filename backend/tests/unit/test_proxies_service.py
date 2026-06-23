# Testes unitários para app/domains/proxies/service.py (proxies por API).
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.security import encrypt_value
from app.domains.proxies.models import Proxy, ProxyStatus
from app.domains.proxies.schemas import ProxyCreate, ProxyReportRequest
from app.domains.proxies.service import (
    ProxyNotFoundError,
    create_proxy,
    get_proxy_config_for_api,
    report_proxy_failure,
    resolve_owner_for_request,
    to_response,
)


def make_proxy(**kw) -> Proxy:
    defaults = dict(
        id=uuid.uuid4(), api_id=uuid.uuid4(), account_id=None, name="p1",
        provider="brightdata", ownership="platform", type="residential",
        scheme="http", host="1.2.3.4", port=8080, rotation="sticky",
        session_ttl_s=600, status=ProxyStatus.ACTIVE.value, priority=10,
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
async def test_create_proxy_encrypts_credentials_and_sets_api() -> None:
    api_id = uuid.uuid4()
    db = AsyncMock()
    db.add = MagicMock()
    data = ProxyCreate(name="p", host="h", port=1080, username="u", password="pw")

    with patch(
        "app.domains.proxies.service.get_api_by_id", new=AsyncMock()
    ):
        await create_proxy(db, str(api_id), data, account_id=None)

    added = db.add.call_args[0][0]
    assert added.api_id == api_id
    assert added.account_id is None
    from app.core.security import decrypt_value
    assert decrypt_value(added.username_encrypted) == "u"
    db.commit.assert_awaited()


# -------------------------------------------------- resolve_owner_for_request
@pytest.mark.asyncio
async def test_resolve_owner_no_client_is_admin() -> None:
    api = MagicMock(id=uuid.uuid4())
    out = await resolve_owner_for_request(AsyncMock(), api, client_id=None)
    assert out is None


@pytest.mark.asyncio
async def test_resolve_owner_client_managed() -> None:
    api = MagicMock(id=uuid.uuid4())
    client_id = uuid.uuid4()
    perm = MagicMock(proxy_managed_by_client=True)
    with patch(
        "app.domains.proxies.service.get_permission",
        new=AsyncMock(return_value=perm),
    ):
        out = await resolve_owner_for_request(AsyncMock(), api, client_id=client_id)
    assert out == client_id


@pytest.mark.asyncio
async def test_resolve_owner_not_managed_falls_back_to_admin() -> None:
    api = MagicMock(id=uuid.uuid4())
    perm = MagicMock(proxy_managed_by_client=False)
    with patch(
        "app.domains.proxies.service.get_permission",
        new=AsyncMock(return_value=perm),
    ):
        out = await resolve_owner_for_request(AsyncMock(), api, client_id=uuid.uuid4())
    assert out is None


# --------------------------------------------------- get_proxy_config_for_api
@pytest.mark.asyncio
async def test_config_empty_when_api_does_not_use_proxy() -> None:
    api = MagicMock(uses_proxy=False)
    cfg = await get_proxy_config_for_api(AsyncMock(), api)
    assert cfg.proxies == []


@pytest.mark.asyncio
async def test_config_returns_admin_proxies_decrypted() -> None:
    api = MagicMock(id=uuid.uuid4(), uses_proxy=True)
    p1 = make_proxy(priority=1, username_encrypted=encrypt_value("u1"),
                    password_encrypted=encrypt_value("pw1"))
    p2 = make_proxy(priority=2)
    proxies_result = MagicMock()
    proxies_result.scalars.return_value.all.return_value = [p1, p2]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=proxies_result)

    cfg = await get_proxy_config_for_api(db, api, client_id=None)
    assert len(cfg.proxies) == 2
    assert cfg.proxies[0].username == "u1"
    assert cfg.proxies[0].password == "pw1"
    assert cfg.proxies[1].username is None


@pytest.mark.asyncio
async def test_config_uses_client_proxies_when_managed() -> None:
    api = MagicMock(id=uuid.uuid4(), uses_proxy=True)
    client_id = uuid.uuid4()
    perm = MagicMock(proxy_managed_by_client=True)
    p1 = make_proxy(account_id=client_id, priority=1)
    proxies_result = MagicMock()
    proxies_result.scalars.return_value.all.return_value = [p1]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=proxies_result)

    with patch(
        "app.domains.proxies.service.get_permission",
        new=AsyncMock(return_value=perm),
    ):
        cfg = await get_proxy_config_for_api(db, api, client_id=client_id)
    assert len(cfg.proxies) == 1


# ----------------------------------------------------- report_proxy_failure
@pytest.mark.asyncio
async def test_report_marks_proxy_failing() -> None:
    api_id = uuid.uuid4()
    api = MagicMock(id=api_id)
    proxy = make_proxy(api_id=api_id, account_id=None)
    result = MagicMock()
    result.scalar_one_or_none.return_value = proxy
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    data = ProxyReportRequest(proxy_id=proxy.id, message="login refused")
    updated = await report_proxy_failure(db, api, data, client_id=None)
    assert updated.status == ProxyStatus.FAILING.value
    assert updated.last_error == "login refused"
    assert updated.last_error_at is not None


@pytest.mark.asyncio
async def test_report_rejects_proxy_from_another_api() -> None:
    api = MagicMock(id=uuid.uuid4())
    proxy = make_proxy(api_id=uuid.uuid4(), account_id=None)  # outra API
    result = MagicMock()
    result.scalar_one_or_none.return_value = proxy
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    data = ProxyReportRequest(proxy_id=proxy.id)
    with pytest.raises(ProxyNotFoundError):
        await report_proxy_failure(db, api, data, client_id=None)
