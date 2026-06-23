# Documento de Requisitos — Refatoração das APIs + Plataforma Bridge

## Context

A Bridge API é um gateway que centraliza o acesso dos clientes às APIs do próprio
dono (consultas complexas via POST, com proxies e resolução de captcha por trás).
Hoje o gateway já faz forwarding, autentica chaves, valida permissões, aplica rate
limit (Redis) e grava logs (MongoDB, TTL 24h) + métricas (Postgres). Mas falta a
infraestrutura para operar isso de forma confiável em escala:

- **Não existe entidade de Proxy** — proxy hoje é só a `base_url` da `ExternalAPI`.
  Sem gestão, sem health, sem troca/failover, sem distinção "proxy meu vs do cliente".
- **Não existe captcha** em lugar nenhum do código.
- **Logs são só internos do gateway** — não há canal para as APIs downstream
  *enviarem* logs estruturados para a plataforma.
- **Timeout fixo de 30s** (hardcoded em `proxy/router.py:32`) — incompatível com
  consultas que demoram minutos por causa de proxy + captcha.
- **Health check é trivial** (`GET /health` → `{"status":"ok"}` em `main.py:47`),
  sem visão de saúde das APIs/proxies/captcha em tempo real.
- **Histórico de pesquisas** existe parcialmente (logs Mongo 24h), mas curto e sem
  foco em debug/replay.

**Decisões tomadas (definem o documento):**
1. **Execução híbrida**: síncrono até ~90s; se passar, vira job assíncrono
   (`202 + job_id`) com polling/webhook/SSE.
2. **Escopo**: contrato dos dois lados — o que cada API downstream expõe/envia E o
   que a plataforma Bridge ganha.
3. **Padronização via SDK/lib compartilhada** (`bridge-sdk`) que toda API importa.

O objetivo final: **um `correlation_id` único atravessa toda a cadeia**
(cliente → Bridge → API downstream → proxy → captcha), e tudo (logs, status, custo,
erros) se ancora nele. É isso que torna "fácil de achar os problemas" real.

---

## 1. Conceito central: o contrato Bridge ↔ API downstream

A refatoração padroniza um **contrato** que toda API downstream cumpre, fornecido
pela `bridge-sdk` (lib interna, instalável via pip):

```
bridge-sdk/
  logging/     # logger estruturado JSON + envio assíncrono p/ a plataforma
  health/      # rotas /health (liveness) e /status (readiness profundo) prontas
  proxy/       # cliente de proxy com seleção/rotação/failover + report de status
  captcha/     # cliente de captcha com failover + checagem de saldo
  context/     # propagação do correlation_id (contextvars) por toda a request
  errors/      # taxonomia de erros estruturados (BridgeError + subclasses)
```

Refatorar uma API = **adotar a SDK** e remover o código ad-hoc equivalente. A SDK é
versionada (semver); a plataforma valida a versão da SDK reportada no `/status`.

---

## 2. Requisitos — Logging estruturado + ingestão

**Objetivo:** logs bem estruturados, padronizados, correlacionados, fáceis de buscar.

### 2.1 Formato (lado da API — `bridge-sdk/logging`)
- Toda linha de log é **JSON estruturado** com campos fixos:
  `timestamp, level, correlation_id, api_id, api_version, sdk_version, event,
  message, duration_ms, proxy_id, captcha_provider, error_code, extra{}`.
- **Níveis**: `DEBUG, INFO, WARNING, ERROR, CRITICAL`.
- **Eventos de ciclo de vida** padronizados (enum), ex:
  `request.received, proxy.acquired, proxy.failed, captcha.requested,
  captcha.solved, captcha.failed, upstream.called, request.completed`.
- `correlation_id` **nunca** é gerado pela API — vem propagado da Bridge (ver §7).

### 2.2 Ingestão (lado da plataforma — novo domínio `app/domains/ingest`)
- Novo endpoint **`POST /ingest/logs`** (batch, aceita array de log entries).
- Autenticado por **service token** por API (novo conceito — não usar a chave de
  cliente). Tabela `api_service_tokens` ou campo na `ExternalAPI`.
