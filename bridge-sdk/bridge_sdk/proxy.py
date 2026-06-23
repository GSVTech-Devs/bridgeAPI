"""Cliente de proxy: busca o pool da plataforma, seleciona por prioridade,
faz failover e reporta falhas.

A config vem de ``GET /ingest/proxies`` (autenticada pelo service token) com cache
curto — então trocar o proxy na plataforma reflete na próxima atualização do cache,
sem deploy. Falhas são reportadas via ``POST /ingest/proxies/report`` e logadas
como ``proxy.failed``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, TypeVar
from urllib.parse import quote

import httpx

from . import errors, events
from .config import SDKConfig

T = TypeVar("T")


@dataclass
class ProxyEndpoint:
    id: str
    name: str
    scheme: str
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    rotation: str = "sticky"
    session_ttl_s: Optional[int] = None
    priority: int = 100

    @property
    def url(self) -> str:
        """URL pronta para httpx/requests, ex.: ``http://user:pass@host:8080``."""
        auth = ""
        if self.username:
            auth = quote(self.username, safe="")
            if self.password:
                auth += ":" + quote(self.password, safe="")
            auth += "@"
        return f"{self.scheme}://{auth}{self.host}:{self.port}"


class ProxyClient:
    def __init__(
        self,
        config: SDKConfig,
        *,
        logger=None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._config = config
        self._logger = logger
        self._client = client if client is not None else httpx.AsyncClient(
            timeout=config.timeout
        )
        self._cache: Optional[list[ProxyEndpoint]] = None
        self._cache_at: float = 0.0
        self._failed: set[str] = set()

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------ config fetch
    async def get_proxies(self, *, force: bool = False) -> list[ProxyEndpoint]:
        fresh = (
            self._cache is not None
            and (time.monotonic() - self._cache_at) < self._config.proxy_cache_ttl
        )
        if fresh and not force:
            return self._cache  # type: ignore[return-value]
        try:
            resp = await self._client.get(
                f"{self._config.platform_url.rstrip('/')}/ingest/proxies",
                headers={"X-Service-Token": self._config.service_token},
            )
            resp.raise_for_status()
            data = resp.json()
            proxies = [ProxyEndpoint(**item) for item in data.get("proxies", [])]
        except Exception:
            if self._cache is not None:
                return self._cache  # degrada para cache antigo
            raise errors.ProxyUnavailable("não foi possível obter o pool de proxies")
        self._cache = proxies
        self._cache_at = time.monotonic()
        self._failed.clear()  # config nova → reavalia todos
        return proxies

    # --------------------------------------------------------------- seleção
    async def acquire(self) -> Optional[ProxyEndpoint]:
        """Retorna o proxy de maior prioridade ainda não marcado como falho."""
        for proxy in await self.get_proxies():
            if proxy.id not in self._failed:
                if self._logger is not None:
                    self._logger.info(events.PROXY_ACQUIRED, proxy_id=proxy.id)
                return proxy
        return None

    async def report_failure(
        self,
        proxy: ProxyEndpoint,
        *,
        error_code: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        """Marca o proxy como falho localmente, loga e avisa a plataforma."""
        self._failed.add(proxy.id)
        if self._logger is not None:
            self._logger.error(
                events.PROXY_FAILED,
                message or "proxy failed",
                proxy_id=proxy.id,
                error_code=error_code or errors.ProxyAuthFailed.error_code,
            )
        try:
            await self._client.post(
                f"{self._config.platform_url.rstrip('/')}/ingest/proxies/report",
                headers={"X-Service-Token": self._config.service_token},
                json={
                    "proxy_id": proxy.id,
                    "status": "failing",
                    "error_code": error_code,
                    "message": message,
                },
            )
        except Exception:
            pass  # report é best-effort

    # --------------------------------------------------------------- failover
    async def with_failover(
        self,
        fn: Callable[[ProxyEndpoint], Awaitable[T]],
        *,
        retry_on: tuple[type[BaseException], ...] = (Exception,),
        max_attempts: Optional[int] = None,
    ) -> T:
        """Executa ``fn(proxy)`` tentando cada proxy por prioridade até um dar
        certo. Em falha (exceção em ``retry_on``), reporta o proxy e tenta o
        próximo. Esgotados, levanta ``ProxyUnavailable``."""
        proxies = [p for p in await self.get_proxies() if p.id not in self._failed]
        if not proxies:
            raise errors.ProxyUnavailable("nenhum proxy disponível no pool")
        if max_attempts is not None:
            proxies = proxies[:max_attempts]

        last_exc: Optional[BaseException] = None
        for proxy in proxies:
            try:
                return await fn(proxy)
            except retry_on as exc:
                last_exc = exc
                code = getattr(exc, "error_code", None)
                await self.report_failure(proxy, error_code=code, message=str(exc))
        raise errors.ProxyUnavailable(
            "todos os proxies do pool falharam"
        ) from last_exc
