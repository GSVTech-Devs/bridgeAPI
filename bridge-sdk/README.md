# bridge-sdk

Biblioteca interna que **toda API downstream da Bridge importa**. Padroniza o
contrato entre suas APIs e a plataforma: `correlation_id` propagado ponta a ponta,
**logging estruturado** enviado para a plataforma, e uma **taxonomia de erros**
comum.

Refatorar uma API = **adotar esta SDK** e remover o logging/erros ad-hoc.

> **Escopo atual (v0.1):** `context` (correlation_id), `logging` (estruturado +
> envio resiliente), `errors` (taxonomia), `health` (`/health`, `/status` e
> heartbeat de readiness) e `proxy` (cliente de pool com failover).
> **Próxima fase:** cliente de **captcha** com checagem de saldo.

---

## Índice

- [Instalação](#instalação)
- [Conceito: o correlation_id](#conceito-o-correlation_id)
- [Quickstart (FastAPI)](#quickstart-fastapi)
- [Uso manual (workers / sem FastAPI)](#uso-manual-workers--sem-fastapi)
- [Configuração](#configuração)
- [Emitindo logs](#emitindo-logs)
- [Health & Status (readiness)](#health--status-readiness)
- [Proxies (failover)](#proxies-failover)
- [Erros padronizados](#erros-padronizados)
- [Como obter o service token](#como-obter-o-service-token)
- [O que é enviado (schema do log)](#o-que-é-enviado-schema-do-log)
- [Resiliência](#resiliência)
- [Visualizando os logs na plataforma](#visualizando-os-logs-na-plataforma)
- [Versionamento](#versionamento)
- [Desenvolvimento e testes](#desenvolvimento-e-testes)

---

## Instalação

```bash
# com a integração FastAPI (recomendado para as APIs)
pip install "bridge-sdk[fastapi]"

# só o núcleo (workers, scripts)
pip install bridge-sdk
```

Durante o desenvolvimento, instale a partir do diretório do repositório:

```bash
pip install -e "./bridge-sdk[fastapi]"
```

---

## Conceito: o correlation_id

A Bridge gera um `correlation_id` por requisição e o repassa à sua API no header
**`X-Correlation-Id`**. A SDK:

1. **lê** esse header em cada request (middleware) e o guarda num `contextvar`;
2. **injeta** automaticamente em todo log emitido durante aquela request;
3. devolve o header na resposta.

Resultado: um único ID liga o log do gateway, os logs da sua API, e (nas próximas
fases) os eventos de proxy e captcha. Na plataforma, `GET /logs/admin/trace/{id}`
mostra essa timeline unificada — é o painel de debug.

```
cliente → Bridge (gera cid) → SUA API (SDK lê X-Correlation-Id) → proxy/captcha
                 └──────────── tudo logado sob o mesmo cid ─────────────┘
```

---

## Quickstart (FastAPI)

```python
from fastapi import FastAPI
from bridge_sdk import SDKConfig, events
from bridge_sdk.integrations.fastapi import install

app = FastAPI()

# Lê BRIDGE_PLATFORM_URL e BRIDGE_SERVICE_TOKEN do ambiente.
config = SDKConfig.from_env(api_version="2.3.1")

# Registra: middleware de correlation_id + ciclo de vida do logger + /health.
logger = install(app, config)


@app.post("/consultar")
async def consultar(payload: dict):
    logger.info(events.REQUEST_RECEIVED, "consulta recebida", campos=list(payload))
    # ... sua lógica (proxy, captcha, scraping) ...
    logger.info(events.REQUEST_COMPLETED, "ok", duration_ms=812.4)
    return {"ok": True}
```

`install()` faz, nesta ordem:

- adiciona o `CorrelationMiddleware` (lê/define/devolve o `X-Correlation-Id`);
- envolve o *lifespan* do app para **iniciar** o flusher de logs e o heartbeat de
  status na subida e **drenar + fechar** na descida (não usa `on_event`, que é
  deprecado);
- expõe `app.state.bridge_logger` (o logger, também retornado) e
  `app.state.bridge_status` (o registry de checks de readiness);
- registra `GET /health` (liveness) e `GET /status` (readiness). Use
  `add_health=False` / `add_status=False` para desligar cada um.

---

## Uso manual (workers / sem FastAPI)

Fora de um request HTTP (ex.: consumidor de fila), você controla o ciclo de vida
e o correlation_id explicitamente:

```python
import asyncio
from bridge_sdk import SDKConfig, BridgeLogger, context, events

async def main():
    logger = BridgeLogger(SDKConfig.from_env(api_version="2.3.1"))
    logger.start()
    try:
        # recebeu um job com o cid vindo da Bridge
        with context.use_correlation_id(job["correlation_id"]):
            logger.info(events.PROXY_ACQUIRED, proxy_id="br-resi-07")
            # ... processa ...
    finally:
        await logger.aclose()   # drena o buffer e fecha

asyncio.run(main())
```

---

## Configuração

Via ambiente (`SDKConfig.from_env`):

| Variável                | Obrigatória | Descrição                                  |
|-------------------------|-------------|--------------------------------------------|
| `BRIDGE_PLATFORM_URL`   | sim         | Base da Bridge, ex.: `https://bridge.example.com` |
| `BRIDGE_SERVICE_TOKEN`  | sim         | Token de serviço da API (`brgsvc_...`)     |
| `BRIDGE_API_VERSION`    | não         | Versão da sua API (default `unknown`)      |

Ou direto no `SDKConfig(...)`. Campos e defaults:

| Campo              | Default  | Para quê                                            |
|--------------------|----------|-----------------------------------------------------|
| `platform_url`     | —        | base da plataforma                                  |
| `service_token`    | —        | autentica o envio (`X-Service-Token`)               |
| `api_version`      | `unknown`| carimbado em cada log                               |
| `enabled`          | `True`   | se `False`, não envia (útil em dev/testes)          |
| `local_echo`       | `True`   | também imprime cada log como JSON no stdout         |
| `flush_interval`   | `2.0`    | segundos entre flushes do buffer                    |
| `batch_max`        | `100`    | máx. de entries por requisição                      |
| `buffer_max`       | `10000`  | capacidade do buffer (descarta os mais antigos)     |
| `timeout`          | `5.0`    | timeout HTTP do envio                               |
| `max_retries`      | `3`      | tentativas extras antes do fallback local           |
| `retry_base_delay` | `0.5`    | backoff exponencial inicial                         |
| `status_enabled`   | `True`   | liga o heartbeat de readiness (POST /ingest/status) |
| `status_interval`  | `30.0`   | segundos entre relatórios de status                 |
| `proxy_cache_ttl`  | `60.0`   | segundos de cache da config do pool de proxies      |

---

## Emitindo logs

```python
logger.info(event, message="", **campos)
logger.debug(...) / logger.warning(...) / logger.error(...) / logger.critical(...)

# campos de primeira classe (viram colunas filtráveis na plataforma):
logger.error(
    events.PROXY_FAILED,
    "login do proxy recusado",
    error_code="PROXY_AUTH_FAILED",
    proxy_id="br-resi-07",
    duration_ms=1532.0,
)

# qualquer outro kwarg vai para `extra` (objeto livre):
logger.info(events.UPSTREAM_CALLED, alvo="serasa", tentativa=2)
```

**Níveis:** `DEBUG, INFO, WARNING, ERROR, CRITICAL` (`bridge_sdk.LogLevel`).

**Eventos canônicos** (`bridge_sdk.events`) — use-os para manter os logs buscáveis:

| Constante              | Valor                 |
|------------------------|-----------------------|
| `REQUEST_RECEIVED`     | `request.received`    |
| `PROXY_ACQUIRED`       | `proxy.acquired`      |
| `PROXY_FAILED`         | `proxy.failed`        |
| `CAPTCHA_REQUESTED`    | `captcha.requested`   |
| `CAPTCHA_SOLVED`       | `captcha.solved`      |
| `CAPTCHA_FAILED`       | `captcha.failed`      |
| `UPSTREAM_CALLED`      | `upstream.called`     |
| `REQUEST_COMPLETED`    | `request.completed`   |

O `event` aceita qualquer string, mas os valores acima são o vocabulário padrão.

> O `correlation_id` é preenchido **automaticamente** do contexto. Você nunca o
> passa manualmente nas APIs FastAPI. Fora de um request, use
> `context.use_correlation_id(...)`. Sem contexto, o log sai como `uncorrelated`.

---

## Health & Status (readiness)

Duas semânticas distintas:

- **`/health` (liveness)** — o processo está de pé? Resposta trivial e rápida,
  sem checar dependências. Para load balancer / k8s.
- **`/status` (readiness)** — *consigo realmente atender?* Roda os **checks** que
  você registrou (pool de proxy, saldo de captcha, alvo alcançável...) e devolve o
  pior status entre eles.

Registre checks via `checks=` no `install()` ou em `app.state.bridge_status`:

```python
async def check_proxies():
    free = pool.available()
    return {
        "status": "healthy" if free > 2 else "degraded",
        "available": free, "total": pool.size(),
    }

def check_captcha():
    bal = solver.balance_usd()
    return {"status": "degraded" if bal < 5 else "healthy",
            "balance_usd": bal, "provider": solver.name}

logger = install(app, config, checks={
    "proxy_pool": check_proxies,   # sync ou async, tanto faz
    "captcha": check_captcha,
})
# ou depois: app.state.bridge_status.register("target", check_target)
```

Cada check devolve um dict com `status` (`healthy` | `degraded` | `down`) + os
campos extras que quiser. Um check que **levanta exceção** vira `down`
automaticamente. `GET /status` responde:

```json
{
  "status": "degraded",
  "sdk_version": "0.1.0",
  "uptime_s": 38211,
  "checks": {
    "proxy_pool": {"status": "healthy", "available": 8, "total": 10},
    "captcha":    {"status": "degraded", "balance_usd": 2.10, "provider": "capsolver"}
  }
}
```

**Heartbeat:** com `status_enabled` (default), a SDK também **envia** esse
relatório para a plataforma a cada `status_interval` segundos
(`POST /ingest/status`) — assim o painel `/admin/status` mostra a saúde em tempo
real mesmo para APIs atrás de firewall (sem a plataforma precisar fazer polling).
É best-effort: se o envio falhar, não afeta a sua API.

---

## Proxies (failover)

O `ProxyClient` busca o **pool de proxies** que a plataforma atribuiu à sua API
(`GET /ingest/proxies`, com cache de `proxy_cache_ttl`), seleciona por prioridade,
faz **failover** e **reporta falhas** de volta (a plataforma marca o proxy como
`failing` e para de servi-lo). Trocar o proxy na Ui reflete na próxima atualização
do cache — **sem deploy**.

```python
from bridge_sdk import ProxyClient

proxy_client = ProxyClient(config, logger=logger)  # logger é opcional

# Forma recomendada — failover automático:
async def fetch(proxy):
    async with httpx.AsyncClient(proxy=proxy.url) as http:
        r = await http.get(alvo)
        if r.status_code == 407:
            raise errors.ProxyAuthFailed("login do proxy recusado")
        return r

resultado = await proxy_client.with_failover(fetch)
# tenta cada proxy por prioridade; em exceção, reporta e tenta o próximo;
# se todos falharem, levanta errors.ProxyUnavailable.

await proxy_client.aclose()
```

Controle manual, se preferir:

```python
proxy = await proxy_client.acquire()          # maior prioridade disponível
if proxy is None:
    raise errors.ProxyUnavailable("pool vazio")
try:
    ... usar proxy.url ...
except ProxyLoginError as e:
    await proxy_client.report_failure(proxy, error_code="PROXY_AUTH_FAILED", message=str(e))
```

- `proxy.url` → `scheme://user:pass@host:port` (credenciais já URL-encoded).
- `report_failure` loga `proxy.failed` (com `proxy_id` + `error_code`) e avisa a
  plataforma — best-effort, nunca trava sua request.
- Se a config não puder ser obtida e não houver cache, levanta `ProxyUnavailable`;
  havendo cache, usa o cache antigo (degrada com elegância).

> **Status do proxy no painel:** as falhas reportadas aparecem em
> `/admin/proxies` (proxy vira `failing` com o último erro). Reative manualmente lá.

---

## Erros padronizados

Levante a subclasse de `BridgeError` apropriada; cada uma carrega um `error_code`
estável e um `http_status` sugerido. Logue o `error_code` no evento de falha para
que a plataforma consiga filtrar por causa raiz.

```python
from bridge_sdk import errors

try:
    proxy = pool.acquire()
except ProxyLoginError:
    logger.error(events.PROXY_FAILED, error_code=errors.ProxyAuthFailed.error_code,
                 proxy_id=proxy.id)
    raise errors.ProxyAuthFailed("login recusado pelo fornecedor X")
```

| Classe                     | `error_code`                | HTTP |
|----------------------------|-----------------------------|------|
| `ProxyAuthFailed`          | `PROXY_AUTH_FAILED`         | 502  |
| `ProxyUnavailable`         | `PROXY_UNAVAILABLE`         | 503  |
| `CaptchaFailed`            | `CAPTCHA_FAILED`            | 502  |
| `CaptchaBalanceExhausted`  | `CAPTCHA_BALANCE_EXHAUSTED` | 503  |
| `TargetBlocked`            | `TARGET_BLOCKED`            | 502  |
| `TargetTimeout`            | `TARGET_TIMEOUT`            | 504  |
| `InvalidQuery`             | `INVALID_QUERY`             | 400  |

`errors.ERRORS_BY_CODE["PROXY_AUTH_FAILED"]` resolve a classe a partir do code.

---

## Como obter o service token

O token de serviço autentica os logs da sua API (≠ chave de cliente). Um **admin
da plataforma** gera/rotaciona via:

```
POST /ingest/apis/{api_id}/token     (Authorization: Bearer <token admin>)
→ { "api_id": "...", "service_token": "brgsvc_ab12cd34_...", "prefix": "ab12cd34" }
```

O `service_token` é mostrado **uma única vez**. Guarde-o como segredo na API
(ex.: variável `BRIDGE_SERVICE_TOKEN`). Rotacionar = chamar o endpoint de novo
(invalida o anterior).

---

## O que é enviado (schema do log)

Cada entry enviada a `POST /ingest/logs` tem:

```json
{
  "timestamp": "2026-06-23T12:00:01.234+00:00",
  "level": "ERROR",
  "correlation_id": "0f8c...",
  "event": "proxy.failed",
  "message": "login do proxy recusado",
  "api_version": "2.3.1",
  "sdk_version": "0.1.0",
  "duration_ms": 1532.0,
  "proxy_id": "br-resi-07",
  "captcha_provider": null,
  "error_code": "PROXY_AUTH_FAILED",
  "extra": { "tentativa": 2 }
}
```

O `api_id` **não** vai no corpo — a plataforma o deriva do service token (uma API
não pode forjar logs em nome de outra). Valores que parecem segredo (prefixo
`brg_`) são mascarados no servidor antes de persistir.

---

## Resiliência

O envio é **assíncrono e não-bloqueante**:

- `log()` só monta a entry e a coloca num buffer (rápido, não faz I/O).
- Uma task de fundo drena o buffer a cada `flush_interval`, em lotes de até
  `batch_max`, com **retry exponencial** (`max_retries`).
- Se a plataforma estiver fora após os retries, cai para **fallback local**
  (a entry é impressa no `stderr` com prefixo `[bridge-sdk:fallback]`) — a
  request da sua API **nunca trava nem falha** por causa de logging.
- Se o buffer encher (`buffer_max`), os logs **mais antigos** são descartados
  (memória limitada).
- `aclose()` drena o que restou antes de fechar — chame no shutdown
  (`install()` já faz isso por você).

---

## Visualizando os logs na plataforma

Endpoints admin da Bridge:

- `GET /logs/admin/app` — logs estruturados das APIs, com filtros
  `correlation_id, api_id, level, event, error_code, since, until`.
- `GET /logs/admin/trace/{correlation_id}` — **timeline unificada** (logs do
  gateway + logs da sua API) ordenada no tempo. Comece o debug por aqui.

---

## Versionamento

Semver. A versão da SDK é enviada em cada log (`sdk_version`), então a plataforma
sabe quais APIs já estão no contrato novo. Importe de `bridge_sdk.__version__`.

---

## Desenvolvimento e testes

```bash
pip install -e "./bridge-sdk[fastapi,dev]"
cd bridge-sdk && pytest -q
```

A suíte cobre context, logging (buffer/flush/fallback), erros e a integração
FastAPI. Nenhuma conexão real é feita — o transporte é mockado.
