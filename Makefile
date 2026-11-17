# The Garage · Ideas — developer commands. Synthetic data only.
# Every target is safe to run more than once.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Per-checkout settings read from `.env`, so a second stack in a worktree can run beside the first (BLD-200).
# A value already in the shell environment wins. Defaults are the first stack's.
env_get = $(shell sed -n 's/^$(1)=//p' .env 2>/dev/null | tail -1 | sed 's/[[:space:]]*\#.*//')
COMPOSE_PROJECT_NAME ?= $(or $(call env_get,COMPOSE_PROJECT_NAME),kfin-ideas)
POSTGRES_PORT        ?= $(or $(call env_get,POSTGRES_PORT),5432)
E2E_BASE_URL         ?= $(or $(call env_get,E2E_BASE_URL),http://localhost:3000)
OIDC_ISSUER          ?= $(or $(call env_get,OIDC_ISSUER),http://localhost:8090/default)
STACK_UP_FLAGS       ?= $(call env_get,STACK_UP_FLAGS)

COMPOSE := docker compose -p $(COMPOSE_PROJECT_NAME) -f infra/docker-compose.yml --project-directory . --env-file .env
PY      := cd services/worker && uv run --frozen
WEB     := cd apps/web &&

.PHONY: help setup build up down health migrate db-users seed demo demo-reset demo-remove test test-py test-web e2e eval lint lint-py lint-web lint-ci verify db-types killswitch clean-data uat-deploy uat-rehearsal

help: ## List the commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-12s %s\n", $$1, $$2}'

.env:
	cp .env.example .env

setup: .env ## Install Python and Node dependencies on this machine
	cd services/worker && uv sync --frozen
	$(WEB) npm ci
	$(WEB) npx playwright install chromium

build: .env ## Build the worker and web images
	$(COMPOSE) build

up: .env ## Start the local stack and wait until every service is healthy
	@mkdir -p .data  # made by this user, not by Docker as root, so host-side seed and tests can write to it (Linux)
	$(COMPOSE) up -d --wait --wait-timeout 120 postgres
	$(COMPOSE) run --rm dbmate up
	$(MAKE) --no-print-directory db-users
	$(COMPOSE) up -d --build --wait --wait-timeout 180 $(STACK_UP_FLAGS)
	@docker image prune -f --filter label=org.kfin.project=kfin-ideas --filter until=6h >/dev/null  # old builds only (BLD-105, BLD-225)
	@$(COMPOSE) exec -T postgres df -P /var/lib/postgresql/data 2>/dev/null | awk 'NR == 2 { u = $$5 + 0; if (u >= 80) printf "Warning: the Docker disk is %d%% full. Builds fail when it fills; see BLD-225.\n", u }' || true
	$(PY) python -m core.health --timeout 120

down: ## Stop the local stack (data volumes are kept)
	$(COMPOSE) down

health: ## Check every service health endpoint
	$(PY) python -m core.health --timeout 120

migrate: .env ## Apply database migrations (dbmate); a second run changes nothing
	$(COMPOSE) run --rm dbmate up
	$(MAKE) --no-print-directory db-users

db-users: ## Dev only: login users for the web and worker roles (UAT/prod: ops, from the vault)
	$(COMPOSE) exec -T postgres psql -q -v ON_ERROR_STOP=1 -U ideas -d ideas < infra/dev/db-users.sql

seed: migrate ## Create the local company repo, validate it, index it, load synthetic users
	$(PY) python -m bootstrap.seed

# DEMO_SET=1pc picks the 1% Club seed for the handoff's tables (bootstrap/club_seed.py) instead of the old demo.
DEMO_SET ?= 1pc

demo: ## Dev only: load the synthetic demo (docs/DEMO.md; DEMO_SET=1pc for the 1% Club seed); a second run changes nothing
	$(PY) python -m bootstrap.demo --set $(DEMO_SET)

demo-reset: ## Dev only: remove the demo (and, for the old one, every One in the local database), then load it again
	$(PY) python -m bootstrap.demo --set $(DEMO_SET) --reset

demo-remove: ## Dev only: remove the demo without loading it again; run before e2e on this stack (BLD-154)
	$(PY) python -m bootstrap.demo --set $(DEMO_SET) --remove

test: up migrate test-py test-web ## Unit and integration tests

test-py:
	$(PY) pytest -q

test-web:
	$(WEB) npx vitest run

e2e: up seed ## Playwright end-to-end and accessibility checks (signs in as the seeded personas)
	$(PY) python -m bootstrap.demo --set 1pc
	$(WEB) E2E_BASE_URL="$(E2E_BASE_URL)" OIDC_ISSUER="$(OIDC_ISSUER)" \
		E2E_DATABASE_URL="postgres://ideas:ideas@localhost:$(POSTGRES_PORT)/ideas?sslmode=disable" npx playwright test

eval: up ## Golden sets for every agent (model gates enforced on a real route only, BLD-076)
	$(PY) python -m evalrunner

lint: lint-py lint-web lint-ci ## Linters, OKF validator, no-SDK rule, log scrubber

lint-py:
	$(PY) ruff check .
	$(PY) ruff format --check .
	$(PY) mypy .

lint-web:
	$(WEB) npx eslint .
	$(WEB) npx prettier --check .
	$(WEB) npx tsc --noEmit

lint-ci:
	$(PY) python -m okf.validate ../../seed/company-repo
	$(PY) python ../../scripts/ci/check_no_model_sdk.py ../..
	$(PY) python ../../scripts/ci/check_decision_ids.py ../../docs/DECISIONS.md
	$(PY) pytest -q tests/test_log_scrubber.py

verify: up seed lint test e2e eval ## Every gate a block must pass, in one go (use on the test Mac)
	@echo "verify: all gates passed"

db-types: ## Regenerate Kysely types from the migrated dev database
	$(WEB) npx kysely-codegen --dialect postgres --url "postgres://ideas:ideas@localhost:$(POSTGRES_PORT)/ideas" --out-file src/server/db-types.ts --exclude-pattern "public.schema_migrations"

killswitch: ## Flip a kill switch: make killswitch NAME=submissions STATE=off REASON="…" ACTOR=REV-0001
	$(PY) python -m core.killswitch set "$(NAME)" "$(STATE)" --reason "$(REASON)" --actor "$(ACTOR)"

clean-data: ## Delete the local company repo (not the database)
	rm -rf .data/kfin-ideas

uat-deploy: ## UAT from a clean database: make uat-deploy APP_ENV_FILE=… DB_ENV_FILE=… (docs/UAT.md)
	scripts/uat/deploy.sh "$(APP_ENV_FILE)" "$(DB_ENV_FILE)"

uat-rehearsal: ## Rehearse the UAT deploy here with throwaway secrets, then tear it down (pauses the dev stack)
	scripts/uat/rehearse.sh