- Validação de schema via Pydantic; rejeita entries malformadas com erro claro.
- Persistência no **MongoDB** (reusar `logs/service.py`), em coleção
  `app_logs` separada de `request_logs`, com TTL próprio.
- **Backpressure / resiliência**: a SDK envia em background (buffer + flush
  periódico + retry com backoff). Se a plataforma cair, a API não trava nem perde a
  request — degrada para log local em disco.

### 2.3 Busca/leitura (admin)
- `GET /logs/admin/app` com filtros: `correlation_id, api_id, level, event,
  error_code, since/until`, paginação.
- **Vista unificada por `correlation_id`**: dado um ID, retornar a timeline
  completa (logs do gateway de `request_logs` + logs da app de `app_logs`),
  ordenada — esse é o painel de debug principal.

---

## 3. Requisitos — Health check & status em tempo real

**Objetivo:** saber em tempo real se cada API/proxy/captcha está funcionando.

### 3.1 Lado da API (`bridge-sdk/health`)
Duas rotas, semântica distinta (blind spot comum — ver §10):
- **`GET /health` (liveness)** — o processo está de pé? Resposta rápida, sem checar
  dependências. Para load balancer / k8s.
- **`GET /status` (readiness profundo)** — *consigo realmente atender?* Retorna JSON:
  ```json
  {
    "status": "healthy|degraded|down",
    "sdk_version": "1.4.0",
    "checks": {
      "proxy_pool":    {"status":"healthy","available":8,"total":10},
      "captcha":       {"status":"degraded","balance_usd":2.10,"provider":"x"},
      "target_reachable": {"status":"healthy","latency_ms":420}
    },
    "uptime_s": 38211
  }
  ```
- `degraded` = funciona mas com risco (ex: saldo de captcha baixo, poucos proxies).

### 3.2 Lado da plataforma (novo domínio `app/domains/status`)
- **Coletor** que faz polling periódico de `/status` de cada API ativa (job de
  fundo — APScheduler/Celery beat/cron) e armazena snapshots
  (`api_status_snapshots` no Mongo, ou Redis p/ "último estado" + Mongo p/ histórico).
- **Heartbeat push opcional**: a SDK também pode empurrar status via
  `POST /ingest/status` (cobre APIs atrás de firewall que o coletor não alcança).
- `GET /status/overview` (admin): estado atual de todas as APIs + proxies + captcha.
- **Painel de status em tempo real** no admin via **SSE** (`GET /status/stream`) —
  evita polling pesado no front. (Há precedente: o front já é centralizado em
  `frontend/src/lib/api.ts`.)
- **Alertas** (blind spot — hoje tudo é pull): regra mínima → quando uma API vira
  `down`/`degraded` ou captcha fica abaixo de um limiar, registrar evento e
  (fase 2) notificar (email/webhook).

---

## 4. Requisitos — Gestão de Proxies

**Objetivo:** proxies configurados na plataforma, com status, troca e logs de falha.

### 4.1 Modelo de dados (novo domínio `app/domains/proxies`)
Nova tabela `proxies`:
```
id, name, provider (ex: brightdata, oxylabs, cliente_x),
ownership (enum: PLATFORM | CLIENT),         # proxy meu vs do cliente
type (datacenter|residential|mobile),
scheme (http|https|socks5),
host, port,
username_encrypted, password_encrypted,      # reusar cripto de master_key (apis/service.py)
rotation (sticky|rotating), session_ttl_s,
status (active|inactive|failing),
priority (int),                              # ordem de uso p/ failover
created_at
```
- Tabela de junção `api_proxies` (N:N) **ou** `proxy_pool_id` na `ExternalAPI` —
  uma API usa um *pool* de proxies, não um só. Recomendo entidade `proxy_pools`
  + `proxy_pool_members`, com a `ExternalAPI` apontando para um pool.
