"""Cliente de captcha: busca os provedores da plataforma para a API, seleciona
por prioridade (pulando os sem saldo), faz failover e reporta falhas/saldo.

Espelha o ``ProxyClient``: a config vem de ``GET /ingest/captcha`` (autenticada
pelo service token + ``X-Bridge-Client``) com cache curto e keyed por cliente.
Falhas vão para ``POST /ingest/captcha/report`` e são logadas como ``captcha.failed``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, TypeVar

import httpx

from . import context, errors, events
from .config import SDKConfig

T = TypeVar("T")


@dataclass
class CaptchaProvider:
    id: str
    name: str
    provider: Optional[str] = None
    api_key: Optional[str] = None
    balance_usd: Optional[float] = None
    priority: int = 100

    @property
    def has_balance(self) -> bool:
        """Saldo desconhecido (None) conta como disponível; <= 0 é esgotado."""
        return self.balance_usd is None or self.balance_usd > 0


class CaptchaClient:
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
        # Cache e failed-set por cliente (a resolução é híbrida, igual ao proxy).
        self._cache: dict[str, list[CaptchaProvider]] = {}
        self._cache_at: dict[str, float] = {}
        self._failed: dict[str, set[str]] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _key() -> str:
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
    async def get_providers(self, *, force: bool = False) -> list[CaptchaProvider]:
        key = self._key()
        cached = self._cache.get(key)
        fresh = (
            cached is not None
            and (time.monotonic() - self._cache_at.get(key, 0.0))
            < self._config.captcha_cache_ttl
        )
        if fresh and not force:
            return cached  # type: ignore[return-value]
        try:
            resp = await self._client.get(
                f"{self._config.platform_url.rstrip('/')}/ingest/captcha",
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            providers = [CaptchaProvider(**item) for item in data.get("providers", [])]
        except Exception:
            if cached is not None:
                return cached  # degrada para cache antigo
            raise errors.CaptchaFailed("não foi possível obter os provedores de captcha")
        self._cache[key] = providers
        self._cache_at[key] = time.monotonic()
        self._failed[key] = set()
        return providers

    # --------------------------------------------------------------- seleção
    async def acquire(self) -> Optional[CaptchaProvider]:
        """Provedor de maior prioridade ainda não-falho e com saldo."""
        failed = self._failed_set()
        for provider in await self.get_providers():
            if provider.id not in failed and provider.has_balance:
                if self._logger is not None:
                    self._logger.info(
                        events.CAPTCHA_REQUESTED, captcha_provider=provider.name
                    )
                return provider
        return None

    async def report_failure(
        self,
        provider: CaptchaProvider,
        *,
        error_code: Optional[str] = None,
        message: Optional[str] = None,
        balance_usd: Optional[float] = None,
    ) -> None:
        """Marca o provedor como falho localmente, loga e avisa a plataforma
        (opcionalmente atualizando o saldo restante)."""
        self._failed_set().add(provider.id)
        if self._logger is not None:
            self._logger.error(
                events.CAPTCHA_FAILED,
                message or "captcha failed",
                captcha_provider=provider.name,
                error_code=error_code or errors.CaptchaFailed.error_code,
            )
        try:
            await self._client.post(
                f"{self._config.platform_url.rstrip('/')}/ingest/captcha/report",
                headers=self._headers(),
                json={
                    "provider_id": provider.id,
                    "status": "failing",
                    "error_code": error_code,
                    "message": message,
                    "balance_usd": balance_usd,
                },
            )
        except Exception:
            pass  # report é best-effort

    # --------------------------------------------------------------- failover
    async def with_failover(
        self,
        fn: Callable[[CaptchaProvider], Awaitable[T]],
        *,
        retry_on: tuple[type[BaseException], ...] = (Exception,),
        max_attempts: Optional[int] = None,
    ) -> T:
        """Executa ``fn(provider)`` tentando cada provedor com saldo por prioridade
        até um dar certo. Esgotados, levanta ``CaptchaFailed``."""
        failed = self._failed_set()
        providers = [
            p for p in await self.get_providers()
            if p.id not in failed and p.has_balance
        ]
        if not providers:
            raise errors.CaptchaBalanceExhausted("nenhum provedor de captcha disponível")
        if max_attempts is not None:
            providers = providers[:max_attempts]

        last_exc: Optional[BaseException] = None
        for provider in providers:
            try:
                return await fn(provider)
            except retry_on as exc:
                last_exc = exc
                code = getattr(exc, "error_code", None)
                await self.report_failure(provider, error_code=code, message=str(exc))
        raise errors.CaptchaFailed("todos os provedores de captcha falharam") from last_exc
