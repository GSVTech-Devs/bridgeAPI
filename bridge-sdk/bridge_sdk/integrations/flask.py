"""Integração plug-and-play com apps Flask (síncronos).

``install(app, config)`` cria um :class:`SyncBridge` (loop de fundo + logger +
heartbeat + fachadas sync de proxy/captcha), liga o ``correlation_id`` por
request (lê/devolve ``X-Correlation-Id`` e lê ``X-Bridge-Client``) e expõe
``GET /health`` e ``GET /status``. Requer o extra: ``pip install "bridge-sdk[flask]"``.

    from flask import Flask
    from bridge_sdk import SDKConfig
    from bridge_sdk.integrations.flask import install

    app = Flask(__name__)
    config = SDKConfig.from_env(api_version="2.3.1")
    bridge = install(app, config, checks={"alvo": check_alvo})

    # use bridge.proxy / bridge.captcha / bridge.logger nas suas rotas.
    # no shutdown do processo: bridge.close()
"""

from __future__ import annotations

from typing import Optional

from flask import Flask, g, request

from .. import context
from ..config import SDKConfig
from ..health import CheckFn
from ..runtime import SyncBridge


def install(
    app: Flask,
    config: SDKConfig,
    *,
    add_health: bool = True,
    add_status: bool = True,
    checks: Optional[dict[str, CheckFn]] = None,
) -> SyncBridge:
    """Instala correlation_id + logging + status num app Flask. Retorna o ``SyncBridge``.

    O bridge fica acessível em ``app.extensions['bridge']``. Lembre de chamar
    ``bridge.close()`` no encerramento do processo para drenar os logs."""
    bridge = SyncBridge(config, checks=checks)
    bridge.start()
    if not hasattr(app, "extensions") or app.extensions is None:
        app.extensions = {}
    app.extensions["bridge"] = bridge

    @app.before_request
    def _bridge_before():  # type: ignore[unused-ignore]
        cid = context.correlation_id_from_headers(request.headers)
        g._bridge_cid = context.set_correlation_id(cid)
        g._bridge_client = context.set_client(context.client_from_headers(request.headers))
        g.bridge_correlation_id = cid

    @app.after_request
    def _bridge_after(response):  # type: ignore[unused-ignore]
        response.headers[context.CORRELATION_HEADER] = g.get("bridge_correlation_id", "")
        return response

    @app.teardown_request
    def _bridge_teardown(exc=None):  # type: ignore[unused-ignore]
        token_client = g.pop("_bridge_client", None)
        token_cid = g.pop("_bridge_cid", None)
        if token_client is not None:
            context.reset_client(token_client)
        if token_cid is not None:
            context.reset_correlation_id(token_cid)

    if add_health:
        @app.get("/health")
        def _bridge_health():  # type: ignore[unused-ignore]
            return {"status": "ok"}

    if add_status:
        @app.get("/status")
        def _bridge_status():  # type: ignore[unused-ignore]
            return bridge.status_report()

    return bridge
