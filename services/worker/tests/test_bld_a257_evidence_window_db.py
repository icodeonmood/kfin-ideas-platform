"""BLD-A257: the dry run of the evidence window's three reads (docs/UAT.md, after step 10 of full mode).

A stack test (it uses the `db` fixture, BLD-A251): CI only, never run locally. It takes the three SQL strings OUT OF
docs/UAT.md (never a copy), seeds synthetic rows around an `ai.all` switch-on two hours ago and asserts every number
each read prints. It is also lane E's first READY condition: the dry run fails if a read could return idea text. The
numbers-only check below runs on every read's output, and on a deliberately bad read (read 1 with the ideas' titles,
built in the test) it must fail; the distinctive synthetic words seeded below never come out of the real reads.

Everything is seeded inside one transaction that is rolled back at the end, so `now()` is the same for every row and
every read. `audit_log` is append-only and the session's database is shared: other tests switch `ai.all` on at real
times, after "two hours ago". Inside this test's own transaction the guard is lifted only long enough to remove the
earlier `ai.all` rows, then put back, so the window starts where this test says; the rollback restores them.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

import pytest
import yaml
from psycopg.types.json import Jsonb

from core.db import Conn
from onepc.context import seal_text
from tests import helpers
from tests import lane_f_fixtures as lf
from tests.test_bld_a257_evidence_window import COLUMNS, bad_read, reads

pytestmark = pytest.mark.stack

# Distinctive synthetic words for one idea's title, summary, helper text, message and the team-up texts on it: they
# must never come out of a read (non-negotiable 3). Invented text only (non-negotiable 11).
WORDS = "Quokka ledger 7731 says the zebra mandate never reconciles"
OUTCOMES = frozenset(
    {
        "ok",
        "ok_after_retry",
        "cached",
        "agent_failed",
        "leak_abort",
        "tag_mismatch",
        "route_error",
        "switched_off",
    }
)  # the llm_calls outcome CHECK list (20261108000500_platform.sql)
AGENTS = frozenset(
    yaml.safe_load(p.read_text("utf-8"))["name"] for p in (helpers.ROOT / "agents").glob("*/config.yaml")
)
HOUR = 3600.0


def only_numbers_a_time_or_a_label(names: Sequence[str], rows: Sequence[dict[str, Any]]) -> list[str]:
    """What a read may print: a number, the window start (`since`, a timestamp), an agent's name in `agent`, an
    outcome from the CHECK list in `outcome`, or nothing. Returns each breach as `column: type`, never the value."""
    problems: list[str] = []
    for row in rows:
        for name in names:
            value = row[name]
            if value is None:
                continue
            if isinstance(value, bool):
                ok = False
            elif isinstance(value, int | float | Decimal):
                ok = name not in ("agent", "outcome", "since")
            elif isinstance(value, dt.datetime):
                ok = name == "since"
            elif isinstance(value, str):
                ok = (name == "agent" and value in AGENTS) or (name == "outcome" and value in OUTCOMES)
            else:
                ok = False
            if not ok:
                problems.append(f"{name}: {type(value).__name__}")
    return problems


def _run(conn: Conn, sql: str) -> tuple[list[str], list[dict[str, Any]]]:
    cur = conn.execute(sql)
    assert cur.description is not None
    return [d.name for d in cur.description], cur.fetchall()


def _ago(conn: Conn, seconds: float) -> dt.datetime:
    row = conn.execute("SELECT now() - %s::float8 * interval '1 second' AS t", (float(seconds),)).fetchone()
    assert row is not None
    return row["t"]


def _secs(seconds: float | None) -> float | None:
    """Seconds as a float (None stays NULL: the SQL casts it to float8 either way)."""
    return None if seconds is None else float(seconds)


def _clear_ai_all_switch_rows(conn: Conn) -> None:
    conn.execute("ALTER TABLE audit_log DISABLE TRIGGER audit_log_append_only")
    conn.execute("DELETE FROM audit_log WHERE entity = 'kill_switch:ai.all'")
    conn.execute("ALTER TABLE audit_log ENABLE TRIGGER audit_log_append_only")


def _switch(conn: Conn, name: str, state: str, seconds_ago: float) -> None:
    """The audit row `core.killswitch.set_switch` writes, at a chosen time."""
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, before, after, reason, at) "
        "VALUES ('ops:a257-test', 'kill_switch.set', %s, %s, %s, 'Synthetic switch change for the A257 dry run', "
        "now() - %s::float8 * interval '1 second')",
        (f"kill_switch:{name}", Jsonb({"state": "off" if state == "on" else "on"}), Jsonb({"state": state}),
         float(seconds_ago)),
    )  # fmt: skip


def _moved(
    conn: Conn, idea: dict[str, Any], frm: str, to: str, seconds_ago: float, source: str = "live"
) -> None:
    conn.execute(
        "INSERT INTO idea_status_history (idea_uuid, from_status, to_status, at, source) "
        "VALUES (%s, %s, %s, now() - %s::float8 * interval '1 second', %s)",
        (idea["id"], frm, to, float(seconds_ago), source),
    )


def _call(conn: Conn, agent: str, outcome: str, latency_ms: int, seconds_ago: float) -> None:
    conn.execute(
        "INSERT INTO llm_calls (agent, prompt_version, model, latency_ms, outcome, created_at) "
        "VALUES (%s, '1.0.0', 'synthetic-model', %s, %s, now() - %s::float8 * interval '1 second')",
        (agent, latency_ms, outcome, float(seconds_ago)),
    )


def _teamup(
    conn: Conn,
    idea: dict[str, Any],
    who: dict[str, Any],
    state: str,
    sent_ago: float,
    answered_ago: float | None,
) -> None:
    rid = str(uuid.uuid4())
    reason = (
        seal_text("teamup_requests", "lead_reason_encrypted", rid, WORDS) if state == "declined" else None
    )
    conn.execute(
        "INSERT INTO teamup_requests (id, idea_uuid, from_code, note_encrypted, state, lead_reason_encrypted, "
        "sent_at, answered_at) VALUES (%s, %s, %s, %s, %s, %s, now() - %s::float8 * interval '1 second', "
        "now() - %s::float8 * interval '1 second')",
        (rid, idea["id"], who["code"], seal_text("teamup_requests", "note_encrypted", rid, WORDS), state, reason,
         float(sent_ago), _secs(answered_ago)),
    )  # fmt: skip


def _ask(
    conn: Conn,
    draft: dict[str, Any],
    other: dict[str, Any],
    who: dict[str, Any],
    state: str,
    sent_ago: float,
    answered_ago: float | None,
) -> None:
    rid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO merge_requests (id, draft_uuid, other_idea_uuid, from_code, note_encrypted, state, sent_at, "
        "answered_at) VALUES (%s, %s, %s, %s, %s, %s, now() - %s::float8 * interval '1 second', "
        "now() - %s::float8 * interval '1 second')",
        (rid, draft["id"], other["id"], who["code"], seal_text("merge_requests", "note_encrypted", rid, WORDS),
         state, float(sent_ago), _secs(answered_ago)),
    )  # fmt: skip


def _seed(conn: Conn) -> list[dict[str, Any]]:
    """The synthetic world, relative to the transaction's now(). Returns the ideas sent and sorted in the window."""
    _clear_ai_all_switch_rows(conn)
    _switch(conn, "ai.all", "on", 5 * HOUR)  # an older switch-on: the window takes the latest
    _switch(conn, "ai.all", "off", 3 * HOUR)
    _switch(conn, "ai.all", "on", 2 * HOUR)  # the switch-on: the window starts here
    _switch(conn, "agent.gatekeeper", "on", 1 * HOUR)  # another switch never moves the window

    sharer = lf.person(conn, "Ojasvi Tarkunde")
    helper = lf.person(conn, "Hemant Valsangkar")
    asker = lf.person(conn, "Revati Mungekar")

    def idea(title: str, status: str, **kw: Any) -> dict[str, Any]:
        return lf.idea(conn, sharer, title, status=status, **kw)

    # Five ideas sent and sorted in the window: 3, 5, 7, 9 and 41 seconds from Send to sorted.
    # p50 = 7.0; p95 = 9 + 0.8 x (41 - 9) = 34.6 (percentile_cont, position 0.95 x 4 = 3.8); max = 41.0.
    sorted_ideas = [
        idea(WORDS, "with_review_desk", summary=f"{WORDS}. Branches see it daily.", helper_text=WORDS),
        idea("Nominee updates bounce at the counter", "needs_you"),
        idea("SIP pause requests wait two days", "with_review_desk"),
        idea("Address changes need a second visit", "with_review_desk"),
        idea("Redemption letters print twice", "with_review_desk"),
    ]
    lf.message(conn, sorted_ideas[0], WORDS)
    for i, (sent_ago, took) in enumerate([(90, 3), (80, 5), (70, 7), (60, 9), (50, 41)]):
        _moved(conn, sorted_ideas[i], "draft", "checking", sent_ago * 60)
        _moved(conn, sorted_ideas[i], "checking", "with_review_desk", sent_ago * 60 - took)
    # Only the first move out of checking counts: the desk's question 10 minutes later changes nothing.
    _moved(conn, sorted_ideas[1], "with_review_desk", "needs_you", 80 * 60 - 600)

    # Two sent in the window and still being checked: one 20 minutes ago (over 15 minutes), one 5 minutes ago.
    for minutes in (20, 5):
        waiting = idea(f"Mandate form check {minutes}", "checking")
        _moved(conn, waiting, "draft", "checking", minutes * 60)

    # Left out: sent before the switch-on (sorted before it, and sorted after it), a backfill row, and a restore
    # (withdrawn -> checking is not a Send).
    before = idea("Dividend mail goes to old addresses", "with_review_desk")
    _moved(conn, before, "draft", "checking", 3 * HOUR)
    _moved(conn, before, "checking", "with_review_desk", 3 * HOUR - 100)
    across = idea("KYC copies are asked for again", "with_review_desk")
    _moved(conn, across, "draft", "checking", 2 * HOUR + 600)
    _moved(conn, across, "checking", "with_review_desk", 1 * HOUR)
    backfilled = idea("Old folio merges take a week", "with_review_desk")
    _moved(conn, backfilled, "draft", "checking", 1 * HOUR, source="backfill")
    _moved(conn, backfilled, "checking", "with_review_desk", 1 * HOUR - 50)
    restored = idea("Branch queues at month end", "with_review_desk")
    _moved(conn, restored, "withdrawn", "checking", 30 * 60)
    _moved(conn, restored, "checking", "with_review_desk", 30 * 60 - 20)

    # Model calls: two agents, two outcomes; one call before the switch-on is left out.
    for ms, minutes in ((1200, 80), (1800, 70), (2400, 60), (3000, 50), (9000, 40)):
        _call(conn, "gatekeeper", "ok", ms, minutes * 60)
    _call(conn, "gatekeeper", "route_error", 30000, 30 * 60)
    _call(conn, "draft-part", "ok", 4000, 45 * 60)
    _call(conn, "draft-part", "ok", 6000, 35 * 60)
    _call(conn, "gatekeeper", "ok", 60000, 3 * HOUR)

    # Team-up requests on the idea with the distinctive words (every note and reason sealed with them).
    lead = sorted_ideas[0]
    other = sorted_ideas[2]
    _teamup(conn, lead, helper, "approved_team_only", 90 * 60, 60 * 60)  # sent, answered
    _teamup(conn, other, helper, "declined", 80 * 60, 30 * 60)  # sent, answered, declined
    _teamup(conn, lead, asker, "declined", 3 * HOUR, 1 * HOUR)  # sent before: answered and declined
    _teamup(conn, other, asker, "sent", 10 * 60, None)  # sent, waiting
    _teamup(conn, sorted_ideas[3], helper, "declined", 4 * HOUR, 3 * HOUR)  # wholly before: left out
    _teamup(conn, sorted_ideas[4], helper, "closed", 100 * 60, 20 * 60)  # closed with its idea: answered
    _teamup(conn, sorted_ideas[1], asker, "withdrawn", 30 * 60, None)  # withdrawn by its sender: sent only
    # Drafts' asks: two sent in the window (one waiting, one declined), one sent before it.
    drafts = [
        lf.idea(conn, asker, f"Draft about {w}", shared_days=None) for w in ("mandates", "nominees", "KYC")
    ]
    _ask(conn, drafts[0], lead, asker, "waiting", 45 * 60, None)
    _ask(conn, drafts[1], lead, asker, "declined", 2 * HOUR + 1800, 1 * HOUR)
    _ask(conn, drafts[2], other, asker, "declined", 20 * 60, 5 * 60)
    return sorted_ideas


