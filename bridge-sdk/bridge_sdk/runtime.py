"""Suporte a consumidores SÍNCRONOS (Flask, workers sync).

O núcleo da SDK é async. Em vez de duplicar a lógica, esta camada roda **um**
event loop num thread de fundo e oferece fachadas sync que empacotam os métodos
async:

- as tarefas de fundo (flusher de log, heartbeat de status) rodam nesse loop;
- proxy/captcha: a I/O **da própria SDK** (buscar config, reportar falha) é
  marshalada para o loop de fundo, mas o **seu** trabalho (``fn(proxy)``) roda no
  thread do chamador e pode bloquear à vontade.

Assim o ``httpx.AsyncClient`` interno fica preso a UM loop (sem o bug de
"event loop is closed" que apareceria com ``asyncio.run()`` por request) e o seu
código sync não precisa lidar com event loop nenhum.

> Caminho comum: na maioria das APIs há **um** proxy/captcha configurado (no
> máximo dois), então ``acquire()`` é o que você usa. ``with_failover`` existe
> para o caso de haver mais de um, mas não é o foco.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Awaitable, Callable, Optional, TypeVar

from . import context, errors
from .captcha import CaptchaClient, CaptchaProvider
from .config import SDKConfig
from .health import CheckFn, StatusRegistry
from .logging import BridgeLogger
from .proxy import ProxyClient, ProxyEndpoint
from .status_reporter import StatusReporter

T = TypeVar("T")


class BackgroundLoop:
    """Um event loop asyncio rodando num thread daemon dedicado."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            raise RuntimeError("BackgroundLoop não iniciado (chame start()).")
        return self._loop

    def start(self) -> None:
        if self._loop is not None:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._serve, name="bridge-sdk-loop", daemon=True
        )
        self._thread.start()

    def _serve(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()  # type: ignore[union-attr]

    def run(self, coro: Awaitable[T]) -> T:
        """Roda um coroutine no loop de fundo e BLOQUEIA pelo resultado.

        Carrega o ``correlation_id`` e o ``client`` do thread chamador para dentro
        do loop (contextvars não cruzam threads sozinhos), para que logs e headers
        emitidos pela SDK lá fiquem corretamente correlacionados."""
        cid = context.get_correlation_id()
        client = context.get_client()

        async def _wrapped() -> T:
            token_id = context.set_correlation_id(cid)
            token_client = context.set_client(client)
            try:
                return await coro
            finally:
                context.reset_client(token_client)
                context.reset_correlation_id(token_id)

        return asyncio.run_coroutine_threadsafe(_wrapped(), self.loop).result()

    def close(self) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._loop.close()
        self._loop = None
        self._thread = None


class SyncProxyClient:
    """Fachada sync do ``ProxyClient``.

    A I/O da SDK (buscar pool, reportar falha) roda no loop de fundo; o seu
    ``fn(proxy)`` roda no thread do chamador (pode bloquear)."""

    def __init__(self, client: ProxyClient, loop: BackgroundLoop) -> None:
        self._client = client
        self._loop = loop

    def get_proxies(self, *, force: bool = False) -> list[ProxyEndpoint]:
        return self._loop.run(self._client.get_proxies(force=force))

    def acquire(self) -> Optional[ProxyEndpoint]:
        """Proxy de maior prioridade disponível (o caminho comum: 1 configurado)."""
        return self._loop.run(self._client.acquire())

    def report_failure(self, proxy: ProxyEndpoint, **kw) -> None:
        self._loop.run(self._client.report_failure(proxy, **kw))

    def with_failover(
        self,
        fn: Callable[[ProxyEndpoint], T],
        *,
        retry_on: tuple[type[BaseException], ...] = (Exception,),
        max_attempts: Optional[int] = None,
    ) -> T:
        """Tenta cada proxy elegível com um ``fn`` **síncrono** até um dar certo.

        Só importa quando há mais de um proxy; com um, equivale a usar ``acquire``."""
        proxies = self._loop.run(self._client.candidates())
        if not proxies:
            raise errors.ProxyUnavailable("nenhum proxy disponível no pool")
        if max_attempts is not None:
            proxies = proxies[:max_attempts]
        last_exc: Optional[BaseException] = None
        for proxy in proxies:
            try:
                return fn(proxy)
            except retry_on as exc:
                last_exc = exc
                code = getattr(exc, "error_code", None)
                self._loop.run(
                    self._client.report_failure(proxy, error_code=code, message=str(exc))
                )
        raise errors.ProxyUnavailable("todos os proxies do pool falharam") from last_exc


class SyncCaptchaClient:
    """Fachada sync do ``CaptchaClient`` (espelha ``SyncProxyClient``)."""

    def __init__(self, client: CaptchaClient, loop: BackgroundLoop) -> None:
        self._client = client
        self._loop = loop

    def get_providers(self, *, force: bool = False) -> list[CaptchaProvider]:
        return self._loop.run(self._client.get_providers(force=force))

    def acquire(self) -> Optional[CaptchaProvider]:
        """Provedor de maior prioridade com saldo (caminho comum: 1 configurado)."""
        return self._loop.run(self._client.acquire())

    def report_failure(self, provider: CaptchaProvider, **kw) -> None:
        self._loop.run(self._client.report_failure(provider, **kw))

    def with_failover(
        self,
        fn: Callable[[CaptchaProvider], T],
        *,
        retry_on: tuple[type[BaseException], ...] = (Exception,),
        max_attempts: Optional[int] = None,
    ) -> T:
        providers = self._loop.run(self._client.candidates())
        if not providers:
            raise errors.CaptchaBalanceExhausted("nenhum provedor de captcha disponível")
        if max_attempts is not None:
            providers = providers[:max_attempts]
        last_exc: Optional[BaseException] = None
        for provider in providers:
            try:
                return fn(provider)
            except retry_on as exc:
                last_exc = exc
                code = getattr(exc, "error_code", None)
                self._loop.run(
                    self._client.report_failure(provider, error_code=code, message=str(exc))
                )
        raise errors.CaptchaFailed("todos os provedores de captcha falharam") from last_exc


class SyncBridge:
    """Ponto de entrada para apps SÍNCRONOS.

    Cria e gerencia o loop de fundo, o logger, o heartbeat de status e as
    fachadas sync de proxy/captcha. Use diretamente (workers, scripts) ou via
    ``bridge_sdk.integrations.flask.install``.

        bridge = SyncBridge(config, checks={"alvo": check_alvo})
        bridge.start()
        proxy = bridge.proxy.acquire()
        bridge.logger.info(events.REQUEST_RECEIVED, "...")
        ...
        bridge.close()   # no shutdown
    """

    def __init__(
        self, config: SDKConfig, *, checks: Optional[dict[str, CheckFn]] = None
    ) -> None:
        self._config = config
        self._loop = BackgroundLoop()
        self.logger = BridgeLogger(config)
        self.status = StatusRegistry()
        for name, fn in (checks or {}).items():
            self.status.register(name, fn)
        self._reporter = (
            StatusReporter(config, self.status) if config.status_enabled else None
        )
        self._proxy_async = ProxyClient(config, logger=self.logger)
        self._captcha_async = CaptchaClient(config, logger=self.logger)
        self.proxy = SyncProxyClient(self._proxy_async, self._loop)
        self.captcha = SyncCaptchaClient(self._captcha_async, self._loop)
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._loop.start()
        self._loop.run(self._astart())
        self._started = True

    async def _astart(self) -> None:
        # rodam NO loop de fundo (create_task exige loop em execução)
        self.logger.start()
        if self._reporter is not None:
            self._reporter.start()

    def register_check(self, name: str, fn: CheckFn) -> None:
        self.status.register(name, fn)

    def status_report(self) -> dict:
        """Relatório de readiness agregado (para a rota ``GET /status``)."""
        return self._loop.run(self.status.aggregate())

    def close(self) -> None:
        """Drena logs, encerra heartbeat e fecha clientes/loop. Chame no shutdown."""
        if not self._started:
            return
        if self._reporter is not None:
            self._loop.run(self._reporter.aclose())
        self._loop.run(self.logger.aclose())
        self._loop.run(self._proxy_async.aclose())
        self._loop.run(self._captcha_async.aclose())
        self._loop.close()
        self._started = False
