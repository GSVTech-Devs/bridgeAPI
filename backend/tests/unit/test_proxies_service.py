# Testes unitários para app/domains/proxies/service.py.
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.security import encrypt_value
from app.domains.proxies.models import Proxy, ProxyPool, ProxyStatus
from app.domains.proxies.schemas import ProxyCreate, ProxyReportRequest
from app.domains.proxies.service import (
    ProxyNotFoundError,
    ProxyPoolNotFoundError,
    create_proxy,
    get_pool_config_for_api,
    report_proxy_failure,
    resolve_pool_id_for_client,
    set_client_override,
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


# ------------------------------------------- resolução híbrida (override cliente)
@pytest.mark.asyncio
async def test_resolve_no_client_uses_api_default() -> None:
    api = MagicMock(proxy_pool_id=uuid.uuid4())
    db = AsyncMock()
    out = await resolve_pool_id_for_client(db, api, client_id=None)
    assert out == api.proxy_pool_id
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_uses_client_override_when_present() -> None:
    api = MagicMock(id=uuid.uuid4(), proxy_pool_id=uuid.uuid4())
    override_pool = uuid.uuid4()
    result = MagicMock()
    result.scalar_one_or_none.return_value = override_pool
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    out = await resolve_pool_id_for_client(db, api, client_id=uuid.uuid4())
    assert out == override_pool


@pytest.mark.asyncio
async def test_resolve_falls_back_when_no_override() -> None:
    api = MagicMock(id=uuid.uuid4(), proxy_pool_id=uuid.uuid4())
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    out = await resolve_pool_id_for_client(db, api, client_id=uuid.uuid4())
    assert out == api.proxy_pool_id


@pytest.mark.asyncio
async def test_pool_config_uses_client_override() -> None:
    client_pool = uuid.uuid4()
    api = MagicMock(id=uuid.uuid4(), proxy_pool_id=uuid.uuid4())
    pool = ProxyPool(name="client-pool")
    pool.id = client_pool

    override_result = MagicMock()
    override_result.scalar_one_or_none.return_value = client_pool
    pool_result = MagicMock()
    pool_result.scalar_one_or_none.return_value = pool
    proxies_result = MagicMock()
    proxies_result.scalars.return_value.all.return_value = [
        make_proxy(pool_id=client_pool, priority=1)
    ]

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[override_result, pool_result, proxies_result])

    cfg = await get_pool_config_for_api(db, api, client_id=uuid.uuid4())
    assert cfg.pool_id == client_pool
    assert cfg.pool_name == "client-pool"
    assert len(cfg.proxies) == 1


@pytest.mark.asyncio
async def test_report_honors_client_override_pool() -> None:
    client_pool = uuid.uuid4()
    api = MagicMock(id=uuid.uuid4(), proxy_pool_id=uuid.uuid4())
    proxy = make_proxy(pool_id=client_pool)  # pertence ao pool do cliente

    override_result = MagicMock()
    override_result.scalar_one_or_none.return_value = client_pool
    proxy_result = MagicMock()
    proxy_result.scalar_one_or_none.return_value = proxy
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[override_result, proxy_result])

    data = ProxyReportRequest(proxy_id=proxy.id, message="dead")
    updated = await report_proxy_failure(db, api, data, client_id=uuid.uuid4())
    assert updated.status == ProxyStatus.FAILING.value


# ------------------------------------------------- set_client_override (cliente)
@pytest.mark.asyncio
async def test_set_client_override_creates_row() -> None:
    aid = uuid.uuid4()
    api = MagicMock(id=uuid.uuid4())
    pool = ProxyPool(name="mine")
    pool.id = uuid.uuid4()
    pool.account_id = aid

    lookup = MagicMock()
    lookup.scalar_one_or_none.return_value = None  # ainda não existe override
    pool_res = MagicMock()
    pool_res.scalar_one_or_none.return_value = pool
    db = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock(side_effect=[lookup, pool_res])

    with patch(
        "app.domains.proxies.service.get_api_by_id",
        new=AsyncMock(return_value=api),
    ):
        out = await set_client_override(db, str(api.id), aid, str(pool.id))

    assert out == pool.id
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_set_client_override_rejects_foreign_pool() -> None:
    aid = uuid.uuid4()
    api = MagicMock(id=uuid.uuid4())
    pool = ProxyPool(name="someone-elses")
    pool.id = uuid.uuid4()
    pool.account_id = uuid.uuid4()  # pertence a outra conta

    lookup = MagicMock()
    lookup.scalar_one_or_none.return_value = None
    pool_res = MagicMock()
    pool_res.scalar_one_or_none.return_value = pool
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[lookup, pool_res])

    with patch(
        "app.domains.proxies.service.get_api_by_id",
        new=AsyncMock(return_value=api),
    ):
        with pytest.raises(ProxyPoolNotFoundError):
            await set_client_override(db, str(api.id), aid, str(pool.id))


@pytest.mark.asyncio
async def test_set_client_override_clears_existing() -> None:
    aid = uuid.uuid4()
    api = MagicMock(id=uuid.uuid4())
    row = MagicMock()
    lookup = MagicMock()
    lookup.scalar_one_or_none.return_value = row
    db = AsyncMock()
    db.execute = AsyncMock(return_value=lookup)

    with patch(
        "app.domains.proxies.service.get_api_by_id",
        new=AsyncMock(return_value=api),
    ):
        out = await set_client_override(db, str(api.id), aid, None)

    assert out is None
    db.delete.assert_awaited_with(row)
