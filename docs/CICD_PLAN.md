# Plano de CI/CD — Bridge API

Documento de planejamento para o pipeline de CI/CD, focado em TDD + XP com
deploy automatizado via Docker Compose em VPS própria.

---

## 1. O modelo (padrão da indústria)

Três camadas bem separadas, cada uma pegando o que a anterior deixou passar.

```
┌─────────────────────────────────────────────────────────┐
│ CAMADA 1: LOCAL (desenvolvimento)                       │
│ - docker compose up → infra local idêntica à produção   │
│ - Makefile com comandos padronizados                    │
│ - pytest-watch → red/green automático (TDD)             │
│ - pre-commit → bloqueia commit se lint/unit quebrar     │
├─────────────────────────────────────────────────────────┤
│ CAMADA 2: CI (GitHub Actions, em todo PR)               │
│ - lint + unit + integration (serviços como containers)  │
│ - build da imagem Docker, push pra GHCR (SHA + branch)  │
│ - gate: merge bloqueado se falhar                       │
├─────────────────────────────────────────────────────────┤
│ CAMADA 3: CD (GitHub Actions, em merge)                 │
│ - staging: auto no merge → staging                      │
│ - prod: auto no merge → main (com approval opcional)    │
│ - SSH na VPS, docker compose pull, migrations, up -d    │
│ - health check pós-deploy, rollback automático          │
└─────────────────────────────────────────────────────────┘
```

### Modelo de branches

```
feature/xxx  ──PR──▶  staging  ──PR──▶  main (prod)
     │                   │                 │
     │                   │                 └─ CI + deploy produção
     │                   └─ CI + deploy staging
     └─ CI (testes) roda no PR, bloqueia merge se quebrar
```

- `feature/xxx` → PR para `staging`: CI roda (lint + unit + integration). Só faz merge se verde.
- merge em `staging` → deploy automático no ambiente staging.
- testa manualmente no staging → PR de `staging` para `main`.
- merge em `main` → deploy automático em produção.

---

## 2. Por que este é o modelo certo

- **Mesma imagem Docker do build até prod**: o container que passou nos testes é
  exatamente o que roda em produção. Nada de "funciona na minha máquina".
- **GHCR como fonte única de verdade de binários**: versionado por SHA do commit.
  Rollback = retag + redeploy.
- **Compose igual em todos os ambientes**: dev, staging, prod usam o mesmo
  `docker-compose.yml` com overrides (`.dev.yml`, `.staging.yml`, `.prod.yml`)
  para diferenças pontuais.
- **Migrations como serviço Compose**: `depends_on` garante que roda antes da
  app. Elimina a classe de bugs "deploy novo contra schema velho".

---

## 3. Como o Claude Code ajuda a achar problemas

O segredo é **paridade local/CI**. Tudo que o CI roda, você roda local com um
comando só. Quando o CI falha, você reproduz em segundos e o Claude investiga
junto.

Três mecanismos:

1. **`make ci`**: roda exatamente o mesmo que o GitHub Actions, localmente. Com
   as mesmas versões de Docker, Python, Node.
2. **Logs estruturados em arquivo**: `logs/pytest.log`, `logs/ci.log`,
   `logs/deploy.log`. O Claude lê esses arquivos com a Read tool e analisa
   direto.
3. **`pytest --tb=short --log-file=logs/pytest.log`**: falha em formato
   consumível. Quando algo quebra, cola o log ou só diz "quebrou, olha o log".

---

## 4. Artefatos finais

```
bridgeAPI/
├── Makefile                              # comandos únicos
├── .pre-commit-config.yaml               # gate local
├── docker-compose.yml                    # base (dev)
├── docker-compose.prod.yml               # overrides prod
├── docker-compose.staging.yml            # overrides staging
├── backend/
│   └── Dockerfile                        # multi-stage, prod-ready
├── frontend/
│   └── Dockerfile                        # multi-stage
├── .github/
│   └── workflows/
│       ├── ci.yml                        # lint + test + build
│       └── cd.yml                        # deploy staging/prod
└── docs/
    ├── CICD_PLAN.md                      # este arquivo
    ├── INFRA.md                          # como a infra está montada
    ├── DEPLOY.md                         # playbook de migração
    └── LOCAL_DEV.md                      # como desenvolver local
```

### Makefile — coração do dia-a-dia

