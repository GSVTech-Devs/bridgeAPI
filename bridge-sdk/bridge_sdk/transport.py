"""Transporte HTTP dos logs para a Bridge (POST /ingest/logs)."""

from __future__ import annotations

from typing import Any

import httpx

from .config import SDKConfig


class LogTransport:
    """Envia lotes de logs para o endpoint de ingestão da plataforma."""

    def __init__(self, config: SDKConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(timeout=config.timeout)

    async def send_batch(self, entries: list[dict[str, Any]]) -> int:
        url = f"{self._config.platform_url.rstrip('/')}/ingest/logs"
        response = await self._client.post(
            url,
            json={"entries": entries},
            headers={"X-Service-Token": self._config.service_token},
        )
        response.raise_for_status()
        try:
            return int(response.json().get("accepted", len(entries)))
        except Exception:
            return len(entries)

    async def send_status(self, report: dict[str, Any]) -> None:
        url = f"{self._config.platform_url.rstrip('/')}/ingest/status"
        response = await self._client.post(
            url,
            json=report,
            headers={"X-Service-Token": self._config.service_token},
        )
        response.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