- Credenciais **criptografadas em repouso** (reusar utilitário de cripto já usado em
  `master_key_encrypted`).

### 4.2 Cliente de proxy (`bridge-sdk/proxy`)
- Seleciona proxy do pool por prioridade/disponibilidade.
- **Failover automático**: ao falhar (auth falhou, conexão recusada, timeout),
  marca o proxy, emite log `proxy.failed` com `error_code`, e tenta o próximo.
- **Reporta status** de cada proxy de volta (no `/status` e/ou via ingest), para a
  plataforma mostrar claramente quando "o login do proxy falhou".

### 4.3 Plataforma
- CRUD de proxies e pools (admin) + nova tela `/admin/proxies`.
- Status de cada proxy no painel (§3.2): `active / failing` com último erro.
- **Troca de proxy sem deploy**: alterar pool/prioridade na plataforma reflete na
  próxima request (a SDK lê config do pool — via endpoint de config ou cache curto).
- Logs específicos de proxy buscáveis por `proxy_id` e `error_code`.

---

## 5. Requisitos — Provedores de Captcha

**Objetivo:** mesmos requisitos do proxy + monitoramento de saldo (blind spot).

### 5.1 Modelo (novo domínio `app/domains/captcha`)
Nova tabela `captcha_providers`:
```
id, name, provider (2captcha|anticaptcha|capsolver|...),
api_key_encrypted, endpoint,
supported_types (recaptcha_v2|v3|hcaptcha|turnstile|image),
status (active|inactive|failing),
priority, balance_usd (cache do último saldo), balance_checked_at,
created_at
```

### 5.2 Cliente (`bridge-sdk/captcha`) + plataforma
- Failover entre provedores por prioridade (igual proxy).
- **Checagem de saldo periódica** — captcha solver fica sem crédito silenciosamente;
  expor `balance_usd` no `/status` e alertar abaixo de limiar.
- Logs `captcha.requested/solved/failed` com provider, tipo, custo e duração.
- CRUD + status no admin (`/admin/captcha`); troca de provedor sem deploy.

---

## 6. Requisitos — Execução híbrida síncrono/assíncrono + timeout

**Objetivo:** consultas longas (proxy+captcha) não estouram timeout.

### 6.1 Estratégia híbrida
- Tornar o timeout **configurável** (remover `30.0` hardcoded em
  `proxy/router.py:32`; ler de `core/config.py`). Limite síncrono ~90s (config).
- No `_dispatch` (`proxy/router.py:39`): se a upstream responder dentro do limite,
  retorna `200` normal (contrato atual preservado).
- Se exceder o limite, a Bridge retorna **`202 Accepted` + `{job_id, status_url}`** e
  continua processando em background.

### 6.2 Modelo de jobs (novo domínio `app/domains/jobs`)
Nova tabela `proxy_jobs`:
```
id (=job_id), correlation_id, account_id, api_id, key_id,
status (pending|running|done|failed|timeout),
request_snapshot (sanitizado), result_body, result_status_code,
error_code, created_at, completed_at, expires_at
```
- Worker assíncrono processa o forward (asyncio task / fila — começar com asyncio
  background task; migrar p/ Celery/RQ se volume exigir).
- **Entrega do resultado** (3 caminhos, cliente escolhe):
  - **Polling**: `GET /jobs/{id}` → status + resultado quando `done`.
  - **Webhook**: cliente registra `callback_url`; a Bridge faz POST ao concluir
    (com assinatura HMAC).
  - **SSE**: `GET /jobs/{id}/stream`.
- **Idempotência** (blind spot — §10): header `Idempotency-Key` evita reprocessar/
  recobrar a mesma consulta em retry.

### 6.3 Billing sob async (blind spot)
- Definir explicitamente *quando cobra*: hoje cobra só em `200` (`proxy/router.py`).
  Com job, cobrar em `done` com `result_status_code==200`; `timeout`/`failed` não
  cobram. Registrar `cost` no `proxy_jobs` e no `RequestMetric`.

