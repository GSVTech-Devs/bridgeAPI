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

from . import context, errors, events
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
        # Cache e failed-set são por cliente: a resolução é híbrida (o pool de um
        # cliente difere do default), então não dá para compartilhar entre eles.
        self._cache: dict[str, list[ProxyEndpoint]] = {}
        self._cache_at: dict[str, float] = {}
        self._failed: dict[str, set[str]] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _key() -> str:
        """Chave de cache = cliente atual (ou "" quando não há)."""
        return context.get_client() or ""

    def _headers(self) -> dict[str, str]:
        headers = {"X-Service-Token": self._config.service_token}
        client = context.get_client()
        if client:
            headers["X-Bridge-Client"] = client
        return headers

    def _failed_set(self) -> set[str]:
        return self._failed.setdefault(self._key(), set())

    # ------------------------------------------------------------ config fetch
    async def get_proxies(self, *, force: bool = False) -> list[ProxyEndpoint]:
        key = self._key()
        cached = self._cache.get(key)
        fresh = (
            cached is not None
            and (time.monotonic() - self._cache_at.get(key, 0.0))
            < self._config.proxy_cache_ttl
        )
        if fresh and not force:
            return cached  # type: ignore[return-value]
        try:
            resp = await self._client.get(
                f"{self._config.platform_url.rstrip('/')}/ingest/proxies",
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            proxies = [ProxyEndpoint(**item) for item in data.get("proxies", [])]
        except Exception:
            if cached is not None:
                return cached  # degrada para cache antigo
            raise errors.ProxyUnavailable("não foi possível obter o pool de proxies")
        self._cache[key] = proxies
        self._cache_at[key] = time.monotonic()
        self._failed[key] = set()  # config nova → reavalia todos
        return proxies

    # --------------------------------------------------------------- seleção
    async def acquire(self) -> Optional[ProxyEndpoint]:
        """Retorna o proxy de maior prioridade ainda não marcado como falho."""
        failed = self._failed_set()
        for proxy in await self.get_proxies():
            if proxy.id not in failed:
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
        self._failed_set().add(proxy.id)
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
                headers=self._headers(),
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
        failed = self._failed_set()
        proxies = [p for p in await self.get_proxies() if p.id not in failed]
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
