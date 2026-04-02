# Plano de Desenvolvimento — Bridge API
## TDD + XP (Extreme Programming)

---

## Decisões Confirmadas

| Decisão | Escolha |
|---|---|
| Execução das iterações | Uma por uma (aprovação entre cada iteração) |
| Ordem backend/frontend | Backend completo primeiro, depois Next.js |
| Stack de bancos | PostgreSQL + MongoDB + Redis (conforme planejamento) |

---

## Contexto

O projeto Bridge API é um gateway/proxy centralizado para gerenciamento de APIs de terceiros. Atualmente o repositório contém apenas o documento de planejamento (`PLANEJAMENTO_BRIDGE_API.md`). O objetivo deste plano é guiar o desenvolvimento do zero com **TDD (Test-Driven Development)** e práticas de **XP (Extreme Programming)**, garantindo qualidade, confiabilidade e entregas incrementais funcionais.

---

## Princípios XP Adotados

| Prática XP | Aplicação |
|---|---|
| **TDD** | Todo código de produção nasce de um teste falhando |
| **Small Releases** | Cada iteração entrega valor funcional |
| **Simple Design** | Menor complexidade que atenda o requisito |
| **Refactoring** | Ao final de cada ciclo red→green→refactor |
| **Continuous Integration** | GitHub Actions rodando testes a cada push |
| **Collective Ownership** | Padrões de código definidos e documentados |
| **Coding Standards** | Linting (ruff, black, ESLint) desde o dia 1 |
| **User Stories** | Cada feature descrita como história de usuário |

---

## Ciclo TDD por Feature

```
1. Escrever teste falhando (RED)
2. Escrever código mínimo para passar (GREEN)
3. Refatorar mantendo testes verdes (REFACTOR)
4. Commit + Push → CI valida
```

---

## Stack Técnica

**Backend:** FastAPI + SQLAlchemy (async) + Alembic + Pydantic + httpx  
**Frontend:** Next.js + React + TypeScript  
**Bancos:** PostgreSQL (transacional) · MongoDB (logs) · Redis (cache/rate limit/sessão)  
**Testes Backend:** pytest + pytest-asyncio + httpx (TestClient) + factory-boy + pytest-cov  
**Testes Frontend:** Jest + React Testing Library + MSW (mock service worker)  
**CI/CD:** GitHub Actions  
**Infra Local:** Docker Compose (postgres + mongo + redis)

---

## Estrutura de Diretórios Alvo

```
bridgeAPI/
├── backend/
│   ├── app/
│   │   ├── core/          # config, security, database
│   │   ├── domains/
│   │   │   ├── auth/
│   │   │   ├── clients/
│   │   │   ├── apis/
│   │   │   ├── keys/
│   │   │   ├── proxy/
│   │   │   ├── metrics/
│   │   │   └── logs/
│   │   └── main.py
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   ├── alembic/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/           # Next.js App Router
│   │   ├── components/
│   │   └── lib/
│   ├── __tests__/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── .github/
    └── workflows/
        └── ci.yml
```

---

## Iterações de Desenvolvimento

### ITERAÇÃO 0 — Bootstrap e Infraestrutura
**Objetivo:** Repositório funcional com CI rodando testes vazios

**Tarefas:**
- [ ] Criar `docker-compose.yml` com PostgreSQL, MongoDB, Redis
- [ ] Inicializar projeto FastAPI com `pyproject.toml` (ruff, black, pytest, pytest-cov)
- [ ] Inicializar projeto Next.js com TypeScript + ESLint + Jest
- [ ] Configurar GitHub Actions: lint + test backend + test frontend
- [ ] Criar `.env.example` com todas as variáveis necessárias
- [ ] Primeiro teste de saúde: `GET /health` → `{"status": "ok"}`