---

## 7. Requisito transversal — Correlation ID ponta a ponta

É a espinha dorsal de "fácil achar problemas":
- A Bridge **já gera** `correlation_id` no `_dispatch` (`proxy/router.py`). Hoje só
  volta no header `x-correlation-id`.
- **Refatoração**: a Bridge passa o `correlation_id` para a API downstream via header
  (`X-Correlation-Id`). A `bridge-sdk/context` lê e injeta em **todo** log, chamada de
  proxy e captcha (via `contextvars`).
- Resultado: um único ID liga gateway log + app logs + proxy events + captcha events
  + job. O painel de debug (§2.3) é a junção por esse ID.

---

## 8. Requisito — Histórico de pesquisas p/ debug

- O `request_logs` (Mongo) já guarda req/resp; **estender retenção** para debug
  (config separada do TTL de 24h atual — ex: 7–30 dias) e/ou amostragem.
- **Replay**: endpoint admin `POST /logs/admin/{correlation_id}/replay` que
  reexecuta a consulta a partir do snapshot (útil p/ reproduzir bug). Reusa o
  caminho de `_dispatch`.
- **Mascaramento/PII** (blind spot — LGPD): já há masking de headers em
  `logs/service.py:12`; estender p/ campos sensíveis no body e definir política de
  retenção/expurgo do histórico.

---

## 9. Taxonomia de erros estruturados (`bridge-sdk/errors`)

Hoje erros viram `502`/`500` opacos. Padronizar `BridgeError` com `error_code`
estável que a API retorna e a Bridge propaga ao cliente e aos logs:

| error_code | significado | HTTP sugerido |
|---|---|---|
| `PROXY_AUTH_FAILED` | login do proxy falhou | 502 |
| `PROXY_UNAVAILABLE` | nenhum proxy do pool disponível | 503 |
| `CAPTCHA_FAILED` | solver não resolveu | 502 |
| `CAPTCHA_BALANCE_EXHAUSTED` | sem saldo no provedor | 503 |
| `TARGET_BLOCKED` | alvo bloqueou (ex: 403/captcha wall) | 502 |
| `TARGET_TIMEOUT` | alvo não respondeu no tempo | 504 |
| `INVALID_QUERY` | parâmetros da consulta inválidos | 400 |

A Bridge mapeia `error_code` → status + mensagem clara (estende o tratamento em
`proxy/router.py` que hoje cobre `InvalidKeyError`, `RateLimitExceededError`, etc).

---

## 10. O que você não está enxergando (blind spots)

1. **Correlation ID propagado à downstream** (§7) — sem isso, "logs fáceis de buscar"
   não acontece; os logos da app ficam desconectados do gateway.
2. **Liveness vs readiness** (§3.1) — uma API pode estar "no ar" mas incapaz de
   atender (proxy caído, captcha sem saldo). Precisa dos dois.
3. **Saldo do captcha** (§5.2) — solvers ficam sem crédito silenciosamente; é causa
   comum de "parou de funcionar" sem erro claro.
4. **Idempotência** (§6.2) — com requests longas + retries + async, sem chave de
   idempotência você reprocessa e recobra a mesma consulta.
5. **Billing sob async/erros** (§6.3) — definir o momento exato da cobrança.
6. **Esgotamento de workers** — requests síncronas de minutos seguram workers; o modo
   híbrido (§6) e timeouts configuráveis mitigam, mas dimensione concorrência.
7. **Segredos em repouso** — credenciais de proxy/captcha criptografadas (reusar a
   cripto de `master_key_encrypted`).
8. **Service token ≠ chave de cliente** (§2.2) — a API autentica na ingestão com um
   token de serviço próprio, não com chave de cliente.
9. **Versão da SDK reportada** (§3.1) — para saber quais APIs estão no contrato novo.
10. **Retenção/PII do histórico** (§8) — LGPD, masking de body, expurgo.
11. **Config sem deploy** — troca de proxy/captcha deve refletir sem redeploy da API
    (SDK lê config do pool da plataforma com cache curto).