def test_bld_a257_the_three_reads_on_seeded_rows(db: Any) -> None:
    conn: Conn = db
    with conn.transaction(force_rollback=True):
        _seed(conn)
        # The history trigger added its own rows (from_status NULL) for every idea inserted: they change nothing.
        trig = conn.execute(
            "SELECT count(*) AS n FROM idea_status_history WHERE from_status IS NULL"
        ).fetchone()
        assert trig is not None and trig["n"] >= 14
        r1, r2, r3 = reads()
        outputs = [_run(conn, sql) for sql in (r1, r2, r3)]

        names, rows = outputs[0]
        assert tuple(names) == COLUMNS[0]
        assert rows == [
            {
                "since": _ago(conn, 2 * HOUR),
                "sent": 7,
                "sorted": 5,
                "checking_over_15_min": 1,
                "p50_s": Decimal("7.0"),
                "p95_s": Decimal("34.6"),
                "max_s": Decimal("41.0"),
            }
        ]

        names, rows = outputs[1]
        assert tuple(names) == COLUMNS[1]
        assert [tuple(r.values()) for r in rows] == [
            ("draft-part", "ok", 2, Decimal("5.0"), Decimal("5.9"), Decimal("6.0")),
            ("gatekeeper", "ok", 5, Decimal("2.4"), Decimal("7.8"), Decimal("9.0")),
            ("gatekeeper", "route_error", 1, Decimal("30.0"), Decimal("30.0"), Decimal("30.0")),
        ]

        names, rows = outputs[2]
        assert tuple(names) == COLUMNS[2]
        assert rows == [{"teamup_sent": 5, "teamup_answered": 4, "teamup_declined": 2, "draft_asks": 2}]

        # Lane E's READY condition 1: numbers, a timestamp or a label only, and never the seeded words.
        for names, rows in outputs:
            assert only_numbers_a_time_or_a_label(names, rows) == []
            assert WORDS not in repr(rows) and "Quokka" not in repr(rows)


