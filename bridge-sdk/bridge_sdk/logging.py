"""Logger estruturado com envio assíncrono e resiliente para a Bridge.

Cada chamada a ``log()`` monta uma entrada JSON com correlation_id (herdado do
contexto), timestamp, versões e campos do evento, e a coloca num buffer. Uma
task de fundo drena o buffer periodicamente e envia em lote para a plataforma,
com retry/backoff. Se a plataforma estiver fora, NÃO trava a request nem perde
o log — degrada para fallback local (stderr).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

from . import context
from .config import SDKConfig
from .events import LogLevel
from .transport import LogTransport
from .version import __version__

_UNCORRELATED = "uncorrelated"


class BridgeLogger:
    def __init__(self, config: SDKConfig, transport: Optional[LogTransport] = None) -> None:
        self._config = config
        self._transport = transport if transport is not None else LogTransport(config)
        self._buffer: deque[dict[str, Any]] = deque(maxlen=config.buffer_max)
        self._task: Optional[asyncio.Task] = None
        self._closing = False

    # ------------------------------------------------------------------ API
    def log(
        self,
        level: LogLevel | str,
        event: str,
        message: str = "",
        *,
        error_code: Optional[str] = None,
        duration_ms: Optional[float] = None,
        proxy_id: Optional[str] = None,
        captcha_provider: Optional[str] = None,
        **extra: Any,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.value if isinstance(level, LogLevel) else str(level),
            "correlation_id": context.get_correlation_id() or _UNCORRELATED,
            "event": event,
            "message": message,
            "api_version": self._config.api_version,
            "sdk_version": __version__,
        }
        if duration_ms is not None:
            entry["duration_ms"] = duration_ms
        if proxy_id is not None:
            entry["proxy_id"] = proxy_id
        if captcha_provider is not None:
            entry["captcha_provider"] = captcha_provider
        if error_code is not None:
            entry["error_code"] = error_code
        if extra:
            entry["extra"] = extra

        if self._config.local_echo:
            print(json.dumps(entry, default=str), file=sys.stdout, flush=True)
        if self._config.enabled:
            self._buffer.append(entry)
        return entry

    def debug(self, event: str, message: str = "", **kw: Any) -> dict[str, Any]:
        return self.log(LogLevel.DEBUG, event, message, **kw)

    def info(self, event: str, message: str = "", **kw: Any) -> dict[str, Any]:
        return self.log(LogLevel.INFO, event, message, **kw)

    def warning(self, event: str, message: str = "", **kw: Any) -> dict[str, Any]:
        return self.log(LogLevel.WARNING, event, message, **kw)

    def error(self, event: str, message: str = "", **kw: Any) -> dict[str, Any]:
        return self.log(LogLevel.ERROR, event, message, **kw)

    def critical(self, event: str, message: str = "", **kw: Any) -> dict[str, Any]:
        return self.log(LogLevel.CRITICAL, event, message, **kw)

    # ----------------------------------------------------------- lifecycle
    def start(self) -> None:
        """Inicia a task de flush em background (precisa de um event loop ativo)."""
        if self._task is None:
            self._closing = False
            self._task = asyncio.create_task(self._run())

    async def aclose(self) -> None:
        """Encerra: para a task, drena o buffer e fecha o transporte."""
        self._closing = True
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        while self._buffer:
            await self._flush_once()
        await self._transport.aclose()

    # ------------------------------------------------------------ internals
    async def _run(self) -> None:
        with contextlib.suppress(asyncio.CancelledError):
            while not self._closing:
                await asyncio.sleep(self._config.flush_interval)
                await self._flush_once()

    async def _flush_once(self) -> None:
        if not self._buffer:
            return
        batch: list[dict[str, Any]] = []
        while self._buffer and len(batch) < self._config.batch_max:
            batch.append(self._buffer.popleft())
        if not batch:
            return
        try:
            await self._send_with_retry(batch)
        except Exception:
            self._fallback(batch)

    async def _send_with_retry(self, batch: list[dict[str, Any]]) -> None:
        delay = self._config.retry_base_delay
        for attempt in range(self._config.max_retries + 1):
            try:
                await self._transport.send_batch(batch)
                return
            except Exception:
                if attempt >= self._config.max_retries:
                    raise
                await asyncio.sleep(delay)
                delay *= 2

    def _fallback(self, batch: list[dict[str, Any]]) -> None:
        for entry in batch:
            print(
                "[bridge-sdk:fallback] " + json.dumps(entry, default=str),
                file=sys.stderr,
                flush=True,
            )
