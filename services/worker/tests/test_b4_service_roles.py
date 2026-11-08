"""Per-service database roles (BLD-032, BLD-077): the web app's role can never read the pseudonym vault or the
model cache, cannot write the model-call log and cannot change or remove contributor codes. The worker (gateway
and restore service) can. The list of tables hidden from the web role is pinned here, so a new sensitive
table cannot slip through by default."""

from __future__ import annotations

import psycopg
import pytest

from core.db import connect

pytestmark = pytest.mark.stack
WEB = "postgres://ideas_web:dev-web-only@localhost:5432/ideas?sslmode=disable"
WORKER = "postgres://ideas_worker:dev-worker-only@localhost:5432/ideas?sslmode=disable"
HIDDEN_FROM_WEB = {"pseudonym_vault", "llm_cache", "vault_counters", "schema_migrations"}


def test_web_role_cannot_touch_the_vault_or_cache() -> None:
    with psycopg.connect(WEB, autocommit=True) as web:
        for table in ("pseudonym_vault", "llm_cache"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                web.execute(f"SELECT 1 FROM {table} LIMIT 1")  # noqa: S608 - fixed names
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            web.execute(
                "INSERT INTO llm_calls (agent, prompt_version, model, outcome) VALUES ('x', '0', 'x', 'ok')"
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            web.execute("UPDATE contributor_map SET contributor_code = contributor_code WHERE false")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            web.execute("UPDATE scans SET result_encrypted = NULL WHERE false")  # results are the worker's
        web.execute("UPDATE scans SET overrides = overrides WHERE false")  # a person's choice is allowed
        assert web.execute("SELECT count(*) FROM ideas").fetchone() is not None
        assert web.execute("SELECT count(*) FROM llm_calls").fetchone() is not None


def test_worker_role_reaches_what_the_gateway_needs() -> None:
    with psycopg.connect(WORKER, autocommit=True) as worker:
        for table in ("pseudonym_vault", "llm_cache", "llm_calls", "scans", "jobs", "outbox"):
            worker.execute(f"SELECT 1 FROM {table} LIMIT 1")  # noqa: S608 - fixed names


def test_the_tables_hidden_from_web_are_exactly_the_pinned_list() -> None:
    with connect(autocommit=True) as owner:
        rows = owner.execute(
            "SELECT table_name, has_table_privilege('ideas_web_svc', format('public.%I', table_name), 'SELECT') AS web, "
            "has_table_privilege('ideas_worker_svc', format('public.%I', table_name), 'SELECT') AS worker "
            "FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        ).fetchall()
    hidden = {r["table_name"] for r in rows if not r["web"]}
    assert hidden == HIDDEN_FROM_WEB
    assert {r["table_name"] for r in rows if not r["worker"]} == {"schema_migrations"}