```makefile
# Local dev
make up              # sobe infra local (postgres, mongo, redis)
make down            # derruba tudo
make test            # roda unit tests (rápido, <10s)
make test-watch      # TDD mode: rerun on file change
make test-all        # unit + integration (~1min)
make lint            # ruff + black + eslint
make lint-fix        # auto-fix

# Paridade com CI
make ci              # replica 100% o que o GitHub Actions roda
make ci-backend      # só backend (mais rápido)

# Deploy manual (emergência)
make deploy-staging  # SSH + pull + up
make deploy-prod     # idem para prod, com confirmação

# Utilidades
make logs-staging    # stream logs da VPS via SSH
make shell-staging   # bash dentro do container de staging
make db-backup-prod  # backup manual do DB
```

Um comando por coisa. Se esquecer, `make help` lista tudo.

---

## 5. Plano de execução — 4 etapas

### Etapa A: fundação local (2-3h, sem tocar em VPS)
- Dockerfile para backend e frontend
- `docker-compose.yml` com overrides por ambiente
- Makefile com todos os targets
- `.pre-commit-config.yaml`
- `docs/LOCAL_DEV.md`

### Etapa B: CI rigoroso (1-2h)
- Reescrever `.github/workflows/ci.yml` (o atual tem bugs de env vars)
- Build + push para GHCR
- Branch protection no GitHub (main e staging exigem PR aprovado + CI verde)

### Etapa C: CD automatizado (meio dia)
- `.github/workflows/cd.yml`: deploy no merge
- Script de deploy idempotente no VPS (`deploy.sh`)
- Rollback automático via retag da imagem anterior
- Notificação Discord

### Etapa D: documentação + playbook (2h)
- `docs/INFRA.md` — estado final da infra
- `docs/DEPLOY.md` — como recuperar/migrar tudo do zero

---

## 6. Infraestrutura-alvo

### Configuração declarada pelo usuário
- VPS própria (self-hosted)
- Docker Compose como unidade de deploy (para portabilidade em migrações)
- Nginx em VPS separada (atua como reverse proxy / ponto de entrada)
- VPS de staging e prod separadas (a serem provisionadas)
- Bancos em VPS dedicadas (tanto staging quanto prod)
- Backend e frontend em containers separados na mesma VPS de aplicação
- Downtime zero **não é requisito** — aceita janela de 5-10s no deploy

### Arquitetura resultante

```
GitHub (código + CI/CD)
  │
  │ SSH (secrets do GitHub Actions)
  ▼
┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ VPS NGINX   │────▶│ VPS APP staging │────▶│ VPS DB staging  │
│ (LB / SSL)  │     │ docker compose: │     │ postgres/mongo/ │
│             │     │  - backend      │     │ redis           │
│             │     │  - frontend     │     │ + cron backup   │
│             │     │  - migrator     │     └─────────────────┘
│             │     └─────────────────┘
│             │     ┌─────────────────┐     ┌─────────────────┐
│             │────▶│ VPS APP prod    │────▶│ VPS DB prod     │
│             │     │ docker compose: │     │ postgres/mongo/ │
│             │     │  - backend      │     │ redis           │
│             │     │  - frontend     │     │ + cron backup   │
│             │     │  - migrator     │     └─────────────────┘
│             │     └─────────────────┘
└─────────────┘
```

---

## 7. Decisões pendentes (3 perguntas)

Antes de iniciar a Etapa A:

1. **Pré-commit bloqueia só unit tests** (rápido, ~10s) **ou unit + integration**
   (~1min, exige Docker up)?
   - **Recomendação**: unit apenas no pre-commit, integration no pre-push.

2. **Frontend Next.js em produção: SSR ou estático?**
   - SSR → precisa de `next start` em container Node (~200MB RAM).
   - Estático → `next build && next export`, Nginx serve direto (praticamente
     zero RAM, mas perde SSR e rotas autenticadas server-side).

3. **Deploy para produção: automático no merge para `main`, ou manual com
   aprovação?**
   - Automático: mais ágil, mais risco de deploy acidental.
   - **Recomendação**: manual com aprovação (feature grátis do GitHub
     Environments — evita deploy acidental em horários críticos).

---


## 8. Ordem recomendada de execução

1. **Etapa A** (local) — independente de VPS. Começa imediatamente.
2. **Etapa B** (CI) — depende só do repositório GitHub.
3. **Provisionar VPS** (staging e prod) — em paralelo com B, mas antes de C.
4. **Etapa C** (CD) — precisa das VPS prontas.
5. **Etapa D** (docs) — ao final, documenta o que ficou em pé.

A Etapa A sozinha já entrega **80% do valor de TDD seguro**: pre-commit impede
commit de código quebrado, Makefile padroniza comandos, Dockerfiles garantem
paridade local/prod.