12. **Alertas proativos** (§3.2) — hoje tudo é pull; pelo menos registrar eventos de
    transição `healthy→degraded→down`.

---

## Arquivos / módulos a criar ou alterar

**Plataforma (backend) — novos domínios** (seguir o padrão
`models/schemas/service/router` já usado em `app/domains/*`):
- `app/domains/proxies/` (§4) + migration `proxies`, `proxy_pools`, `proxy_pool_members`
- `app/domains/captcha/` (§5) + migration `captcha_providers`
- `app/domains/jobs/` (§6) + migration `proxy_jobs`
- `app/domains/ingest/` (§2.2) — `POST /ingest/logs`, `POST /ingest/status`
- `app/domains/status/` (§3.2) — coletor + `GET /status/overview`, `/status/stream`

**Alterações em código existente:**
- `app/domains/proxy/router.py` — timeout configurável; fork síncrono/job (§6.1);
  propagar `X-Correlation-Id` à upstream (§7); mapear `error_code` (§9).
- `app/domains/proxy/service.py` — `build_upstream_headers` injeta correlation id.
- `app/core/config.py` — `sync_timeout_s`, `app_log_retention_days`,
  `captcha_balance_threshold`, etc.
- `app/domains/logs/service.py` — coleção `app_logs` + busca por `correlation_id`;
  estender masking de body (§8).
- `app/domains/apis/models.py` — `proxy_pool_id`, `captcha_provider_id`,
  `service_token` (ou tabela à parte).

**Frontend (admin)** — novas telas seguindo o padrão de
`frontend/src/app/admin/*` + funções em `frontend/src/lib/api.ts`:
- `/admin/proxies`, `/admin/captcha`, `/admin/status` (tempo real via SSE),
  `/admin/debug` (timeline por correlation_id), `/admin/jobs`.

**SDK** — repositório/pacote `bridge-sdk` separado (§1), versionado, adotado por
cada API downstream na refatoração.

---

## Ordem sugerida (fases)

1. **Fundação de observabilidade**: `bridge-sdk/context` + propagação do
   correlation_id (§7) + ingestão de logs (§2) + vista unificada por ID (§2.3).
   *Entrega valor imediato de debug.*
2. **Health & status** (§3) + tela `/admin/status`.
3. **Proxy** (§4) — modelo, SDK client, tela, failover.
4. **Captcha** (§5) — espelha o proxy, + saldo.
5. **Execução híbrida/jobs** (§6) + timeout configurável + idempotência + billing.
6. **Histórico/replay** (§8) + alertas (§3.2).

Cada fase é independente o suficiente para entregar isolada; a fase 1 é pré-requisito
das demais (todo o resto se ancora no correlation_id).

---

## Verification

Como este documento é a base para a refatoração (não um patch único), a verificação
é por fase, mas os critérios end-to-end são:
- **Logs**: disparar uma consulta de ponta a ponta e recuperar a **timeline completa**
  por `correlation_id` (gateway + app + proxy + captcha) em `/admin/debug`.
- **Status**: derrubar um proxy / zerar saldo de captcha de teste e ver a API virar
  `degraded`/`down` no `/admin/status` em tempo real (SSE), com erro claro.
- **Híbrido**: simular upstream lenta (>90s) e confirmar `202 + job_id`, depois
  resultado via polling, webhook e SSE; confirmar cobrança só em `done/200`.
- **Failover**: marcar proxy primário como `failing` e confirmar uso automático do
  próximo do pool, com log `proxy.failed`.
- **Idempotência**: repetir request com mesmo `Idempotency-Key` e confirmar que não
  reprocessa nem recobra.
- **Testes**: seguir o padrão atual `backend/tests/unit/` (ver
  `tests/unit/test_proxy_router.py`); rodar via Docker do usuário (não usar
  py_compile — ver memória do ambiente).
