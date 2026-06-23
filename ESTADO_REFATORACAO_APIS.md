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

### Fase 4a — Proxy POR API (substitui a camada de pools) ✅
> **Mudança de direção (pedido do dono):** acabaram os "pools/fornecedores configurados fora".
> Agora **cada API tem sua própria lista de proxies** (e, na 4b, de captchas), configurada
> dentro da API. A migration `p6e7f8a9b0c1` **removeu** `proxy_pools`,
> `api_client_proxy_pool` e `external_apis.proxy_pool_id` (a primeira versão da 4a).

Modelo atual:
- **`proxies`** pertence a UMA API (`api_id`) e a um dono (`account_id`: NULL = admin/plataforma;
  preenchido = cliente). Vários por API, com prioridade/failover e toggle/editar/excluir.
  `status`/`last_error` = monitoramento.
- **`external_apis.uses_proxy`** (bool): nem toda API usa proxy — decide-se no cadastro.
- **`permissions.proxy_managed_by_client`** (bool): no momento em que o admin libera a API pro
  cliente, ele decide se o **cliente gerencia o próprio proxy**. Se sim, a Bridge usa os proxies
  do cliente (ele começa sem nenhum e configura os dele); se não, usa os do admin.
- **Resolução** (`proxies/service.py`): `resolve_owner_for_request(db, api, client_id)` →
  dono (cliente se a permissão dele marca `proxy_managed_by_client`, senão admin/None);
  `get_proxy_config_for_api` (vazio se `uses_proxy=False`) e `report_proxy_failure` usam isso.
- **Propagação**: gateway injeta `X-Bridge-Client` (anti-spoof: strip da entrada); ingest lê.
- **Endpoints**: admin `/apis/{api_id}/proxies` (CRUD), cliente `/client/apis/{api_id}/proxies`
  (CRUD, exige `Feature.PROXIES` + `proxy_managed_by_client`), monitoramento `/monitoring/proxies`,
  permissão `PATCH /permissions/{account}/{api}/config` (liga/desliga o autosserviço).
- **SDK**: contextvar `client` + middleware + `ProxyClient` com `X-Bridge-Client` e cache/failed
  keyed por client (inalterado; só consome `/ingest/proxies`).
- **Frontend**: `/admin/proxies` (escolhe API → CRUD dos proxies dela + monitoramento agregado),
  `/dashboard/proxies` (cliente, por API, guard `CAP.PROXIES`), checkbox **"usa proxy"** no
  cadastro de API, toggle **PROXY: ADMIN/CLIENTE** por linha na tela de permissões.
- **Pendência de polish (fase 4 do plano)**: embutir a lista de proxies dentro do próprio
  formulário de cadastro de API (hoje fica na tela `/admin/proxies`, escolhendo a API).

---

## Como rodar (ambiente Docker do usuário)
Containers: `bridge_backend`, `bridge_frontend`, `bridge_postgres`, `bridge_redis`, `bridge_mongo`.
A imagem do backend (`bridgeapi-backend`) tem todas as deps (inclusive p/ a SDK).

```bash
# Backend (421 testes)
docker exec bridge_backend pytest tests/unit/ -q --no-cov

# Migrations (head atual: p6e7f8a9b0c1)
docker exec bridge_backend alembic upgrade head

# bridge-sdk (53 testes) — montada na imagem do backend
docker run --rm -v "$PWD/bridge-sdk:/sdk" -w /sdk -e PYTHONPATH=/sdk bridgeapi-backend python -m pytest -q

# Frontend (89 jest + typecheck + lint)
docker exec bridge_frontend npm test
docker exec bridge_frontend npx tsc --noEmit      # erros pré-existentes só em __tests__ (sem @types/jest)
docker exec bridge_frontend npx eslint src/...
```
Estado atual dos testes: **backend 427 · sdk 64 · frontend 89** — todos verdes.

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

## Onde paramos — Fase 4b (PRÓXIMA): CAPTCHA por API

A **Fase 4a (proxy por API)** está pronta, testada e documentada acima. A 4b é
**captcha no MESMO padrão da 4a** (por API, admin+cliente, com toggle/editar/excluir),
mais o **saldo** como diferencial.

### Decisões já tomadas (não reabrir)
- Proxy/captcha **dentro da API**, sem pools/fornecedores à parte. Vários por API.
- Admin decide no cadastro se a API usa proxy/captcha (`uses_proxy`, futuro `uses_captcha`).
- Na permissão, admin decide se o cliente gerencia o próprio (proxy: `proxy_managed_by_client`;
  captcha: futuro `captcha_managed_by_client`). Ligado → cliente configura o dele; senão admin.

### Como espelhar a 4a no captcha (mapa concreto)
O **proxy é o template literal** — clonar o desenho por-API:
1. **Modelo** `captcha_providers`: `api_id` (FK), `account_id` (NULL=admin), `name`,
   `provider`, `api_key_encrypted`, `balance_usd`, `priority`, `status`, `last_error*`.
   (Sem tabela de pool/override — a posse é por `api_id`+`account_id`, igual `proxies`.)
2. **Flags**: `external_apis.uses_captcha` + `permissions.captcha_managed_by_client`.
3. **Resolução** `captcha/service.py`: `resolve_owner_for_request` (reusa a lógica do proxy),
   `get_captcha_config_for_api(db, api, client_id)` (vazio se `uses_captcha=False`),
   `report_captcha_failure(db, api, data, client_id)`.
4. **Endpoints**: ingest `GET /ingest/captcha` + `POST /ingest/captcha/report` (lê `X-Bridge-Client`,
   já propagado); admin `/apis/{api_id}/captchas`; cliente `/client/apis/{api_id}/captchas`;
   monitoramento `/monitoring/captchas`; `Feature.CAPTCHA` em `core/authz.py`.
5. **SDK** `CaptchaClient` espelha `ProxyClient` (failover por prioridade + **checagem de saldo**),
   cache/failed-set keyed por client (o contextvar `client` já existe).
6. **Frontend**: captcha na tela `/admin/proxies` (ou `/admin/providers`) e `/dashboard`,
   checkbox "usa captcha" no cadastro de API, toggle na permissão.
- **Saldo** (`balance_usd`): o `CaptchaClient` pula provider sem saldo; saldo entra no `/status`
  (degraded abaixo do limiar) e em alertas (Fase 6).

### Roadmap restante
| Fase | Status |
|---|---|
| 1 Observabilidade · 2 Health/Status · 3 Proxies | ✅ feito |
| 4a Proxy POR API (admin + cliente, monitoramento) | ✅ feito |
| 4b Captcha POR API (mesmo padrão + saldo) | ⬜ próxima |
| 4c Polish: embutir proxy/captcha no formulário de cadastro da API | ⬜ |
| 4d API **POST**: `request_method` + `request_body_template` ({query}/{token}) no gateway | ⬜ |
| 4e Import de OpenAPI/Swagger p/ pré-preencher o body template | ⬜ |
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
