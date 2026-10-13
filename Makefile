# RecallRadar developer commands. Run `make help` for the list.
SHELL := /bin/bash
.DEFAULT_GOAL := help

WEB := pnpm --dir apps/web
UNAME := $(shell uname -s)

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "} {printf "  \033[33m%-14s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install Python (uv) and web (pnpm) dependencies
	uv sync --all-packages
ifeq ($(UNAME),Darwin)
	@# macOS can flag venv files "hidden" (e.g. iCloud-synced folders), and Python skips hidden .pth files.
	@chflags -R nohidden .venv
endif
	$(WEB) install --frozen-lockfile

.PHONY: up
up: ## Start Postgres, Mailpit, and the API (docker compose)
	docker compose up -d --build --wait

.PHONY: down
down: ## Stop the compose stack (data is kept)
	docker compose down

.PHONY: migrate
migrate: ## Apply database migrations to DATABASE_URL (default: local compose db)
	uv run alembic -c packages/core/alembic.ini upgrade head

.PHONY: api
api: ## Run the API on the host with reload (needs `make up` for the db)
	uv run uvicorn recallradar_api.main:create_app --factory --reload --port 8000

.PHONY: web
web: ## Run the web app dev server on http://localhost:3000
	$(WEB) dev

.PHONY: lint
lint: ## Lint and format-check everything
	uv run ruff check .
	uv run ruff format --check .
	$(WEB) lint
	$(WEB) format:check

.PHONY: format
format: ## Auto-format everything
	uv run ruff check --fix .
	uv run ruff format .
	$(WEB) format

.PHONY: typecheck
typecheck: ## mypy --strict and tsc
	uv run mypy .
	$(WEB) typecheck

.PHONY: test
test: ## Python tests (DB tests need `make up`) and web unit tests
	uv run pytest
	$(WEB) test

.PHONY: e2e
e2e: ## Build the web app and run Playwright (desktop, mobile, reduced motion)
	$(WEB) build
	$(WEB) e2e

.PHONY: openapi
openapi: ## Regenerate the API schema and the web app's TypeScript types
	uv run recallradar-openapi apps/web/src/lib/api/openapi.json
	$(WEB) gen:api

.PHONY: check
check: lint typecheck test ## Everything CI runs except e2e

.PHONY: eval
eval: ## Matching-engine evaluation (arrives in M3)
	@echo "make eval: the labelled evaluation set and script arrive in Milestone 3 (SPEC §6.9)." && exit 1
