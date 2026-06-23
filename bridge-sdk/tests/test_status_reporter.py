from __future__ import annotations

import asyncio

import pytest

from bridge_sdk.config import SDKConfig
from bridge_sdk.health import HEALTHY, StatusRegistry
from bridge_sdk.status_reporter import StatusReporter


class FakeTransport:
    def __init__(self, *, fail: bool = False) -> None:
        self.reports: list[dict] = []
        self.fail = fail
        self.closed = False

    async def send_status(self, report):
        if self.fail:
            raise RuntimeError("platform down")
        self.reports.append(report)

    async def aclose(self):
        self.closed = True


def make_config(**overrides) -> SDKConfig:
    base = dict(
        platform_url="http://platform.test",
        service_token="brgsvc_x_y",
        status_interval=0.01,
    )
    base.update(overrides)
    return SDKConfig(**base)


@pytest.mark.asyncio
async def test_reports_status_on_start() -> None:
    reg = StatusRegistry()
    reg.register("proxy_pool", lambda: {"status": HEALTHY})
    transport = FakeTransport()
    reporter = StatusReporter(make_config(status_interval=999), reg, transport=transport)

    reporter.start()
    await asyncio.sleep(0.02)  # tempo do tick inicial
    await reporter.aclose()

    assert len(transport.reports) >= 1
    assert transport.reports[0]["status"] == HEALTHY
    assert "proxy_pool" in transport.reports[0]["checks"]
    assert transport.closed is True


@pytest.mark.asyncio
async def test_reports_periodically() -> None:
    transport = FakeTransport()
    reporter = StatusReporter(make_config(), StatusRegistry(), transport=transport)
    reporter.start()
    await asyncio.sleep(0.05)
    await reporter.aclose()
    assert len(transport.reports) >= 2  # tick inicial + ao menos um do loop


@pytest.mark.asyncio
async def test_transport_failure_does_not_crash() -> None:
    transport = FakeTransport(fail=True)
    reporter = StatusReporter(make_config(), StatusRegistry(), transport=transport)
    reporter.start()
    await asyncio.sleep(0.03)
    await reporter.aclose()  # não deve levantar
    assert transport.reports == []
