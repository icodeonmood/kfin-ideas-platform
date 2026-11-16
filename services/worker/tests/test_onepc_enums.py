"""E-ENUMS shared contract (BLD-E006): `contracts/1pc/enums.json` is the one source; the worker's copy equals it, the
cut-over migration's CHECK constraints equal it (read from the file here, and from the live database in the stack
test), and the encryption context matches the web app's."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core.config import REPO_ROOT
from onepc import enums
from onepc.context import open_text, seal_text, sealed_context

assert REPO_ROOT is not None
ROOT: Path = REPO_ROOT
SOURCE = ROOT / "contracts" / "1pc" / "enums.json"
MIGRATION = ROOT / "db" / "migrations" / "20261121500100_handoff_cutover.sql"
_TABLE = re.compile(r"(?:CREATE|ALTER) TABLE (\w+)")
_CHECK = re.compile(r"CHECK \(\s*(\w+) IN \(([^)]*)\)|CHECK \(\s*(\w+) <@ ARRAY\[([^\]]*)\]")
_LITERAL = re.compile(r"'([^']*)'")


def checks_in_migration(sql: str) -> dict[str, frozenset[str]]:
    up = sql.split("-- migrate:down")[0]
    tables = [(m.start(), m.group(1)) for m in _TABLE.finditer(up)]
    out: dict[str, frozenset[str]] = {}
    for m in _CHECK.finditer(up):
        table = [name for at, name in tables if at < m.start()][-1]
        column, listed = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        out[f"{table}.{column}"] = frozenset(_LITERAL.findall(listed))
    return out


def test_e_enums_worker_copy_equals_the_source() -> None:
    assert json.loads(enums.ENUMS_FILE.read_text(encoding="utf-8")) == json.loads(
        SOURCE.read_text(encoding="utf-8")
    ), "run `cd apps/web && npm run sync:shared`"


def test_e_enums_idea_status_is_the_packs_eleven() -> None:
    assert enums.IDEA_STATUS == (
        "draft", "checking", "with_review_desk", "needs_you", "picked", "being_built", "shipped",
        "not_now", "not_picked", "withdrawn", "merged",
    )  # fmt: skip
    assert set(enums.CLOSED_STATUSES) == {"not_picked", "not_now", "withdrawn", "merged"}
    assert enums.TIER_NAME[1] == "Spark" and enums.TIER_NAME[7] == "Star"
    assert enums.is_value("hidden_kind", "folio") and not enums.is_value("hidden_kind", "pran")


def test_e_enums_every_check_in_the_migration_equals_its_enum() -> None:
    found = checks_in_migration(MIGRATION.read_text(encoding="utf-8"))
    for key in enums.db_checks():
        assert key in found, f"{key}: no CHECK in the cut-over migration"
        assert found[key] == enums.expected_check_values(key), key


def test_promises_are_not_checks_in_sql() -> None:
    """P-PRODUCT.promises: the answer times and the return periods are configuration."""
    found = checks_in_migration(MIGRATION.read_text(encoding="utf-8"))
    for key in ("question_sets.time_to_answer", "idea_decisions.return_in", "decision_reversals.return_in"):
        assert key not in found


def test_sealed_text_round_trips_and_is_bound_to_its_row() -> None:
    assert (
        sealed_context("idea_decisions", "reason_encrypted", "abc") == "idea_decisions.reason_encrypted:abc"
    )
    blob = seal_text("answers", "text_encrypted", "row-1", "Synthetic answer text")
    assert open_text("answers", "text_encrypted", "row-1", blob) == "Synthetic answer text"
    assert open_text("answers", "text_encrypted", "row-2", blob) is None
    sealed = seal_text("idea_words_sealed", "text_encrypted", 7, "Synthetic words", vault=True)
    assert open_text("idea_words_sealed", "text_encrypted", 7, sealed, vault=True) == "Synthetic words"


@pytest.mark.stack
def test_e_enums_the_live_database_checks_equal_the_json() -> None:
    """The migrated dev database (make test runs `make migrate` first) holds exactly these CHECK values."""
    from core.db import connect

    with connect(autocommit=True) as conn:
        for key in enums.db_checks():
            table, column = key.split(".")
            rows = conn.execute(
                "SELECT pg_get_constraintdef(c.oid) AS def FROM pg_constraint c "
                "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1] "
                "WHERE c.contype = 'c' AND c.conrelid = %s::regclass AND a.attname = %s "
                "AND array_length(c.conkey, 1) = 1",
                (f"public.{table}", column),
            ).fetchall()
            listed = [r["def"] for r in rows if " ANY " in r["def"] or "<@" in r["def"]]
            assert len(listed) == 1, f"{key}: expected one enum CHECK, found {len(listed)}"
            assert frozenset(_LITERAL.findall(listed[0])) == enums.expected_check_values(key), key
