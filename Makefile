# The Garage · Ideas — developer commands. Synthetic data only.
# Every target is safe to run more than once.

SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE := docker compose -f infra/docker-compose.yml --project-directory . --env-file .env
PY      := cd services/worker && uv run --frozen
WEB     := cd apps/web &&

.PHONY: help setup build up down health migrate seed test test-py test-web e2e eval lint lint-py lint-web lint-ci db-types killswitch clean-data

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
	$(COMPOSE) up -d --build --wait --wait-timeout 180
	$(PY) python -m core.health --timeout 120

down: ## Stop the local stack (data volumes are kept)
	$(COMPOSE) down

health: ## Check every service health endpoint
	$(PY) python -m core.health --timeout 120

migrate: .env ## Apply database migrations (dbmate); a second run changes nothing
	$(COMPOSE) run --rm dbmate up

seed: migrate ## Create the local company repo, validate it, index it, load synthetic users
	$(PY) python -m bootstrap.seed

test: up migrate test-py test-web ## Unit and integration tests

test-py:
	$(PY) pytest -q

test-web:
	$(WEB) npx vitest run

e2e: up ## Playwright end-to-end and accessibility checks
	$(WEB) npx playwright test

eval: ## Golden sets for every agent (harness only until B4)
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
	$(PY) pytest -q tests/test_log_scrubber.py

db-types: ## Regenerate Kysely types from the migrated dev database
	$(WEB) npx kysely-codegen --dialect postgres --url "postgres://ideas:ideas@localhost:5432/ideas" --out-file src/server/db-types.ts --exclude-pattern "public.schema_migrations"

killswitch: ## Flip a kill switch: make killswitch NAME=submissions STATE=off REASON="…" ACTOR=REV-0001
	$(PY) python -m core.killswitch set "$(NAME)" "$(STATE)" --reason "$(REASON)" --actor "$(ACTOR)"

clean-data: ## Delete the local company repo (not the database)
	rm -rf .data/kfin-ideas
