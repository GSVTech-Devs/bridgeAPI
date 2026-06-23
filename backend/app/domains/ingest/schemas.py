from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# Eventos de ciclo de vida padronizados (sugeridos pela bridge-sdk). O campo
# `event` aceita qualquer string, mas estes são os valores canônicos.
STANDARD_EVENTS: frozenset[str] = frozenset(
    {
        "request.received",
        "proxy.acquired",
        "proxy.failed",
        "captcha.requested",
        "captcha.solved",
        "captcha.failed",
        "upstream.called",
        "request.completed",
    }
)


class AppLogEntryIn(BaseModel):
    """Uma linha de log estruturado enviada por uma API downstream.

    O `api_id` NÃO vem no corpo — é derivado do service token autenticado,
    para que uma API não possa forjar logs em nome de outra.
    """

    timestamp: datetime
    level: LogLevel
    correlation_id: str
    event: str
    message: str = ""
    duration_ms: Optional[float] = None
    proxy_id: Optional[str] = None
    captcha_provider: Optional[str] = None
    error_code: Optional[str] = None
    api_version: Optional[str] = None
    sdk_version: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class IngestLogsRequest(BaseModel):
    entries: list[AppLogEntryIn] = Field(min_length=1, max_length=1000)


class IngestLogsResponse(BaseModel):
    accepted: int


class ServiceTokenResponse(BaseModel):
    api_id: str
    service_token: str  # revelado apenas no momento da geração
    prefix: str
