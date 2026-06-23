"""Readiness (`/status`) — registro de checks de dependências e agregação.

Liveness (`/health`) só diz se o processo está de pé. Readiness (`/status`)
responde *consigo realmente atender?* — rodando checks das dependências (pool de
proxy, saldo de captcha, alvo alcançável...). Cada check devolve um dict com pelo
menos ``status`` (``healthy`` | ``degraded`` | ``down``); o status geral é o pior
entre todos.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Awaitable, Callable, Union

from .version import __version__

HEALTHY = "healthy"
DEGRADED = "degraded"
DOWN = "down"

_SEVERITY = {HEALTHY: 0, DEGRADED: 1, DOWN: 2}

# Um check devolve um dict (sync ou async). Ex.: {"status": "healthy", "available": 8}
CheckFn = Callable[[], Union[dict, Awaitable[dict]]]


def _worst(statuses: list[str]) -> str:
    if not statuses:
        return HEALTHY
    return max(statuses, key=lambda s: _SEVERITY.get(s, _SEVERITY[DOWN]))


async def _run_check(fn: CheckFn) -> dict[str, Any]:
    try:
        result = fn()
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, dict):
            result = {"status": str(result)}
        result.setdefault("status", HEALTHY)
        return result
    except Exception as exc:  # um check nunca derruba o /status
        return {"status": DOWN, "error": str(exc)}


class StatusRegistry:
    """Guarda os checks de readiness e os agrega num relatório de status."""

    def __init__(self) -> None:
        self._checks: dict[str, CheckFn] = {}
        self._started_at = time.monotonic()

    def register(self, name: str, fn: CheckFn) -> None:
        """Registra um check nomeado (ex.: ``"proxy_pool"``, ``"captcha"``)."""
        self._checks[name] = fn

    def unregister(self, name: str) -> None:
        self._checks.pop(name, None)

    async def aggregate(self) -> dict[str, Any]:
        names = list(self._checks)
        results = await asyncio.gather(*(_run_check(self._checks[n]) for n in names))
        checks = dict(zip(names, results))
        overall = _worst([c.get("status", DOWN) for c in results])
        return {
            "status": overall,
            "sdk_version": __version__,
            "uptime_s": int(time.monotonic() - self._started_at),
            "checks": checks,
        }
