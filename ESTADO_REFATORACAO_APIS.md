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

### Fase 4b — Captcha POR API (espelha a 4a) ✅
Mesmo desenho da 4a, agora para captcha, com **saldo** como diferencial.

- **Backend**: novo domínio `app/domains/captcha/`. Tabela `captcha_providers`
  (`api_id` + `account_id`; `api_key_encrypted`, `balance_usd`, `priority`, `status`,
  `last_error*`). `external_apis.uses_captcha` + `permissions.captcha_managed_by_client`.
  Migration `q7f8a9b0c1d2`. Resolução por dono em `get_captcha_config_for_api` /
  `report_captcha_failure` (idêntica ao proxy). Endpoints: admin `/apis/{id}/captchas`,
  cliente `/client/apis/{id}/captchas` (exige `Feature.CAPTCHA` + flag), `/monitoring/captchas`,
  ingest `GET /ingest/captcha` + `POST /ingest/captcha/report` (lê `X-Bridge-Client`). O report
  aceita `balance_usd` p/ a SDK atualizar o saldo.
- **SDK**: `captcha.py` — `CaptchaProvider` (`.has_balance`) e `CaptchaClient` (espelha
  `ProxyClient`: cache/failed keyed por client + `X-Bridge-Client`; `acquire`/`with_failover`
  **pulam provedores sem saldo**). Config `captcha_cache_ttl`.
- **Frontend**: `/admin/captcha` (escolhe API → CRUD + monitoramento com saldo),
  `/dashboard/captcha` (cliente, por API, guard `CAP.CAPTCHA`), checkbox **"usa captcha"** no
  cadastro de API, toggle **CAPTCHA: ADMIN/CLIENTE** por linha na tela de permissões.

---

## Como rodar (ambiente Docker do usuário)
Containers: `bridge_backend`, `bridge_frontend`, `bridge_postgres`, `bridge_redis`, `bridge_mongo`.
A imagem do backend (`bridgeapi-backend`) tem todas as deps (inclusive p/ a SDK).

```bash
# Backend (489 testes)
docker exec bridge_backend pytest tests/unit/ -q --no-cov

# Migrations (head atual: u1d2e3f4a5b6)
docker exec bridge_backend alembic upgrade head

# bridge-sdk (53 testes) — montada na imagem do backend
docker run --rm -v "$PWD/bridge-sdk:/sdk" -w /sdk -e PYTHONPATH=/sdk bridgeapi-backend python -m pytest -q

# Frontend (89 jest + typecheck + lint)
docker exec bridge_frontend npm test
docker exec bridge_frontend npx tsc --noEmit      # erros pré-existentes só em __tests__ (sem @types/jest)
docker exec bridge_frontend npx eslint src/...
```
Estado atual dos testes: **backend 489 · sdk 75 · frontend 89** — todos verdes.

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

## Onde paramos — Fase 6: falta a metade de **histórico/replay**

A Fase 6 tem duas metades. A de **alertas** está pronta (abaixo). Falta a de
**histórico/replay** (§8 dos requisitos):
- **Retenção estendida** do `request_logs` (config separada do TTL de 24h — ex. 7–30 dias) p/ debug.
- **Replay** `POST /logs/admin/{correlation_id}/replay` — **admin-only, sem billing** (decisão do
  dono): reexecuta a consulta a partir do snapshot, reusando o caminho do `_dispatch`, marcando o
  request como replay (não cobra nem grava métrica de billing).
- **Mascaramento/PII** no body + política de expurgo (LGPD).

### Fase 6 (metade) — Alertas in-app escopados por dono ✅
Decisões do dono: **in-app** (sem email/webhook externo); aparece no painel do **admin** E no
painel do **cliente que gerencia o próprio proxy/captcha** (escopo por dono).

- **Backend**: novo domínio `app/domains/alerts/`. Tabela `alerts` (`account_id` NULL=plataforma/
  admin · preenchido=cliente dono; `api_id`, `resource_id`, `type`, `severity`, `status`,
  `message`, `context`, timestamps; migration `u1d2e3f4a5b6`). `service` com `raise_alert`
  (**dedup**: não duplica alerta aberto p/ mesmo conta+api+tipo+recurso), `resolve_alerts`
  (**auto-resolve** quando a condição limpa), `list_alerts` (admin vê tudo; cliente só os da própria
  conta; devolve `active_count` p/ o sino) e `acknowledge_alert` (escopado).
