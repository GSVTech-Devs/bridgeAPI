from __future__ import annotations

import pytest

from bridge_sdk import context, errors
from bridge_sdk.config import SDKConfig
from bridge_sdk.proxy import ProxyClient, ProxyEndpoint


def setup_function() -> None:
    # isola cada teste — limpa o client do contexto (default = cache key "")
    context.set_client(None)


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class FakeHttp:
    def __init__(self, proxies):
        self._proxies = proxies
        self.reports: list[dict] = []
        self.get_calls = 0
        self.fail_get = False
        self.last_get_headers: dict | None = None
        self.last_post_headers: dict | None = None

    async def get(self, url, headers=None):
        self.get_calls += 1
        self.last_get_headers = headers
        if self.fail_get:
            raise RuntimeError("network down")
        return FakeResponse({"pool_name": "main", "proxies": self._proxies})

    async def post(self, url, headers=None, json=None):
        self.last_post_headers = headers
        self.reports.append(json)
        return FakeResponse({"ok": True})

    async def aclose(self):
        pass


def proxy_dict(pid, priority, **kw):
    base = dict(
        id=pid, name=f"p{pid}", scheme="http", host=f"{pid}.example",
        port=8080, username="u", password="pw", rotation="sticky",
        session_ttl_s=600, priority=priority,
    )
    base.update(kw)
    return base


def make_config(**kw) -> SDKConfig:
    base = dict(platform_url="http://platform.test", service_token="brgsvc_x")
    base.update(kw)
    return SDKConfig(**base)


def client_with(proxies):
    http = FakeHttp(proxies)
    return ProxyClient(make_config(), client=http), http


# ----------------------------------------------------------- ProxyEndpoint.url
def test_url_with_credentials() -> None:
    p = ProxyEndpoint(id="1", name="x", scheme="http", host="h", port=8080,
                      username="user", password="pass")
    assert p.url == "http://user:pass@h:8080"


def test_url_without_credentials() -> None:
    p = ProxyEndpoint(id="1", name="x", scheme="socks5", host="h", port=1080)
    assert p.url == "socks5://h:8080".replace("8080", "1080")


def test_url_escapes_special_chars() -> None:
    p = ProxyEndpoint(id="1", name="x", scheme="http", host="h", port=80,
                      username="u@b", password="p:w/d")
    assert "u%40b" in p.url and "p%3Aw%2Fd" in p.url


# ------------------------------------------------------------------ get/cache
@pytest.mark.asyncio
async def test_get_proxies_parses_and_caches() -> None:
    client, http = client_with([proxy_dict("a", 1), proxy_dict("b", 2)])
    first = await client.get_proxies()
    assert [p.id for p in first] == ["a", "b"]
    await client.get_proxies()  # segunda chamada usa cache
    assert http.get_calls == 1


@pytest.mark.asyncio
async def test_get_proxies_force_refetches() -> None:
    client, http = client_with([proxy_dict("a", 1)])
    await client.get_proxies()
    await client.get_proxies(force=True)
    assert http.get_calls == 2


@pytest.mark.asyncio
async def test_network_error_without_cache_raises() -> None:
    client, http = client_with([])
    http.fail_get = True
    with pytest.raises(errors.ProxyUnavailable):
        await client.get_proxies()


@pytest.mark.asyncio
async def test_network_error_with_cache_returns_stale() -> None:
    client, http = client_with([proxy_dict("a", 1)])
    await client.get_proxies()
    http.fail_get = True
    result = await client.get_proxies(force=True)
    assert [p.id for p in result] == ["a"]


# --------------------------------------------------------------------- acquire
@pytest.mark.asyncio
async def test_acquire_returns_first_available() -> None:
    client, _ = client_with([proxy_dict("a", 1), proxy_dict("b", 2)])
    proxy = await client.acquire()
    assert proxy.id == "a"


