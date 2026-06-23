# Estado da Refatoração das APIs — Handoff

> Documento de continuidade. Use-o para abrir um **novo chat com contexto limpo** e
> seguir a refatoração de onde paramos. Resume o que foi feito (Fases 1–3),
> as decisões tomadas, como testar, e o plano da próxima fase (Fase 4).

## Documentos de referência
- **`REQUISITOS_REFATORACAO_APIS.md`** (raiz) — o documento de requisitos/roadmap completo.
- **`bridge-sdk/README.md`** — guia de uso da SDK (instalação, logging, health/status, proxy, erros).
- **Este arquivo** — estado atual + handoff.

---

## Visão geral

A Bridge é um gateway que centraliza o acesso dos clientes às APIs do dono (consultas
via POST, com proxy + captcha por trás). A refatoração padroniza o **contrato** entre
as APIs downstream e a plataforma, via uma **SDK compartilhada** (`bridge-sdk`) que toda
API importa, ancorado num **`correlation_id` único** que atravessa toda a cadeia.

### Decisões-chave (já tomadas)
1. **Execução híbrida** (Fase 5, futura): síncrono até ~90s, depois job assíncrono.
2. **Contrato dos dois lados**: o doc cobre o que a API expõe E o que a Bridge ganha.
3. **SDK compartilhada** (`bridge-sdk`, pacote Python instalável) — refatorar = adotar a SDK.
4. **Heartbeat push** (não polling) para status — firewall-friendly.
5. **Proxy: modelo simples** — um proxy pertence a UM pool; uma API aponta para um pool.
6. **Fase 4 (próxima): config de proxy/captcha pelo CLIENTE** com **resolução híbrida**
   (proxy do cliente quando existe, senão o default da API) e **autosserviço no
   dashboard do cliente**. Detalhes na seção "Onde paramos".

---

## O que está pronto (Fases 1–3)

Tudo abaixo está implementado, testado e validado por e2e real. **Todas as telas novas
estão em `/admin`** — o dashboard do cliente (`/dashboard`) ainda NÃO foi tocado.

### Fase 1 — Observabilidade ✅
Espinha dorsal: `correlation_id` propagado ponta a ponta + ingestão de logs estruturados.

- **Backend**
  - Propagação: `proxy/service.py::build_upstream_headers(api, headers, correlation_id)`
    injeta `X-Correlation-Id`; chamado em `proxy/router.py::_dispatch`.
  - Novo domínio `app/domains/ingest/`: `POST /ingest/logs` (batch, auth por **service
    token** no header `X-Service-Token`) e `POST /ingest/apis/{api_id}/token` (admin gera/
    rotaciona token). Token guardado como `service_token_prefix`+`service_token_hash` em
    `external_apis` (migration `m3b4c5d6e7f8`). Logs → coleção Mongo **`app_logs`** (TTL
    `app_log_retention_days`, default 7).
  - Leitura admin em `app/domains/logs/`: `GET /logs/admin/app` (filtros) e
    `GET /logs/admin/trace/{correlation_id}` (timeline unificada gateway+app).
    Funções: `get_app_logs`, `get_trace_by_correlation_id`, `mask_sensitive_values`.
- **SDK**: `context` (correlation_id via contextvars), `logging` (BridgeLogger: buffer +
  flush async + retry/backoff + fallback local), `transport`, `errors` (taxonomia
  BridgeError), `events` (LogLevel + eventos canônicos), `config`, `integrations/fastapi.install()`.
- **Frontend**: `/admin/debug` — busca por correlation_id → timeline; logs recentes clicáveis.

### Fase 2 — Health & Status ✅
- **Backend**: novo domínio `app/domains/status/`. `POST /ingest/status` (service token, no
  ingest router). `GET /status/overview` e `/status/events` (admin). `GET /status/stream`
  (**SSE**, auth por `?token=` JWT admin — EventSource não manda header). Mongo:
  `api_status_latest` (upsert), `api_status_history` (TTL), `status_events` (transições).
  Config `status_*` em `core/config.py`.
- **SDK**: `health.py` (`StatusRegistry`: checks de readiness → healthy/degraded/down),
  `status_reporter.py` (heartbeat). `install()` agora expõe `/health` (liveness) e
  `/status` (readiness) + inicia heartbeat; `app.state.bridge_status` para registrar checks.
- **Frontend**: `/admin/status` — cards por API + checks + transições, tempo real (EventSource).

### Fase 3 — Proxies ✅
- **Backend**: novo domínio `app/domains/proxies/`. Tabelas `proxy_pools` e `proxies`
  (creds criptografadas), `external_apis.proxy_pool_id` (migration `n4c5d6e7f8a9`). CRUD
  admin `/proxies/*` (pools, proxies, `PUT /proxies/assignments/{api_id}`). Endpoints SDK
  no ingest router: `GET /ingest/proxies` (config do pool, descriptografada, só ativos, por
  prioridade) e `POST /ingest/proxies/report` (marca failing + last_error). `APIResponse`
  agora inclui `proxy_pool_id`.
- **SDK**: `proxy.py` — `ProxyEndpoint` (`.url`) e `ProxyClient` (cache `proxy_cache_ttl`,
  `acquire()` por prioridade, `report_failure()`, `with_failover()`).
- **Frontend**: `/admin/proxies` — pools, proxies (status/failover/last_error), atribuição API→pool.

---

## Como rodar (ambiente Docker do usuário)
Containers: `bridge_backend`, `bridge_frontend`, `bridge_postgres`, `bridge_redis`, `bridge_mongo`.
A imagem do backend (`bridgeapi-backend`) tem todas as deps (inclusive p/ a SDK).

