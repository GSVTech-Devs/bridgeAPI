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

### Fase 4a — Proxy do cliente (autosserviço + resolução híbrida) ✅
Camada de cliente para PROXY: cada conta gerencia seus próprios pools/proxies e escolhe,
por API, qual pool seu a Bridge usa nas chamadas dela — senão cai no default da API (admin).

- **Backend**
  - Modelos: `proxy_pools.account_id` e `proxies.account_id` (nullable; NULL = plataforma)
    + nova tabela `api_client_proxy_pool (api_id, account_id, pool_id)` (override por cliente).
    Nome de pool passa a ser único **por dono** (`uq_proxy_pools_account_name`).
    Migration `o5d6e7f8a9b0` (head atual). FKs `ondelete=CASCADE` p/ conta.
  - Resolução híbrida em `proxies/service.py::resolve_pool_id_for_client(db, api, client_id)`:
    override do cliente → senão `api.proxy_pool_id`. Usada por `get_pool_config_for_api` e
    `report_proxy_failure` (ambas agora aceitam `client_id`).
  - Propagação do cliente: `proxy/service.py::build_upstream_headers` injeta
    **`X-Bridge-Client: <account.id>`** (e o strip-a da entrada p/ não ser forjável);
    chamado em `proxy/router.py::_dispatch`. O ingest lê o header (`GET/POST /ingest/proxies*`).
  - Autosserviço: novo `proxies/client_router.py` em **`/client/proxies/*`** (pools, proxies,
    `GET/PUT /client/proxies/assignments`), tudo escopado à conta e liberado por
    `Feature.PROXIES` (em `core/authz.py`, atribuível por role). Helpers de posse
    `get_owned_pool/_proxy` tratam "não é seu" como 404.
  - **Anti-spoof**: o cliente nunca define o próprio `X-Bridge-Client`; quem manda é o gateway.
- **SDK**: `context.py` ganhou o contextvar `client` (`set/get/use_client`,
  `client_from_headers`, sem gerar quando ausente). O middleware FastAPI seta o client a
  partir do header. `ProxyClient` manda `X-Bridge-Client` e tem **cache + failed-set keyed
  por client** (pools diferem por cliente).
- **Frontend**: `/dashboard/proxies` (espelha o admin, escopado à conta, guard por
  `CAP.PROXIES`), item no menu do dashboard, funções `*ClientProxy*` em `lib/api.ts`.

---

## Como rodar (ambiente Docker do usuário)
Containers: `bridge_backend`, `bridge_frontend`, `bridge_postgres`, `bridge_redis`, `bridge_mongo`.
A imagem do backend (`bridgeapi-backend`) tem todas as deps (inclusive p/ a SDK).

```bash
# Backend (421 testes)
docker exec bridge_backend pytest tests/unit/ -q --no-cov

# Migrations (head atual: o5d6e7f8a9b0)
docker exec bridge_backend alembic upgrade head

# bridge-sdk (53 testes) — montada na imagem do backend
docker run --rm -v "$PWD/bridge-sdk:/sdk" -w /sdk -e PYTHONPATH=/sdk bridgeapi-backend python -m pytest -q

# Frontend (89 jest + typecheck + lint)
docker exec bridge_frontend npm test
docker exec bridge_frontend npx tsc --noEmit      # erros pré-existentes só em __tests__ (sem @types/jest)
docker exec bridge_frontend npx eslint src/...
```
Estado atual dos testes: **backend 435 · sdk 64 · frontend 89** — todos verdes.

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

## Onde paramos — Fase 4b (PRÓXIMA): CAPTCHA

A **Fase 4a (proxy do cliente)** está pronta, testada e documentada acima. Falta a 4b:
**captcha inteiro já no padrão "config pelo cliente"** — espelhar tudo que foi feito p/ proxy.

### Decisões já tomadas (não reabrir)
- **Resolução híbrida**: na requisição do cliente X para a API Y, usa o proxy/captcha que o
  cliente X configurou para Y; senão cai no default da API (admin). **(já implementado p/ proxy)**
- **Cliente gerencia no `/dashboard`** (autosserviço, escopado à conta, liberado por capability).
  Admin continua vendo/gerenciando tudo.

### Como espelhar a 4a no captcha (mapa concreto)
O proxy é o template — repita o mesmo desenho:
1. **Modelos**: `captcha_providers` com `account_id` (nullable) + creds criptografadas
   (`api_key_encrypted`), `balance_usd`, `priority`, `status`. Override por cliente em
   `api_client_captcha_provider (api_id, account_id, provider_id)`. Default da API em
   `external_apis.captcha_provider_id` (ou um pool, se preferir manter simetria com proxy).
2. **Resolução híbrida**: `captcha/service.py::resolve_provider_for_client(db, api, client_id)`
   — clona `resolve_pool_id_for_client`. `get_captcha_config_for_api(db, api, client_id)` e
   `report_captcha_failure(db, api, data, client_id)`.
3. **Propagação**: o `X-Bridge-Client` já está no upstream (4a) — captcha reusa de graça.
4. **Endpoints SDK** no ingest router: `GET /ingest/captcha` (resolvido por cliente) +
   `POST /ingest/captcha/report`, ambos lendo o header `X-Bridge-Client` (igual proxy).
5. **Autosserviço**: `captcha/client_router.py` em `/client/captcha/*` + `Feature.CAPTCHA`
   em `core/authz.py` (atribuível). Admin em `/captcha/*` (clona `proxies/router.py`).
6. **SDK** `CaptchaClient` espelha `ProxyClient` (failover por prioridade + **checagem de
   saldo**), cache/failed-set keyed por client (o contextvar `client` já existe).
7. **Frontend**: `/admin/captcha` + `/dashboard/captcha` (guard `CAP.CAPTCHA`), funções em
   `lib/api.ts`.

### Detalhes específicos de captcha (além do espelho do proxy)
- **Saldo** (`balance_usd`): além do failover por prioridade, o `CaptchaClient` pula provider
  sem saldo; o saldo entra no `/status` (degraded abaixo do limiar) e em alertas (Fase 6).

### Roadmap restante
| Fase | Status |
|---|---|
| 1 Observabilidade · 2 Health/Status · 3 Proxies | ✅ feito |
| 4a Proxy do cliente (autosserviço + resolução híbrida) | ✅ feito |
| 4b Captcha (mesmo padrão: admin + cliente) | ⬜ próxima |
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

### Fase 4a (proxy do cliente) — sugestão de split de commits
5. `feat(backend):` account scoping de proxies, resolução híbrida, `X-Bridge-Client`,
   `client_router` `/client/proxies/*`, `Feature.PROXIES`, migration `o5d6e7f8a9b0` + testes.
6. `feat(bridge-sdk):` contextvar `client`, propagação no middleware, `ProxyClient` keyed
   por client + header `X-Bridge-Client` + testes.
7. `feat(dashboard):` `/dashboard/proxies` (autosserviço), `CAP.PROXIES`, client API em `lib/api.ts`.
