"""BLD-A249: the runbook's note for the first upgrade to a build with lane C's hourly file clean-up (BLD-C242,
L-HIDE.files). Doc tests only: the note sits in "Updating the live server" after the rollback step, and its three
read-only reads count exactly what `files.sweep` deletes. The check against the code skips until BLD-C242 is in the
build (its `start_sweep_done`)."""

from __future__ import annotations

import ast
import inspect
import re
import textwrap

import pytest

from tests import helpers

UAT_DOC = helpers.ROOT / "docs" / "UAT.md"
NOTE = "**The first upgrade to a build with the hourly file clean-up (BLD-C242).**"

READ_LATEST_START_SWEEP = (
    "SELECT after->>'complete' FROM audit_log WHERE entity = 'files:start_sweep' AND action = 'file.start_sweep' "
    "ORDER BY at DESC, id DESC LIMIT 1"
)
READ_FAILED_COPIES = (
    "SELECT count(*) FROM attachments WHERE kind = 'file' AND file_state = 'upload_failed' AND store_key IS NOT NULL "
    "AND (checks->>'ended_at')::timestamptz < now() - interval '24 hours' AND coalesce(checks->>'copy', '') <> 'gone'"
)
READ_UNSENT_CONVERSATION = (
    "SELECT count(*) FROM attachments WHERE purpose = 'conversation' AND conversation_entry_id IS NULL "
    "AND answer_id IS NULL AND created_at < now() - interval '24 hours'"
)
READS = (READ_LATEST_START_SWEEP, READ_FAILED_COPIES, READ_UNSENT_CONVERSATION)


def _section(doc: str, heading: str) -> str:
    return doc.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]


def _note() -> str:
    section = _section(UAT_DOC.read_text("utf-8"), "Updating the live server (upgrade and rollback)")
    return section.split(NOTE, 1)[1].split("**What a rollback loses:**", 1)[0]


def _where(sql: str) -> str:
    """The filter after the first WHERE, up to ORDER BY or the end, with one space between words."""
    where = sql.split(" WHERE ", 1)[1].split(" ORDER BY ", 1)[0]
    return re.sub(r"\s+", " ", where).strip()


def _sql_in(fn: object) -> list[str]:
    """Every string in a function's body that runs SQL (implicitly joined literals arrive as one constant)."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))  # type: ignore[arg-type]
    return [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.lstrip().startswith("SELECT")
    ]


def test_bld_a249_note_sits_after_the_rollback_step_and_before_what_a_rollback_loses() -> None:
    section = _section(UAT_DOC.read_text("utf-8"), "Updating the live server (upgrade and rollback)")
    assert section.count(NOTE) == 1
    assert section.index("6. Rollback, only when the product lead decides it") < section.index(NOTE)
    assert section.index(NOTE) < section.index("**What a rollback loses:**")


def test_bld_a249_note_gives_the_three_reads_the_timing_and_the_pass_line() -> None:
    note = _note()
    for read in READS:
        assert f'docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "{read}"' in note
    assert note.count("docker exec ") == 3  # read-only: three SELECTs, nothing else
    assert "about 5 minutes after step 5" in note
    assert "Pass: the first read prints `true`, and both counts are 0 or a handful" in note
    assert "after the next :30 past the hour" in note
    assert "send the reads to lane A" in note
    assert "Try again asks for the file again" in note
    # Lane C's rollback check: the database goes back, the file store does not.
    assert "the database goes back to the backup, but the file store does not" in note
    assert "comes back in its box without its copy: it does not open, and Remove clears it" in note
    assert "`attachments.rejected_retention_hours` in the company repo's `rules/thresholds.md`" in note
    # Plain words, no secret, no real address.
    assert not re.search(r"@kfintech\.com|PASSWORD=|SECRET", note)


def test_bld_a249_the_24_hours_match_the_rules_and_the_conversation_limit() -> None:
    thresholds = (helpers.ROOT / "seed" / "company-repo" / "rules" / "thresholds.md").read_text("utf-8")
    assert re.search(r"^\s*rejected_retention_hours: 24$", thresholds, re.M)
    from attachments import files

    assert files.UNSENT_CONVERSATION_HOURS == 24


def test_bld_a249_reads_count_what_files_sweep_deletes_once_c242_is_in() -> None:
    from attachments import files

    if not hasattr(files, "start_sweep_done"):
        pytest.skip("BLD-C242 is not in this build yet")
    from jobs import schedule

    assert schedule.EVERY["files.sweep"] == 60

    def as_code(read: str) -> str:
        return _where(read).replace("interval '24 hours'", "make_interval(hours => %s)")

    def tail(sql: str) -> str:  # the filter, the order and the limit: the latest row, as the guard reads it
        return re.sub(r"\s+", " ", sql.split(" WHERE ", 1)[1]).strip()

    (guard,) = _sql_in(files.start_sweep_done)
    assert tail(guard) == tail(READ_LATEST_START_SWEEP)
    assert guard.split(" FROM ", 1)[1].split(" WHERE ", 1)[0] == "audit_log"

    failed = _sql_in(files._sweep_failed)
    assert [_where(s) for s in failed] == [as_code(READ_FAILED_COPIES)]

    unsent = [_where(s) for s in _sql_in(files.sweep_unsent_conversation)]
    assert unsent[0] == as_code(READ_UNSENT_CONVERSATION)