```bash
# Backend (421 testes)
docker exec bridge_backend pytest tests/unit/ -q --no-cov

# Migrations (head atual: n4c5d6e7f8a9)
docker exec bridge_backend alembic upgrade head

# bridge-sdk (53 testes) — montada na imagem do backend
docker run --rm -v "$PWD/bridge-sdk:/sdk" -w /sdk -e PYTHONPATH=/sdk bridgeapi-backend python -m pytest -q

# Frontend (89 jest + typecheck + lint)
docker exec bridge_frontend npm test
docker exec bridge_frontend npx tsc --noEmit      # erros pré-existentes só em __tests__ (sem @types/jest)
docker exec bridge_frontend npx eslint src/...
```
Estado atual dos testes: **backend 421 · sdk 53 · frontend 89** — todos verdes.

---

## Convenções e gotchas
- **Service token** formato `brgsvc_<prefix>_<secret>`; gerado por `POST /ingest/apis/{api_id}/token`
  (admin), mostrado uma única vez. A API o usa no header `X-Service-Token`.
- **SSE** (`/status/stream`) autentica por `?token=<jwt admin>` (EventSource não envia header).
- **Cripto de credenciais**: reusa `app/core/security.py::encrypt_value/decrypt_value`.
- **Migrations** em `backend/alembic/versions/` seguem o padrão de revision id alfabético
  (…l2…, m3…, n4…). Sempre testar upgrade/downgrade.
- **SDK** não está instalada nos containers; testa-se montando o diretório na imagem do backend.
- Logs estruturados vão para Mongo `app_logs`; request logs do gateway em `request_logs`
  (a timeline une os dois por correlation_id).

---

## Onde paramos — Fase 4 (PRÓXIMA)

**Captcha + camada de autosserviço do cliente**, aplicada a proxy E captcha de uma vez.
Surgiu da pergunta do dono: "tem APIs em que o CLIENTE configura o proxy dele, não só o admin".

### Decisões já tomadas (não reabrir)
- **Resolução híbrida**: na requisição do cliente X para a API Y, usa o proxy/captcha que o
  cliente X configurou para Y; senão cai no default da API (admin).
- **Cliente gerencia no `/dashboard`** (autosserviço, escopado à conta, liberado por capability).
  Admin continua vendo/gerenciando tudo.
- **Fazer junto com captcha** — o mesmo padrão "config pelo cliente" vale para os dois.

### Implicações de arquitetura (a fazer)
1. **Propagar o cliente** até a downstream: header `X-Bridge-Client: <account_id>` no
   `proxy/router.py::_dispatch` (a Bridge já tem `account.id` ali) — análogo ao correlation_id.
2. **Account scoping**: `proxies.account_id` e `proxy_pools.account_id` (nullable; NULL =
   plataforma). Override por cliente: tabela `api_client_proxy_pool (api_id, account_id, pool_id)`;
   fallback continua em `external_apis.proxy_pool_id`.
3. **Resolução híbrida** no `GET /ingest/proxies`: SDK manda o client atual; plataforma resolve
   override do cliente → senão default da API.
4. **SDK**: contextvar de `client` (preenchido pelo middleware, como o correlation_id) +
   cache da config **keyed por client** no `ProxyClient`.
5. **Dashboard do cliente**: páginas `/dashboard/proxies` (e depois `/dashboard/captcha`),
   CRUD escopado à conta, nova capability (ex.: `Feature.PROXIES` / `Feature.CAPTCHA` em
   `app/core/authz.py`).

### Captcha (espelha proxy, já no novo padrão)
- Modelo `captcha_providers` (com `account_id`, `balance_usd`, `priority`, `status`, creds
  criptografadas) + override por cliente.
- Endpoints SDK: `GET /ingest/captcha` (resolvido por cliente) + `POST /ingest/captcha/report`.
- SDK `CaptchaClient` (failover por prioridade + checagem de saldo) — espelha `ProxyClient`.
- **Saldo** entra no `/status` (degraded abaixo do limiar) e em alertas.
- Admin `/admin/captcha` + dashboard `/dashboard/captcha`.

### Ordem sugerida
- **4a**: camada cliente p/ PROXY (account scoping + `X-Bridge-Client` + resolução híbrida +
  dashboard de proxy do cliente). Validar.
- **4b**: captcha inteiro já nesse padrão (admin + cliente).

### Roadmap restante
| Fase | Status |
|---|---|
| 1 Observabilidade · 2 Health/Status · 3 Proxies | ✅ feito |
| 4 Captcha + autosserviço do cliente (proxy+captcha) | ⬜ próxima |
| 5 Execução híbrida / jobs (timeout, 202+job, idempotência, billing) | ⬜ |
| 6 Histórico/replay + alertas | ⬜ |

---

## Mapa de commits (esta entrega)
Commits feitos por **componente** (as fases se entrelaçam em arquivos compartilhados como
`main.py`, `lib/api.ts`, `ingest/router.py`, então o split por componente é o que mantém cada
commit coerente):
1. `docs:` documentos de requisitos + este handoff.
2. `feat(backend):` domínios ingest/status/proxies, leitura de logs, propagação de
   correlation_id, migrations e testes (Fases 1–3).
3. `feat(bridge-sdk):` a SDK completa (context, logging, health, status, proxy, errors).
4. `feat(admin):` telas `/admin/debug`, `/admin/status`, `/admin/proxies` + client API.