def test_bld_a257_the_numbers_only_check_fails_on_a_read_that_prints_idea_text(db: Any) -> None:
    """The dry run's gate is real: read 1 with the ideas' titles in its select list (built in the test, never in
    the doc) runs on the same rows, prints the seeded words, and the check fails on it."""
    conn: Conn = db
    with conn.transaction(force_rollback=True):
        _seed(conn)
        names, rows = _run(conn, bad_read())
        assert "title" in names and WORDS in repr(rows)
        assert only_numbers_a_time_or_a_label(names, rows) == ["title: str"]
        # The check names a breach by column and type only, never by its value.
        assert all(WORDS not in p for p in only_numbers_a_time_or_a_label(names, rows))
        # And a label column holding anything but a label fails too.
        assert only_numbers_a_time_or_a_label(["agent"], [{"agent": WORDS}]) == ["agent: str"]
        assert only_numbers_a_time_or_a_label(["outcome"], [{"outcome": "free text"}]) == ["outcome: str"]
        assert only_numbers_a_time_or_a_label(["sent"], [{"sent": _ago(conn, 0)}]) == ["sent: datetime"]


def test_bld_a257_with_no_switch_on_row_read_1_prints_an_empty_since_and_zeros(db: Any) -> None:
    conn: Conn = db
    with conn.transaction(force_rollback=True):
        _seed(conn)
        _clear_ai_all_switch_rows(conn)
        _switch(conn, "ai.all", "off", 1 * HOUR)  # an ai.all switch-off is not a switch-on
        r1, r2, r3 = reads()
        names, rows = _run(conn, r1)
        assert rows == [
            {
                "since": None,
                "sent": 0,
                "sorted": 0,
                "checking_over_15_min": 0,
                "p50_s": None,
                "p95_s": None,
                "max_s": None,
            }
        ]
        assert only_numbers_a_time_or_a_label(names, rows) == []
        assert _run(conn, r2)[1] == []
        assert _run(conn, r3)[1] == [
            {"teamup_sent": 0, "teamup_answered": 0, "teamup_declined": 0, "draft_asks": 0}
        ]
