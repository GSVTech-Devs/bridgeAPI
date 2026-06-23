"""Integração plug-and-play com apps FastAPI.

``install(app, config)`` faz tudo: registra o middleware que lê o
``X-Correlation-Id`` de cada request (e o devolve na resposta), liga/desliga o
logger e o heartbeat de status no ciclo de vida do app, e expõe ``/health``
(liveness) e ``/status`` (readiness). Requer o extra:
``pip install "bridge-sdk[fastapi]"``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .. import context
from ..config import SDKConfig
from ..health import CheckFn, StatusRegistry
from ..logging import BridgeLogger
from ..status_reporter import StatusReporter


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = context.correlation_id_from_headers(request.headers)
        token = context.set_correlation_id(cid)
        try:
            response = await call_next(request)
        finally:
            context.reset_correlation_id(token)
        response.headers[context.CORRELATION_HEADER] = cid
        return response


def install(
    app,
    config: SDKConfig,
    *,
    add_health: bool = True,
    add_status: bool = True,
    checks: Optional[dict[str, CheckFn]] = None,
) -> BridgeLogger:
    """Instala correlation_id + logging + status num app FastAPI.

    Retorna o logger. Também ficam acessíveis em ``app.state``:
    ``bridge_logger`` e ``bridge_status`` (o ``StatusRegistry`` — registre checks
    de readiness com ``app.state.bridge_status.register("proxy_pool", fn)`` ou
    passe-os via ``checks=``).
    """
    logger = BridgeLogger(config)
    registry = StatusRegistry()
    for name, fn in (checks or {}).items():
        registry.register(name, fn)

    app.add_middleware(CorrelationMiddleware)
    app.state.bridge_logger = logger
    app.state.bridge_status = registry

    reporter = (
        StatusReporter(config, registry) if config.status_enabled else None
    )

    # Envolve o lifespan existente do app (não usa on_event, que é deprecado):
    # inicia logger + heartbeat na subida e drena/fecha na descida.
    previous_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def _bridge_lifespan(app_):
        logger.start()
        if reporter is not None:
            reporter.start()
        try:
            async with previous_lifespan(app_):
                yield
        finally:
            if reporter is not None:
                await reporter.aclose()
            await logger.aclose()

    app.router.lifespan_context = _bridge_lifespan

    if add_health:
        @app.get("/health", tags=["health"])
        async def health() -> dict:
            return {"status": "ok"}

    if add_status:
        @app.get("/status", tags=["health"])
        async def status() -> dict:
            return await registry.aggregate()

    return logger
