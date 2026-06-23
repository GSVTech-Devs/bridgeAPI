"""Níveis e eventos de ciclo de vida padronizados.

O campo ``event`` aceita qualquer string, mas usar estes valores canônicos
mantém os logs buscáveis e consistentes entre todas as APIs.
"""

from __future__ import annotations

from enum import Enum


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# Eventos canônicos do ciclo de vida de uma consulta.
REQUEST_RECEIVED = "request.received"
PROXY_ACQUIRED = "proxy.acquired"
PROXY_FAILED = "proxy.failed"
CAPTCHA_REQUESTED = "captcha.requested"
CAPTCHA_SOLVED = "captcha.solved"
CAPTCHA_FAILED = "captcha.failed"
UPSTREAM_CALLED = "upstream.called"
REQUEST_COMPLETED = "request.completed"

STANDARD_EVENTS: frozenset[str] = frozenset(
    {
        REQUEST_RECEIVED,
        PROXY_ACQUIRED,
        PROXY_FAILED,
        CAPTCHA_REQUESTED,
        CAPTCHA_SOLVED,
        CAPTCHA_FAILED,
        UPSTREAM_CALLED,
        REQUEST_COMPLETED,
    }
)