@pytest.mark.asyncio
async def test_acquire_skips_failed() -> None:
    client, _ = client_with([proxy_dict("a", 1), proxy_dict("b", 2)])
    first = await client.acquire()
    await client.report_failure(first, error_code="PROXY_AUTH_FAILED")
    assert (await client.acquire()).id == "b"


@pytest.mark.asyncio
async def test_report_failure_posts_to_platform() -> None:
    client, http = client_with([proxy_dict("a", 1)])
    p = await client.acquire()
    await client.report_failure(p, error_code="PROXY_AUTH_FAILED", message="boom")
    assert http.reports[0]["proxy_id"] == "a"
    assert http.reports[0]["error_code"] == "PROXY_AUTH_FAILED"


# -------------------------------------------------------------------- failover
@pytest.mark.asyncio
async def test_failover_returns_first_success() -> None:
    client, _ = client_with([proxy_dict("a", 1), proxy_dict("b", 2)])
    used = []

    async def fn(proxy):
        used.append(proxy.id)
        return "ok"

    assert await client.with_failover(fn) == "ok"
    assert used == ["a"]


@pytest.mark.asyncio
async def test_failover_skips_failing_proxy() -> None:
    client, http = client_with([proxy_dict("a", 1), proxy_dict("b", 2)])
    used = []

    async def fn(proxy):
        used.append(proxy.id)
        if proxy.id == "a":
            raise RuntimeError("proxy a is dead")
        return "ok"

    assert await client.with_failover(fn) == "ok"
    assert used == ["a", "b"]
    assert http.reports[0]["proxy_id"] == "a"  # 'a' foi reportado


@pytest.mark.asyncio
async def test_failover_raises_when_all_fail() -> None:
    client, _ = client_with([proxy_dict("a", 1), proxy_dict("b", 2)])

    async def fn(proxy):
        raise RuntimeError("dead")

    with pytest.raises(errors.ProxyUnavailable):
        await client.with_failover(fn)


@pytest.mark.asyncio
async def test_failover_raises_when_no_proxies() -> None:
    client, _ = client_with([])

    async def fn(proxy):
        return "ok"

    with pytest.raises(errors.ProxyUnavailable):
        await client.with_failover(fn)


# --------------------------------------------------- client (resolução híbrida)
@pytest.mark.asyncio
async def test_sends_service_token_and_no_client_header_by_default() -> None:
    client, http = client_with([proxy_dict("a", 1)])
    await client.get_proxies()
    assert http.last_get_headers["X-Service-Token"] == "brgsvc_x"
    assert "X-Bridge-Client" not in http.last_get_headers


@pytest.mark.asyncio
async def test_sends_client_header_when_set() -> None:
    context.set_client("acc-7")
    client, http = client_with([proxy_dict("a", 1)])
    await client.get_proxies()
    assert http.last_get_headers["X-Bridge-Client"] == "acc-7"
    await client.report_failure(ProxyEndpoint(id="a", name="a", scheme="http", host="h", port=80))
    assert http.last_post_headers["X-Bridge-Client"] == "acc-7"


@pytest.mark.asyncio
async def test_cache_is_keyed_by_client() -> None:
    client, http = client_with([proxy_dict("a", 1)])
    context.set_client("c1")
    await client.get_proxies()
    await client.get_proxies()  # mesmo cliente → cache
    assert http.get_calls == 1
    context.set_client("c2")
    await client.get_proxies()  # outro cliente → refetch (pool pode diferir)
    assert http.get_calls == 2


@pytest.mark.asyncio
async def test_failed_set_is_per_client() -> None:
    client, _ = client_with([proxy_dict("a", 1), proxy_dict("b", 2)])
    context.set_client("c1")
    first = await client.acquire()
    await client.report_failure(first)
    assert (await client.acquire()).id == "b"  # 'a' falhou para c1
    context.set_client("c2")
    assert (await client.acquire()).id == "a"  # c2 não herda a falha de c1
