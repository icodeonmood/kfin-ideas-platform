"""Per-service database roles (BLD-032, BLD-077): the web app's role can never read the pseudonym vault or the
model cache, cannot write the model-call log and cannot change or remove contributor codes. The worker (gateway
and restore service) can. The list of tables hidden from the web role is pinned here, so a new sensitive
table cannot slip through by default."""

from __future__ import annotations

import psycopg
import pytest

from core.config import get_settings
from core.db import connect

pytestmark = pytest.mark.stack
_PORT = get_settings().postgres_port
WEB = f"postgres://ideas_web:dev-web-only@localhost:{_PORT}/ideas?sslmode=disable"
WORKER = f"postgres://ideas_worker:dev-worker-only@localhost:{_PORT}/ideas?sslmode=disable"
HIDDEN_FROM_WEB = {
    "pseudonym_vault", "llm_cache", "vault_counters", "schema_migrations",
    "sealed_scores", "ai_prescores", "assessments", "decision_sheets",  # sealed committee records (§4.6–§4.7)
    "appeals",  # statements reach the panel through the worker only (§4.12, BLD-222)
    "voice_notes",  # recordings and what was heard reach the owner through the worker only (DEC-096, BLD-C002)
    "idea_words_sealed",  # the sharer's unmasked words, readable by them alone (DEC-103, L-HIDE.rules/4)
    "voice_streams",  # what a voice note heard, sealed for the person until the draft takes it (DEC-108, BLD-C112)
}  # fmt: skip
# Final or audit-like records of the handoff cut-over: the web role inserts and reads them, never changes or removes
# them (L-DECIDE.rules/9, L-COMMITTEE.rules/4, L-SUBMIT.edit/4, L-AUDIT.flags).
APPEND_ONLY_FOR_WEB = {
    "idea_decisions", "decision_reversals", "idea_versions", "flag_exposures", "idea_opens", "idea_status_history",
}  # fmt: skip


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


def test_the_web_role_cannot_change_final_records_e_entities() -> None:
    """E-ENTITIES.review: decisions and reversals are final; versions, exposures, opens and status history are logs.
    The web role keeps SELECT and INSERT on each; only these tables (of those it can read) lack UPDATE or DELETE."""
    with connect(autocommit=True) as owner:
        rows = owner.execute(
            "SELECT table_name, "
            "has_table_privilege('ideas_web_svc', format('public.%I', table_name), 'SELECT') AS can_select, "
            "has_table_privilege('ideas_web_svc', format('public.%I', table_name), 'INSERT') AS can_insert, "
            "has_table_privilege('ideas_web_svc', format('public.%I', table_name), 'UPDATE') AS can_update, "
            "has_table_privilege('ideas_web_svc', format('public.%I', table_name), 'DELETE') AS can_delete "
            "FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        ).fetchall()
    readable = [r for r in rows if r["can_select"]]
    final = {r["table_name"] for r in readable if not r["can_update"] and not r["can_delete"]}
    # llm_calls is read-only for web and contributor codes are never changed or removed by it (BLD-077).
    assert final - {"llm_calls", "contributor_map"} == APPEND_ONLY_FOR_WEB
    assert all(r["can_insert"] for r in readable if r["table_name"] in APPEND_ONLY_FOR_WEB)
