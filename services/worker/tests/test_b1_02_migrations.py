"""AT-B1-02: `make migrate` applies all migrations to an empty database; a second run changes nothing;
extensions `vector` and `pg_trgm` exist."""

from pathlib import Path

import psycopg
import pytest

from tests import helpers

pytestmark = pytest.mark.stack

MIGRATIONS = sorted((helpers.ROOT / "db" / "migrations").glob("*.sql"))
DAY_ONE_TABLES = {
    "users", "contributor_map", "role_grants", "ideas", "attachments", "idea_links", "clusters", "review_items",
    "corrections", "sla_timers", "points_ledger", "notifications", "comms_log", "comms_prefs", "outbox", "jobs",
    "llm_calls", "pseudonym_vault", "autonomy", "kill_switches", "audit_log", "chunks", "links", "terms",
}  # fmt: skip


def _snapshot(url: str) -> tuple[list[tuple[str, ...]], list[str]]:
    with psycopg.connect(url) as conn:
        columns = conn.execute(
            "SELECT table_name, column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'public' ORDER BY 1, 2"
        ).fetchall()
        versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY 1").fetchall()]
    return [tuple(c) for c in columns], versions


def test_migrate_twice_on_an_empty_database() -> None:
    name = helpers.create_database("ideas_migrate")
    try:
        first = helpers.dbmate(name, "up")
        assert first.returncode == 0
        url = helpers.db_url(name)
        after_first = _snapshot(url)
        assert (
            len(after_first[1])
            == len(MIGRATIONS)
            == len(list(Path(helpers.ROOT / "db" / "migrations").glob("*.sql")))
        )

        second = helpers.dbmate(name, "up")
        assert second.returncode == 0
        assert "Applying" not in second.stdout
        assert _snapshot(url) == after_first

        with psycopg.connect(url) as conn:
            extensions = {r[0] for r in conn.execute("SELECT extname FROM pg_extension").fetchall()}
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                ).fetchall()
            }
        assert {"vector", "pg_trgm"} <= extensions
        assert tables >= DAY_ONE_TABLES
    finally:
        helpers.drop_database(name)


def test_append_only_tables_refuse_updates(test_database: str) -> None:
    with psycopg.connect(helpers.db_url(test_database), autocommit=True) as conn:
        conn.execute(
            "INSERT INTO audit_log (actor, action, entity) VALUES ('system', 'test.append_only', 'x')"
        )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE audit_log SET actor = 'someone' WHERE action = 'test.append_only'")


def test_outbox_refuses_prose_errors(test_database: str) -> None:
    """BLD-020: error columns hold codes, so a stack trace or idea text cannot land there."""
    with (
        psycopg.connect(helpers.db_url(test_database), autocommit=True) as conn,
        pytest.raises(psycopg.errors.CheckViolation),
    ):
        conn.execute(
            "INSERT INTO outbox (event_type, aggregate_id, actor, last_error) "
            "VALUES ('idea.submitted', 'IDEA-2026-000001', 'system', 'Failed: SIP forms are slow')"
        )
