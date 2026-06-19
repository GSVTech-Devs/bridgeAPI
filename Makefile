## Bridge API — Makefile
## Usage: make <target>   |   make help

COMPOSE       := docker compose

.DEFAULT_GOAL := help
.PHONY: help up down stack-up stack-down \
        test test-watch test-all \
        lint lint-fix

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

# ── Help ───────────────────────────────────────────────────────────────────

help: ## List all available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
