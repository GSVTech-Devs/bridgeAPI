from __future__ import annotations

import asyncio

import pytest

from bridge_sdk import context
from bridge_sdk.config import SDKConfig
from bridge_sdk.events import REQUEST_RECEIVED, LogLevel
from bridge_sdk.logging import BridgeLogger


class FakeTransport:
    def __init__(self, *, fail: bool = False) -> None:
        self.batches: list[list[dict]] = []
        self.fail = fail
        self.closed = False

    async def send_batch(self, entries):
        if self.fail:
            raise RuntimeError("platform down")
        self.batches.append(entries)
        return len(entries)

    async def aclose(self):
        self.closed = True


def make_config(**overrides) -> SDKConfig:
    base = dict(
        platform_url="http://platform.test",
        service_token="brgsvc_x_y",
        api_version="1.2.3",
        local_echo=False,
        flush_interval=0.01,
        max_retries=0,
        retry_base_delay=0,
    )
    base.update(overrides)
    return SDKConfig(**base)


def setup_function() -> None:
    context.set_correlation_id(None)


def test_log_builds_entry_with_context_and_versions() -> None:
    context.set_correlation_id("cid-123")
    logger = BridgeLogger(make_config(), transport=FakeTransport())
    entry = logger.info(REQUEST_RECEIVED, "hello", extra_field="v")

    assert entry["correlation_id"] == "cid-123"
    assert entry["level"] == "INFO"
    assert entry["event"] == REQUEST_RECEIVED
    assert entry["api_version"] == "1.2.3"
    assert entry["sdk_version"]
    assert entry["extra"] == {"extra_field": "v"}


def test_log_without_context_is_uncorrelated() -> None:
    logger = BridgeLogger(make_config(), transport=FakeTransport())
    entry = logger.error("proxy.failed", error_code="PROXY_AUTH_FAILED")
    assert entry["correlation_id"] == "uncorrelated"
    assert entry["error_code"] == "PROXY_AUTH_FAILED"


def test_level_helpers_set_correct_level() -> None:
    logger = BridgeLogger(make_config(), transport=FakeTransport())
    assert logger.warning("e")["level"] == LogLevel.WARNING.value
    assert logger.critical("e")["level"] == LogLevel.CRITICAL.value


@pytest.mark.asyncio
async def test_buffered_logs_are_flushed_to_transport() -> None:
    context.set_correlation_id("cid-flush")
    transport = FakeTransport()
    logger = BridgeLogger(make_config(), transport=transport)

    logger.info(REQUEST_RECEIVED, "a")
    logger.info("request.completed", "b")
    logger.start()
    await asyncio.sleep(0.05)
    await logger.aclose()

    sent = [e for batch in transport.batches for e in batch]
    assert len(sent) == 2
    assert sent[0]["correlation_id"] == "cid-flush"
    assert transport.closed is True


@pytest.mark.asyncio
async def test_disabled_does_not_buffer() -> None:
    transport = FakeTransport()
    logger = BridgeLogger(make_config(enabled=False), transport=transport)
    logger.info("e", "m")
    logger.start()
    await asyncio.sleep(0.03)
    await logger.aclose()
    assert transport.batches == []


@pytest.mark.asyncio
async def test_transport_failure_falls_back_without_raising(capsys) -> None:
    transport = FakeTransport(fail=True)
    logger = BridgeLogger(make_config(), transport=transport)
    logger.info("e", "m")
    logger.start()
    await asyncio.sleep(0.05)
    await logger.aclose()  # não deve levantar

    err = capsys.readouterr().err
    assert "bridge-sdk:fallback" in err


@pytest.mark.asyncio
async def test_aclose_drains_remaining_buffer() -> None:
    transport = FakeTransport()
    # flush_interval alto: nada é enviado pela task; só o drain no aclose envia
    logger = BridgeLogger(make_config(flush_interval=999), transport=transport)
    logger.info("e", "m")
    logger.start()
    await logger.aclose()

    sent = [e for batch in transport.batches for e in batch]
    assert len(sent) == 1
