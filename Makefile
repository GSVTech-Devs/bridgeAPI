## Bridge API — Makefile
## Usage: make <target>   |   make help

COMPOSE       := docker compose
COMPOSE_PROD  := docker compose -f docker-compose.yml -f docker-compose.prod.yml
COMPOSE_STG   := docker compose -f docker-compose.yml -f docker-compose.staging.yml

# Override via environment or CLI: make deploy-staging VPS_STAGING_HOST=1.2.3.4
VPS_STAGING_USER ?= deploy
VPS_STAGING_HOST ?=
VPS_PROD_USER    ?= deploy
VPS_PROD_HOST    ?=

.DEFAULT_GOAL := help
.PHONY: help up down stack-up stack-down \
        test test-watch test-all \
        lint lint-fix \
        ci ci-backend \
        deploy-staging deploy-prod \
        logs-staging logs-prod \
        shell-staging shell-prod \
        db-backup-prod

# ── Local dev ──────────────────────────────────────────────────────────────

up: ## Start local databases only (postgres, mongo, redis) — use when rodando backend/frontend fora do Docker
	$(COMPOSE) --profile db up -d

down: ## Stop all local containers and remove orphans
	$(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml --profile db --profile app down --remove-orphans

dev: ## Start full stack in Docker with hot-reload (recommended for development)
	$(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml --profile db --profile app up -d

dev-logs: ## Follow logs of all dev containers
	$(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml --profile db --profile app logs -f

stack-up: ## Start full stack with production build (to test before deploying)
	$(COMPOSE) --profile db --profile app up -d

stack-down: ## Stop full stack (production build)
	$(COMPOSE) --profile db --profile app down --remove-orphans

# ── Tests ──────────────────────────────────────────────────────────────────

test: ## Run unit tests only (fast, no Docker required)
	cd backend && pytest tests/unit/ -x -q --no-cov

test-watch: ## TDD mode: rerun unit tests on file change (requires: pip install pytest-watch)
	cd backend && ptw tests/unit/ -- -x -q --no-cov

test-all: ## Run unit + integration tests (requires: make up)
	cd backend && \
	  TEST_DATABASE_URL="postgresql+asyncpg://bridge:bridge@localhost:5433/bridgeapi_test" \
	  TEST_MONGO_URL="mongodb://bridge:bridge@localhost:27018/bridgelogs_test?authSource=admin" \
	  TEST_REDIS_URL="redis://:bridge@localhost:6380/1" \
	  pytest -v

test-migrations: ## Run only the migration lifecycle tests (requires: make up)
	cd backend && \
	  TEST_DATABASE_URL="postgresql+asyncpg://bridge:bridge@localhost:5433/bridgeapi_test" \
	  pytest tests/integration/test_migrations.py -v

test-e2e: ## Run Playwright E2E tests (auto-starts Next.js dev server)
	cd frontend && npm run test:e2e

test-e2e-headed: ## Run E2E tests in headed (visible) browser
	cd frontend && npm run test:e2e:headed

test-e2e-ui: ## Open Playwright UI mode
	cd frontend && npm run test:e2e:ui

# ── Lint ───────────────────────────────────────────────────────────────────

lint: ## Check code style — ruff + black (backend) + eslint (frontend)
	cd backend && ruff check . && black --check .
	cd frontend && npm run lint

lint-fix: ## Auto-fix code style
	cd backend && ruff check --fix . && black .
	cd frontend && npm run lint -- --fix

# ── CI parity ──────────────────────────────────────────────────────────────

ci: ci-backend ## Replicate full GitHub Actions CI locally (backend + frontend)
	cd frontend && npm ci --silent && npm run lint && npm test -- --coverage

ci-backend: ## Replicate backend CI only (lint + unit + integration)
	@$(MAKE) up
	@echo "Waiting for databases to be healthy..."
	@until $(COMPOSE) exec -T postgres pg_isready -U bridge > /dev/null 2>&1; do sleep 1; done
	@until $(COMPOSE) exec -T redis redis-cli -a bridge ping > /dev/null 2>&1; do sleep 1; done
	@until $(COMPOSE) exec -T mongo mongosh --eval "db.adminCommand('ping')" --quiet > /dev/null 2>&1; do sleep 1; done
	cd backend && \
	  pip install -e ".[dev]" -q && \
	  ruff check . && \
	  black --check . && \
	  pytest tests/unit/ -q && \
	  TEST_DATABASE_URL="postgresql+asyncpg://bridge:bridge@localhost:5433/bridgeapi_test" \
	  TEST_MONGO_URL="mongodb://bridge:bridge@localhost:27018/bridgelogs_test?authSource=admin" \
	  TEST_REDIS_URL="redis://:bridge@localhost:6380/1" \
	  pytest tests/integration/ -v

# ── Deploy manual (emergência) ─────────────────────────────────────────────

deploy-staging: ## Deploy to staging VPS via SSH (set VPS_STAGING_HOST and VPS_STAGING_USER)
	$(if $(VPS_STAGING_HOST),,$(error VPS_STAGING_HOST is not set))
	$(eval SHA := $(shell git rev-parse --short HEAD))
	$(eval REPO := $(shell git remote get-url origin | sed 's/.*github.com[:/]//' | sed 's/\.git$$//' | tr '[:upper:]' '[:lower:]'))
	ssh $(VPS_STAGING_USER)@$(VPS_STAGING_HOST) "\
	  cd /opt/bridge && \
	  export BACKEND_IMAGE=ghcr.io/$(REPO)-backend:$(SHA) && \
	  export FRONTEND_IMAGE=ghcr.io/$(REPO)-frontend:$(SHA) && \
	  docker compose -f docker-compose.yml -f docker-compose.staging.yml --profile app pull && \
	  docker compose -f docker-compose.yml -f docker-compose.staging.yml --profile app up -d && \
	  sleep 5 && curl -sf http://localhost:8000/health && echo 'Health check OK'"

deploy-prod: ## Deploy to production VPS via SSH (set VPS_PROD_HOST and VPS_PROD_USER)
	$(if $(VPS_PROD_HOST),,$(error VPS_PROD_HOST is not set))
	@echo "Deploying to PRODUCTION. Ctrl+C to abort."
	@sleep 3
	$(eval SHA := $(shell git rev-parse --short HEAD))
	$(eval REPO := $(shell git remote get-url origin | sed 's/.*github.com[:/]//' | sed 's/\.git$$//' | tr '[:upper:]' '[:lower:]'))
	ssh $(VPS_PROD_USER)@$(VPS_PROD_HOST) "\
	  cd /opt/bridge && \
	  export BACKEND_IMAGE=ghcr.io/$(REPO)-backend:$(SHA) && \
	  export FRONTEND_IMAGE=ghcr.io/$(REPO)-frontend:$(SHA) && \
	  docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app pull && \
	  docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app up -d && \
	  sleep 5 && curl -sf http://localhost:8000/health && echo 'Health check OK'"

# ── Utilities ──────────────────────────────────────────────────────────────

logs-staging: ## Stream backend logs from staging VPS
	$(if $(VPS_STAGING_HOST),,$(error VPS_STAGING_HOST is not set))
	ssh $(VPS_STAGING_USER)@$(VPS_STAGING_HOST) \
	  "docker logs -f bridge_backend"

logs-prod: ## Stream backend logs from production VPS
	$(if $(VPS_PROD_HOST),,$(error VPS_PROD_HOST is not set))
	ssh $(VPS_PROD_USER)@$(VPS_PROD_HOST) \
	  "docker logs -f bridge_backend"

shell-staging: ## Open a shell inside the staging backend container
	$(if $(VPS_STAGING_HOST),,$(error VPS_STAGING_HOST is not set))
	ssh -t $(VPS_STAGING_USER)@$(VPS_STAGING_HOST) \
	  "docker exec -it bridge_backend bash"

shell-prod: ## Open a shell inside the production backend container
	$(if $(VPS_PROD_HOST),,$(error VPS_PROD_HOST is not set))
	ssh -t $(VPS_PROD_USER)@$(VPS_PROD_HOST) \
	  "docker exec -it bridge_backend bash"

db-backup-prod: ## Dump Postgres from production to a local .sql.gz file
	$(if $(VPS_PROD_HOST),,$(error VPS_PROD_HOST is not set))
	ssh $(VPS_PROD_USER)@$(VPS_PROD_HOST) \
	  "docker exec bridge_postgres pg_dump -U bridge bridgeapi | gzip" \
	  > backup_prod_$(shell date +%Y%m%d_%H%M%S).sql.gz
	@echo "Backup saved."

# ── Help ───────────────────────────────────────────────────────────────────

help: ## List all available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
