from __future__ import annotations

import uuid

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from bridge_sdk import context  # noqa: E402
from bridge_sdk.config import SDKConfig  # noqa: E402
from bridge_sdk.integrations.fastapi import install  # noqa: E402


def make_app() -> FastAPI:
    app = FastAPI()
    install(
        app,
        SDKConfig(
            platform_url="http://platform.test",
            service_token="brgsvc_x_y",
            enabled=False,
            local_echo=False,
            status_enabled=False,  # sem heartbeat de rede nos testes
        ),
    )

    @app.get("/echo")
    async def echo() -> dict:
        return {"seen": context.get_correlation_id()}

    return app


def test_middleware_propagates_incoming_correlation_id() -> None:
    cid = str(uuid.uuid4())
    with TestClient(make_app()) as client:
        resp = client.get("/echo", headers={"X-Correlation-Id": cid})
    assert resp.json()["seen"] == cid
    assert resp.headers["x-correlation-id"] == cid


def test_middleware_generates_when_absent() -> None:
    with TestClient(make_app()) as client:
        resp = client.get("/echo")
    generated = resp.json()["seen"]
    assert uuid.UUID(generated)
    assert resp.headers["x-correlation-id"] == generated


def test_health_route_installed() -> None:
    with TestClient(make_app()) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_logger_exposed_on_app_state() -> None:
    app = make_app()
    assert hasattr(app.state, "bridge_logger")
    assert hasattr(app.state, "bridge_status")


def test_status_route_aggregates_registered_checks() -> None:
    app = make_app()
    app.state.bridge_status.register("proxy_pool", lambda: {"status": "degraded", "available": 1})
    with TestClient(app) as client:
        resp = client.get("/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["proxy_pool"]["available"] == 1
    assert body["sdk_version"]


def test_status_route_healthy_when_no_checks() -> None:
    with TestClient(make_app()) as client:
        resp = client.get("/status")
    assert resp.json()["status"] == "healthy"
