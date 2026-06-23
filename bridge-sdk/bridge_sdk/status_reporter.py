"""Heartbeat de status: envia o readiness para a plataforma periodicamente.

Roda em background (como o logger). Nunca derruba a aplicação — se o envio
falhar, ignora e tenta de novo no próximo ciclo.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Optional

from .config import SDKConfig
from .health import StatusRegistry
from .transport import LogTransport


class StatusReporter:
    def __init__(
        self,
        config: SDKConfig,
        registry: StatusRegistry,
        transport: Optional[LogTransport] = None,
    ) -> None:
        self._config = config
        self._registry = registry
        self._transport = transport if transport is not None else LogTransport(config)
        self._task: Optional[asyncio.Task] = None
        self._closing = False

    def start(self) -> None:
        if self._task is None:
            self._closing = False
            self._task = asyncio.create_task(self._run())

    async def aclose(self) -> None:
        self._closing = True
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._transport.aclose()

    async def _run(self) -> None:
        with contextlib.suppress(asyncio.CancelledError):
            await self._tick()  # reporta logo na subida
            while not self._closing:
                await asyncio.sleep(self._config.status_interval)
                await self._tick()

    async def _tick(self) -> None:
        try:
            report = await self._registry.aggregate()
            await self._transport.send_status(report)
        except Exception:
            # status é best-effort; o coletor/heartbeat seguinte tenta de novo
            pass
