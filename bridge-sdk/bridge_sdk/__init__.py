"""bridge-sdk — contrato compartilhado das APIs downstream da Bridge.

Fase 1: correlation_id (context), logging estruturado e taxonomia de erros.
Fases futuras: clientes de proxy e captcha, e rotas de /status (readiness).
"""

from __future__ import annotations

from . import errors, events
from .config import SDKConfig
from .health import DEGRADED, DOWN, HEALTHY, StatusRegistry
from .context import (
    CORRELATION_HEADER,
    correlation_id_from_headers,
    get_correlation_id,
    new_correlation_id,
    set_correlation_id,
    use_correlation_id,
)
from .errors import BridgeError
from .events import LogLevel
from .logging import BridgeLogger
from .proxy import ProxyClient, ProxyEndpoint
from .version import __version__

__all__ = [
    "__version__",
    "SDKConfig",
    "BridgeLogger",
    "StatusRegistry",
    "ProxyClient",
    "ProxyEndpoint",
    "HEALTHY",
    "DEGRADED",
    "DOWN",
    "LogLevel",
    "BridgeError",
    "errors",
    "events",
    "CORRELATION_HEADER",
    "get_correlation_id",
    "set_correlation_id",
    "new_correlation_id",
    "use_correlation_id",
    "correlation_id_from_headers",
]