- **Tipos/gatilhos**: `api_down`/`api_degraded` (escopo plataforma) disparados em
  `status/service.record_status` (que passou a expor a transição) via `ingest_status`;
  `captcha_low_balance` (limiar `captcha_low_balance_threshold_usd`=5.0) e `captcha_failing`
  em `report_captcha_failure`; `proxy_failing` em `report_proxy_failure` — todos escopados ao
  `account_id` do recurso.
- **Endpoints**: admin `GET /admin/alerts` + `POST /admin/alerts/{id}/ack`; cliente
  `GET /client/alerts` + `POST /client/alerts/{id}/ack` (escopado à conta).
- **Frontend**: componente `AlertsPanel` (lista + ack + filtro ativos/histórico) usado por
  `/admin/alerts` e `/dashboard/alerts`; componente `AlertBell` (sino com contador, polling 30s)
  no header de ambos os painéis. Nav nos dois layouts (cliente gated por `CAP.PROXIES||CAP.CAPTCHA`).

### Fase 5b — Entrega assíncrona (SSE/webhook) + admin ✅
- **SSE** `GET /jobs/{id}/stream` (`jobs/router.py`): autoriza pela `X-Bridge-Key` via `?key=`
  (EventSource não manda header), faz poll de `job_stream_interval_seconds` (2s) e emite o
  `JobResponse` até o estado terminal ou `job_stream_max_seconds` (600s).
- **Webhook** (`jobs/webhook.py`): se a request trouxe `X-Bridge-Callback` (validado http(s)
  no `proxy/router.py::_dispatch`), o `runner.finalize_job` faz `POST` assinado **HMAC-SHA256**
  (header `X-Bridge-Signature: sha256=<hex>`, segredo `webhook_signing_secret` ou `app_secret_key`)
  com retry (`webhook_max_attempts`=3, `webhook_timeout_s`=10). Estado em
  `proxy_jobs.webhook_status` (pending→delivered/failed). Colunas `callback_url`+`webhook_status`
  (migration `t0c1d2e3f4a5`). Best-effort: o resultado fica sempre por polling/SSE.
- **Admin**: `GET /admin/jobs` (lista paginada) e `GET /admin/jobs/{id}` (detalhe). *(Renomeou o
  antigo `GET /jobs` admin da 5a para `/admin/jobs`; `GET /jobs/{id}` cliente segue por X-Bridge-Key.)*
  Schemas expõem `webhook_status` (lista) e `callback_url`/`webhook_status` (detalhe).
- **Frontend**: `/admin/jobs` — tabela paginada (status, correlation_id, HTTP, webhook, custo,
  datas) + drawer de detalhe (corpo da resposta, callback, latência). Nav em `admin/layout.tsx`.
- **Pendente (opcional)**: limpeza por TTL/cron usando `expires_at`. *Idempotência só cobre o
  caminho que virou job (síncrono não cria job) — herdado da 5a.*

### Fase 5a — Execução híbrida (núcleo) ✅
Timeout configurável + fork síncrono→assíncrono + jobs + polling + idempotência + billing.

- **Config**: `sync_timeout_s` (90), `upstream_timeout_s` (300), `job_retention_hours` (168).
  Removido o `30.0` hardcoded.
- **`proxy/router.py::_dispatch`**: o forward roda num `httpx.AsyncClient` **próprio** via
  `asyncio.create_task`, corrido contra `sync_timeout_s` com `asyncio.wait`. Dentro do limite →
  `200` normal (contrato preservado). Excedeu → cria job (status `running`), devolve
  **`202 + {job_id, status_url}`** e um `add_done_callback` agenda `finalize_job` em background.
- **Domínio `app/domains/jobs/`**: modelo `proxy_jobs` (snapshot, result, status, cost, etc.;
  migration `s9b0c1d2e3f4`), `service` (create/get/complete/list + idempotência),
  `runner.finalize_job` (abre sessão/cliente próprios, persiste resultado + métrica/billing +
  request log), `router` (`GET /jobs/{id}` cliente por X-Bridge-Key; `GET /jobs` admin).
- **Billing**: síncrono cobra em `200` (como antes); assíncrono cobra em `done`+`200`
  (`timeout`/`failed` não cobram). Métrica gravada nos dois caminhos.