**TDD do Health Check:**
```python
# RED: test_health.py
def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

---

### ITERAÇÃO 1 — Autenticação de Administrador
**User Stories:**
- `US-01`: Como admin, quero fazer login com email/senha e receber um JWT para acessar o sistema
- `US-02`: Como admin, quero que rotas protegidas retornem 401 sem token válido

**Modelos:** `User` (id, email, password_hash, role, created_at)

**Testes TDD obrigatórios:**
```python
# Unitários
test_password_hash_is_not_plain_text()
test_valid_credentials_return_jwt()
test_invalid_password_returns_401()
test_unknown_email_returns_401()
test_expired_token_returns_401()
test_protected_route_without_token_returns_401()
test_protected_route_with_valid_token_returns_200()
```

**Arquivos críticos:** `backend/app/domains/auth/`

---

### ITERAÇÃO 2 — Gestão de Clientes (Admin)
**User Stories:**
- `US-03`: Como admin, quero registrar um cliente (org) que aguarda aprovação
- `US-04`: Como admin, quero aprovar ou rejeitar um cliente pendente
- `US-05`: Como cliente, quero me registrar e aguardar aprovação

**Modelos:** `Client` (id, name, email, status: pending/active/rejected, created_at)

**Testes TDD obrigatórios:**
```python
test_admin_can_create_client_with_pending_status()
test_admin_can_approve_pending_client()
test_admin_can_reject_pending_client()
test_cannot_approve_already_active_client()
test_client_cannot_login_while_pending()
test_client_can_login_after_approval()
test_list_clients_returns_paginated_results()
```

---

### ITERAÇÃO 3 — Catálogo de APIs (Admin)
**User Stories:**
- `US-06`: Como admin, quero registrar uma API externa com seus metadados e master key
- `US-07`: Como admin, quero registrar endpoints de uma API
- `US-08`: Como admin, quero ativar/desativar uma API

**Modelos:** `API` (id, name, base_url, master_key_encrypted, auth_type, status, ...) · `Endpoint` (id, api_id, method, path, status, cost_rule, ...)

**Testes TDD obrigatórios:**
```python
test_admin_can_register_api()
test_master_key_is_stored_encrypted()
test_admin_can_add_endpoint_to_api()
test_admin_can_disable_api()
test_disabled_api_still_visible_with_status_indicator()
test_duplicate_api_name_returns_409()
test_endpoint_with_invalid_http_method_returns_422()
```

---

### ITERAÇÃO 4 — Chaves de API (Cliente)
**User Stories:**
- `US-09`: Como cliente aprovado, quero criar uma API key com nome amigável
- `US-10`: Como cliente, quero revogar uma API key
- `US-11`: Como cliente, quero listar minhas API keys e seus status

**Modelos:** `APIKey` (id, client_id, name, key_prefix, key_secret_hash, status, created_at)

**Testes TDD obrigatórios:**
```python
test_client_can_create_api_key()
test_api_key_secret_shown_only_at_creation()
test_api_key_secret_is_hashed_in_db()
test_client_can_revoke_own_key()
test_revoked_key_cannot_be_used()
test_client_cannot_access_other_clients_keys()
test_key_has_unique_prefix_and_secret()
```

---

### ITERAÇÃO 5 — Permissões de Acesso (Admin)
**User Stories:**
- `US-12`: Como admin, quero autorizar um cliente a usar uma API específica
- `US-13`: Como admin, quero revogar o acesso de um cliente a uma API
- `US-14`: Como cliente, quero ver quais APIs tenho acesso no meu catálogo

**Modelos:** `Permission` (id, client_id, api_id, granted_at, revoked_at)

**Testes TDD obrigatórios:**
```python
test_admin_can_grant_api_access_to_client()
test_admin_can_revoke_api_access()
test_client_sees_only_authorized_apis_in_catalog()
test_duplicate_permission_returns_409()
test_revoked_permission_hides_api_from_catalog()
```

---

### ITERAÇÃO 6 — Proxy/Bridge Core ⭐ (Mais Crítica)
**User Stories:**
- `US-15`: Como cliente, quero fazer uma chamada via Bridge usando minha API key e o Bridge encaminhar para a API upstream
- `US-16`: Como sistema, preciso validar: key válida → cliente ativo → API ativa → permissão existe → rate limit não excedido
- `US-17`: Como sistema, preciso registrar métricas de cada request

**Fluxo:** `Request → validate_key → validate_permission → check_rate_limit → forward_upstream → record_metrics → return_response`

**Testes TDD obrigatórios:**
```python
# Validações (com mocks para upstream)
test_request_with_invalid_key_returns_401()
test_request_with_revoked_key_returns_401()
test_request_with_inactive_client_returns_403()
test_request_to_disabled_api_returns_503()
test_request_without_permission_returns_403()
test_request_exceeding_rate_limit_returns_429()

# Forwarding
test_valid_request_is_forwarded_to_upstream()
test_upstream_headers_are_injected_with_master_key()
test_upstream_response_is_returned_transparently()
test_upstream_timeout_returns_504()
test_upstream_500_is_forwarded_as_502()

