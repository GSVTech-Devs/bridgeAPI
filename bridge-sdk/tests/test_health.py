from __future__ import annotations

import pytest

from bridge_sdk.health import DEGRADED, DOWN, HEALTHY, StatusRegistry


@pytest.mark.asyncio
async def test_empty_registry_is_healthy() -> None:
    report = await StatusRegistry().aggregate()
    assert report["status"] == HEALTHY
    assert report["checks"] == {}
    assert report["sdk_version"]
    assert report["uptime_s"] >= 0


@pytest.mark.asyncio
async def test_all_healthy_checks() -> None:
    reg = StatusRegistry()
    reg.register("proxy_pool", lambda: {"status": HEALTHY, "available": 8})
    reg.register("captcha", lambda: {"status": HEALTHY, "balance_usd": 50})
    report = await reg.aggregate()
    assert report["status"] == HEALTHY
    assert report["checks"]["proxy_pool"]["available"] == 8


@pytest.mark.asyncio
async def test_degraded_dominates_healthy() -> None:
    reg = StatusRegistry()
    reg.register("proxy_pool", lambda: {"status": HEALTHY})
    reg.register("captcha", lambda: {"status": DEGRADED, "balance_usd": 1.5})
    report = await reg.aggregate()
    assert report["status"] == DEGRADED


@pytest.mark.asyncio
async def test_down_dominates_everything() -> None:
    reg = StatusRegistry()
    reg.register("a", lambda: {"status": DEGRADED})
    reg.register("b", lambda: {"status": DOWN})
    assert (await reg.aggregate())["status"] == DOWN


@pytest.mark.asyncio
async def test_async_check_supported() -> None:
    reg = StatusRegistry()

    async def check():
        return {"status": HEALTHY, "latency_ms": 12}

    reg.register("target", check)
    report = await reg.aggregate()
    assert report["checks"]["target"]["latency_ms"] == 12


@pytest.mark.asyncio
async def test_raising_check_becomes_down() -> None:
    reg = StatusRegistry()

    def boom():
        raise RuntimeError("pool empty")

    reg.register("proxy_pool", boom)
    report = await reg.aggregate()
    assert report["status"] == DOWN
    assert "pool empty" in report["checks"]["proxy_pool"]["error"]


@pytest.mark.asyncio
async def test_non_dict_result_is_wrapped() -> None:
    reg = StatusRegistry()
    reg.register("weird", lambda: "healthy")
    report = await reg.aggregate()
    assert report["checks"]["weird"]["status"] == "healthy"