- **Idempotência**: header `Idempotency-Key`; `uq_proxy_jobs_idem (account_id, idempotency_key)`;
  repetir devolve o estado do job (sem reprocessar). *(MVP: só cobre o caminho que virou job;
  requests que terminam síncronos não criam job, então não são deduplicadas.)*
- **Segurança**: `GET /jobs/{id}` exige a mesma `X-Bridge-Key` e só mostra job da própria conta.

### 4d — API POST ✅
`external_apis.request_method` (NULL = repassa o método do cliente; legado intacto) e
`request_body_template` (renderiza `{query}`/`{token}`). No gateway
(`proxy/service.py::forward_to_upstream`): usa `request_method` quando setado, senão o método
do cliente; quando há `request_body_template`, monta o body renderizado (+ `content-type: application/json`
se ausente), senão repassa o body do cliente. Migration `r8a9b0c1d2e3`. No form de `/admin/apis`:
select "Método na API original" + textarea "Body template". GET/passthrough seguem funcionando.

### 4e — Import de OpenAPI/Swagger ✅
`apis/openapi.py` parseia JSON **ou** YAML (resolve `$ref` locais, suporta OpenAPI 3 e
Swagger 2) e, por operação, gera um `request_body_template` de exemplo a partir do schema do
request body. `fetch_spec(url)` busca a doc **por URL** (server-side, só http(s)) e delega ao
parser. Endpoints admin: `POST /apis/import` (recebe `{url}`, devolve `OpenAPIImportResponse`)
e `POST /apis/import/bulk` (`bulk_register_apis` cria as operações selecionadas como
**rascunho `inactive`**, resiliente: pula nome/slug duplicado e base_url não-http(s) com
motivo). No `/admin/apis`, o botão **"Importar OpenAPI"** abre um modal de 3 passos: informar a
**URL da doc** → **tabela de staging** (todas as operações pré-configuradas e editáveis: nome,
base_url, método, body template, checkbox incluir) → **"Importar N como rascunho"** cria todas
inativas de uma vez; o admin revisa/configura (proxy/captcha/custo) e ativa cada uma depois na
tela de edição. Sem migration. (`register_api` ganhou o parâmetro `status`.)

### Histórico (não reabrir)

### 4c — Embutir no formulário de cadastro da API ✅
O cadastro de API (`/admin/apis`, modo edição) agora mostra, abaixo do form, painéis
**Proxies desta API** e **Captcha desta API** (add/editar-status/excluir), gated pelas
checkboxes `uses_proxy`/`uses_captcha`, reusando as funções `*ApiProxy*`/`*ApiCaptcha*` de
`lib/api.ts` (componentes `ApiProxyPanel`/`ApiCaptchaPanel`). Só aparecem em edição (precisam
do `api_id` salvo) — ao criar, salva-se a API e reabre-se para configurar. As telas
`/admin/proxies` e `/admin/captcha` seguem existindo como **monitoramento agregado**.

### Decisões já tomadas (não reabrir)
- Proxy/captcha **dentro da API**, sem pools/fornecedores à parte. Vários por API.
- Admin decide no cadastro se a API usa proxy/captcha (`uses_proxy`/`uses_captcha`).
- Na permissão, admin decide se o cliente gerencia o próprio
  (`proxy_managed_by_client`/`captcha_managed_by_client`). Ligado → cliente configura o dele;
  senão usa o do admin.
- **Saldo** do captcha: a SDK pula provider sem saldo; entra no monitoramento e (Fase 6) em alertas.

### Roadmap restante
| Fase | Status |
|---|---|
| 1 Observabilidade · 2 Health/Status · 3 Proxies | ✅ feito |
| 4a Proxy POR API (admin + cliente, monitoramento) | ✅ feito |
| 4b Captcha POR API (mesmo padrão + saldo) | ✅ feito |
| 4c Embutir proxy/captcha no formulário de cadastro da API | ✅ feito |
| 4d API **POST**: `request_method` + `request_body_template` ({query}/{token}) no gateway | ✅ feito |
| 4e Import de OpenAPI/Swagger p/ pré-preencher o body template | ✅ feito |
| 5a Execução híbrida núcleo (timeout, 202+job, polling, idempotência, billing) | ✅ feito |
| 5b Entrega assíncrona (SSE/webhook) + `/admin/jobs` | ✅ feito |
| 6a Alertas in-app (status/saldo/proxy) escopados por dono + sino | ✅ feito |
| 6b Histórico/replay (retenção estendida + replay admin-only + PII) | ⬜ próxima |

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
