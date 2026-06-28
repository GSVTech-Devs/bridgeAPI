"""Suporte sync: BackgroundLoop + fachadas sync de proxy/captcha + SyncBridge.

Os testes são SÍNCRONOS (def, não async): exercitam a SDK como um app Flask faria,
sem event loop no thread do teste. O loop de fundo roda em thread separada.
"""
from __future__ import annotations

import pytest

from bridge_sdk import context, errors
from bridge_sdk.captcha import CaptchaClient
from bridge_sdk.config import SDKConfig
from bridge_sdk.proxy import ProxyClient
from bridge_sdk.runtime import (
    BackgroundLoop,
    SyncBridge,
    SyncCaptchaClient,
    SyncProxyClient,
)


def setup_function() -> None:
    context.set_client(None)
    context.set_correlation_id(None)


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class FakeHttp:
    def __init__(self, items, key="proxies"):
        self._items = items
        self._key = key
        self.reports: list[dict] = []
        self.get_calls = 0
        self.last_get_headers: dict | None = None

    async def get(self, url, headers=None):
        self.get_calls += 1
        self.last_get_headers = headers
        return FakeResponse({self._key: self._items})

    async def post(self, url, headers=None, json=None):
        self.reports.append(json)
        return FakeResponse({"ok": True})

    async def aclose(self):
        pass


def make_config(**kw) -> SDKConfig:
    base = dict(platform_url="http://platform.test", service_token="brgsvc_x")
    base.update(kw)
    return SDKConfig(**base)


def proxy_dict(pid, priority):
    return dict(
        id=pid, name=f"p{pid}", scheme="http", host=f"{pid}.ex", port=8080,
        username="u", password="pw", rotation="sticky", session_ttl_s=600,
        priority=priority,
    )


def provider_dict(pid, priority, balance=10.0):
    return dict(
        id=pid, name=f"c{pid}", provider="capmonster", api_key="k",
        balance_usd=balance, priority=priority,
    )


@pytest.fixture
def loop():
    bl = BackgroundLoop()
    bl.start()
    yield bl
    bl.close()


# --------------------------------------------------------------- BackgroundLoop
def test_run_executes_coro_in_background(loop) -> None:
    async def add():
        return 1 + 2

    assert loop.run(add()) == 3


def test_run_carries_correlation_id_across_threads(loop) -> None:
    context.set_correlation_id("cid-123")

    async def grab():
        return context.get_correlation_id()

    assert loop.run(grab()) == "cid-123"


def test_run_carries_client_across_threads(loop) -> None:
    context.set_client("acc-9")
    http = FakeHttp([proxy_dict("a", 1)])
    sp = SyncProxyClient(ProxyClient(make_config(), client=http), loop)
    sp.get_proxies()
    # o header X-Bridge-Client só aparece se o contextvar cruzou para o loop
    assert http.last_get_headers["X-Bridge-Client"] == "acc-9"


# ----------------------------------------------------------- SyncProxyClient
def test_sync_proxy_acquire_returns_first(loop) -> None:
    http = FakeHttp([proxy_dict("a", 1), proxy_dict("b", 2)])
    sp = SyncProxyClient(ProxyClient(make_config(), client=http), loop)
    assert sp.acquire().id == "a"


def test_sync_proxy_failover_with_sync_fn(loop) -> None:
    http = FakeHttp([proxy_dict("a", 1), proxy_dict("b", 2)])
    sp = SyncProxyClient(ProxyClient(make_config(), client=http), loop)
    used: list[str] = []

    def fn(proxy):  # fn SÍNCRONO — roda no thread do teste, pode bloquear
        used.append(proxy.id)
        if proxy.id == "a":
            raise RuntimeError("proxy a morreu")
        return "ok"

    assert sp.with_failover(fn) == "ok"
    assert used == ["a", "b"]
    assert http.reports[0]["proxy_id"] == "a"


def test_sync_proxy_failover_all_fail_raises(loop) -> None:
    http = FakeHttp([proxy_dict("a", 1), proxy_dict("b", 2)])
    sp = SyncProxyClient(ProxyClient(make_config(), client=http), loop)

    def fn(proxy):
        raise RuntimeError("morto")

    with pytest.raises(errors.ProxyUnavailable):
        sp.with_failover(fn)


def test_sync_proxy_no_proxies_raises(loop) -> None:
    http = FakeHttp([])
    sp = SyncProxyClient(ProxyClient(make_config(), client=http), loop)
    with pytest.raises(errors.ProxyUnavailable):
        sp.with_failover(lambda p: "ok")


# ----------------------------------------------------------- SyncCaptchaClient
def test_sync_captcha_acquire_returns_first_with_balance(loop) -> None:
    http = FakeHttp([provider_dict("a", 1)], key="providers")
    sc = SyncCaptchaClient(CaptchaClient(make_config(), client=http), loop)
    assert sc.acquire().id == "a"


def test_sync_captcha_skips_no_balance(loop) -> None:
    http = FakeHttp(
        [provider_dict("a", 1, balance=0.0), provider_dict("b", 2, balance=5.0)],
        key="providers",
    )
    sc = SyncCaptchaClient(CaptchaClient(make_config(), client=http), loop)
    used: list[str] = []

    def fn(p):
        used.append(p.id)
        return "tok"

    assert sc.with_failover(fn) == "tok"
    assert used == ["b"]  # 'a' pulado por falta de saldo


def test_sync_captcha_no_balance_raises(loop) -> None:
    http = FakeHttp([provider_dict("a", 1, balance=0.0)], key="providers")
    sc = SyncCaptchaClient(CaptchaClient(make_config(), client=http), loop)
    with pytest.raises(errors.CaptchaBalanceExhausted):
        sc.with_failover(lambda p: "tok")


# ----------------------------------------------------------------- SyncBridge
def test_sync_bridge_start_status_log_close() -> None:
    cfg = make_config(enabled=False, local_echo=False, status_enabled=False)
    bridge = SyncBridge(cfg, checks={"alvo": lambda: {"status": "healthy", "latency_ms": 10}})
    bridge.start()
    try:
        report = bridge.status_report()
        assert report["status"] == "healthy"
        assert report["checks"]["alvo"]["status"] == "healthy"
        # log sync, não deve levantar
        bridge.logger.info("request.received", "oi")
    finally:
        bridge.close()


def test_sync_bridge_status_worst_of_checks() -> None:
    cfg = make_config(enabled=False, local_echo=False, status_enabled=False)
    bridge = SyncBridge(cfg, checks={
        "ok": lambda: {"status": "healthy"},
        "ruim": lambda: {"status": "degraded", "balance_usd": 1.0},
    })
    bridge.start()
    try:
        assert bridge.status_report()["status"] == "degraded"
    finally:
        bridge.close()