# Métricas
test_successful_request_creates_metric_record()
test_metric_includes_latency_status_and_cost()
test_rate_limited_request_is_not_billed()
test_error_request_is_not_billed()
```

**Nota:** Usar `httpx.MockTransport` para simular upstream nos testes unitários. Testes de integração usam um servidor upstream fake.

---

### ITERAÇÃO 7 — Rate Limiting
**User Stories:**
- `US-18`: Como admin, quero configurar limite de requisições por chave (ex: 100 req/min)
- `US-19`: Como sistema, preciso bloquear e retornar 429 quando limite excedido

**Implementação:** Sliding window com Redis (contador por `key_id:minute_bucket`)

**Testes TDD obrigatórios:**
```python
test_requests_within_limit_are_allowed()
test_request_exceeding_limit_returns_429()
test_rate_limit_resets_after_window()
test_rate_limit_is_per_key_not_per_client()
test_redis_unavailable_falls_back_gracefully()
```

---

### ITERAÇÃO 8 — Logs e Observabilidade
**User Stories:**
- `US-20`: Como cliente, quero ver logs das minhas requisições para debug
- `US-21`: Como sistema, preciso mascarar dados sensíveis antes de persistir logs

**Armazenamento:** MongoDB (logs raw) + correlation_id por request

**Testes TDD obrigatórios:**
```python
test_each_request_gets_unique_correlation_id()
test_log_stores_request_and_response()
test_sensitive_headers_are_masked_in_logs()
test_api_key_value_never_appears_in_logs()
test_client_sees_only_own_logs()
test_logs_respect_retention_policy()
```

---

### ITERAÇÃO 9 — Métricas e Dashboard
**User Stories:**
- `US-22`: Como cliente, quero ver dashboard com total de requests, taxa de erro, latência média e custo por período
- `US-23`: Como admin, quero ver métricas globais de todas as APIs

**Testes TDD obrigatórios:**
```python
test_dashboard_returns_correct_total_requests()
test_error_rate_calculated_correctly()
test_average_latency_calculated_correctly()
test_cost_aggregation_by_key_and_api()
test_billable_vs_non_billable_counts()
test_metrics_filtered_by_date_range()
```

---

### ITERAÇÃO 10 — Frontend (Next.js)
**Sequência por prioridade:**
1. Login admin + client (com testes React Testing Library)
2. Admin: gestão de clientes, APIs, permissões
3. Cliente: catálogo de APIs, gestão de keys
4. Dashboard de métricas e logs

**Testes Frontend obrigatórios por componente:**
```typescript
// Exemplo padrão para cada página/componente
test('renders login form', ...)
test('shows error on invalid credentials', ...)
test('redirects to dashboard on success', ...)
test('API calls use MSW mocks', ...)
```

---

## Estratégia de Testes por Camada

| Camada | Ferramenta | Cobertura Alvo |
|---|---|---|
| Unitários (backend) | pytest + mocks | 90%+ |
| Integração (backend) | pytest + TestClient + DB real | rotas críticas |
| E2E (proxy flow) | pytest + servidor fake upstream | fluxo completo |
| Frontend unitário | Jest + RTL | componentes UI |
| Frontend integração | MSW + RTL | fluxos de página |

---

## CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/ci.yml — por branch e PR
jobs:
  backend:
    - lint (ruff + black --check)
    - test (pytest --cov --cov-fail-under=80)
  frontend:
    - lint (eslint)
    - test (jest --coverage)
  integration:
    - docker-compose up (postgres + mongo + redis)
    - pytest tests/integration/
```

---

## Arquivos Críticos a Criar

| Arquivo | Iteração |
|---|---|
| `docker-compose.yml` | 0 |
| `backend/pyproject.toml` | 0 |
| `backend/app/core/config.py` | 0 |
| `backend/app/core/database.py` | 0 |
| `backend/app/domains/auth/` | 1 |
| `backend/app/domains/clients/` | 2 |
| `backend/app/domains/apis/` | 3 |
| `backend/app/domains/keys/` | 4 |
| `backend/app/domains/proxy/` | 6 |
| `backend/app/domains/metrics/` | 7-8 |
| `frontend/src/app/` | 10 |
| `.github/workflows/ci.yml` | 0 |

---

## Verificação por Iteração

Ao final de cada iteração:
1. `pytest --cov` → cobertura ≥ 80% no domínio da iteração
2. Todos os testes verdes
3. `ruff check` e `black --check` passam
4. CI/CD verde no GitHub Actions
5. `docker-compose up` + smoke test manual do fluxo da iteração
