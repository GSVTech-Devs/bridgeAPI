from __future__ import annotations

import pytest

from bridge_sdk import context, errors
from bridge_sdk.captcha import CaptchaClient, CaptchaProvider
from bridge_sdk.config import SDKConfig


def setup_function() -> None:
    context.set_client(None)


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class FakeHttp:
    def __init__(self, providers):
        self._providers = providers
        self.reports: list[dict] = []
        self.get_calls = 0
        self.fail_get = False
        self.last_get_headers: dict | None = None

    async def get(self, url, headers=None):
        self.get_calls += 1
        self.last_get_headers = headers
        if self.fail_get:
            raise RuntimeError("network down")
        return FakeResponse({"providers": self._providers})

    async def post(self, url, headers=None, json=None):
        self.reports.append(json)
        return FakeResponse({"ok": True})

    async def aclose(self):
        pass


def prov(pid, priority, **kw):
    base = dict(
        id=pid, name=f"c{pid}", provider="2captcha", api_key="k",
        balance_usd=10.0, priority=priority,
    )
    base.update(kw)
    return base


def make_config(**kw) -> SDKConfig:
    base = dict(platform_url="http://platform.test", service_token="brgsvc_x")
    base.update(kw)
    return SDKConfig(**base)


def client_with(providers):
    http = FakeHttp(providers)
    return CaptchaClient(make_config(), client=http), http


# --------------------------------------------------------------- has_balance
def test_has_balance_none_is_available() -> None:
    assert CaptchaProvider(id="1", name="x", balance_usd=None).has_balance is True


def test_has_balance_zero_is_exhausted() -> None:
    assert CaptchaProvider(id="1", name="x", balance_usd=0).has_balance is False


# ------------------------------------------------------------------ get/cache
@pytest.mark.asyncio
async def test_get_providers_parses_and_caches() -> None:
    client, http = client_with([prov("a", 1), prov("b", 2)])
    first = await client.get_providers()
    assert [p.id for p in first] == ["a", "b"]
    await client.get_providers()
    assert http.get_calls == 1


@pytest.mark.asyncio
async def test_network_error_without_cache_raises() -> None:
    client, http = client_with([])
    http.fail_get = True
    with pytest.raises(errors.CaptchaFailed):
        await client.get_providers()


# --------------------------------------------------------------------- acquire
@pytest.mark.asyncio
async def test_acquire_returns_first_with_balance() -> None:
    client, _ = client_with([prov("a", 1), prov("b", 2)])
    assert (await client.acquire()).id == "a"


@pytest.mark.asyncio
async def test_acquire_skips_zero_balance() -> None:
    client, _ = client_with([prov("a", 1, balance_usd=0), prov("b", 2)])
    assert (await client.acquire()).id == "b"


@pytest.mark.asyncio
async def test_acquire_skips_failed() -> None:
    client, _ = client_with([prov("a", 1), prov("b", 2)])
    first = await client.acquire()
    await client.report_failure(first, error_code="CAPTCHA_FAILED")
    assert (await client.acquire()).id == "b"


@pytest.mark.asyncio
async def test_report_failure_posts_balance_to_platform() -> None:
    client, http = client_with([prov("a", 1)])
    p = await client.acquire()
    await client.report_failure(p, error_code="CAPTCHA_FAILED", balance_usd=3.5)
    assert http.reports[0]["provider_id"] == "a"
    assert http.reports[0]["balance_usd"] == 3.5


# -------------------------------------------------------------------- failover
@pytest.mark.asyncio
async def test_failover_skips_failing_provider() -> None:
    client, http = client_with([prov("a", 1), prov("b", 2)])
    used = []

    async def fn(p):
        used.append(p.id)
        if p.id == "a":
            raise RuntimeError("a is dead")
        return "ok"

    assert await client.with_failover(fn) == "ok"
    assert used == ["a", "b"]
    assert http.reports[0]["provider_id"] == "a"


@pytest.mark.asyncio
async def test_failover_raises_when_none_have_balance() -> None:
    client, _ = client_with([prov("a", 1, balance_usd=0)])

    async def fn(p):
        return "ok"

    with pytest.raises(errors.CaptchaBalanceExhausted):
        await client.with_failover(fn)


# ----------------------------------------------------------- client (híbrido)
@pytest.mark.asyncio
async def test_sends_client_header_and_caches_per_client() -> None:
    client, http = client_with([prov("a", 1)])
    context.set_client("acc-7")
    await client.get_providers()
    assert http.last_get_headers["X-Bridge-Client"] == "acc-7"
    await client.get_providers()
    assert http.get_calls == 1  # mesmo cliente → cache
    context.set_client("acc-9")
    await client.get_providers()
    assert http.get_calls == 2  # outro cliente → refetch
