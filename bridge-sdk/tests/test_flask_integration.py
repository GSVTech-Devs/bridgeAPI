"""Integração Flask (sync). Pula se Flask não estiver instalado (ex.: imagem do
backend, que é FastAPI). Roda onde o extra [flask] estiver presente.
"""
from __future__ import annotations

import pytest

from bridge_sdk import context
from bridge_sdk.config import SDKConfig

flask = pytest.importorskip("flask")


def make_config(**kw) -> SDKConfig:
    base = dict(
        platform_url="http://platform.test", service_token="brgsvc_x",
        enabled=False, local_echo=False, status_enabled=False,
    )
    base.update(kw)
    return SDKConfig(**base)


def test_install_exposes_health_and_status() -> None:
    from flask import Flask

    from bridge_sdk.integrations.flask import install

    app = Flask(__name__)
    bridge = install(app, make_config(), checks={"alvo": lambda: {"status": "healthy"}})
    try:
        client = app.test_client()

        r = client.get("/health")
        assert r.status_code == 200 and r.get_json()["status"] == "ok"

        r = client.get("/status")
        body = r.get_json()
        assert body["status"] == "healthy"
        assert body["checks"]["alvo"]["status"] == "healthy"

        assert app.extensions["bridge"] is bridge
    finally:
        bridge.close()


def test_correlation_id_echoed_in_response() -> None:
    from flask import Flask

    from bridge_sdk.integrations.flask import install

    app = Flask(__name__)
    bridge = install(app, make_config())
    try:
        client = app.test_client()
        r = client.get("/health", headers={"X-Correlation-Id": "abc-123"})
        assert r.headers.get(context.CORRELATION_HEADER) == "abc-123"
    finally:
        bridge.close()
