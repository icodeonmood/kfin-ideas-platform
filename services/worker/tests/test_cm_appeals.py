"""Appeals (§4.12) and the fairness report (§3.8, §5.4), host-side against a test database, built on the committee
flow so the decision is real (BLD-222, BLD-223). Filing and hearing an appeal, and the calibration report, went with
their routes (DEC-106, BLD-E078); what is left is whether a decision could be appealed and the parked-group cycle."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import pytest

from committee import appeals, reports, rounds
from tests.test_cm_committee import _grant, _held, _owner_of, _qualify, _score_all, qualified  # noqa: F401
from tests.test_rd_clustering import _user, pool  # noqa: F401 - fixtures

pytestmark = pytest.mark.stack


def _round_decision(q: Any, outcome: str, code: str) -> str:
    """A preliminary review parks or declines the group: a decision on record."""
    _qualify(q)
    rid = rounds.open_cycle(q["db"], q["chair"], {"presentation_slots": 8})["rounds"][0]
    rounds.prescore_round(q["db"], str(rid))  # the `round.prescore` job
    _score_all(q, str(rid), value=1)
    rounds.act(q["db"], str(rid), q["chair"], {"action": "decide", "outcome": outcome, "reason_code": code,
                                                "note": "Not enough value for KFintech right now, given the effort."})  # fmt: skip
    d = (
        q["db"]
        .execute(
            "SELECT id FROM decisions WHERE cluster_id = %s ORDER BY decided_at DESC LIMIT 1", (q["cid"],)
        )
        .fetchone()
    )
    return str(d["id"])


def test_a_first_park_is_not_open_to_appeal_but_a_second_is(qualified: Any) -> None:  # noqa: F811
    db = qualified["db"]
    first = _round_decision(qualified, "parked", "NOT_FEASIBLE_NOW")
    row = db.execute("SELECT appeal_window_closes FROM decisions WHERE id = %s", (first,)).fetchone()
    assert row["appeal_window_closes"] is None
    assert not appeals.appealable(db, qualified["cid"], "parked", first)  # a first park cannot be appealed
    assert appeals.appealable(db, qualified["cid"], "parked")  # the next park would be the second


def test_reports_count_without_naming_anyone(qualified: Any) -> None:  # noqa: F811
    db = qualified["db"]
    _round_decision(qualified, "declined", "LOW_VALUE")
    start, end = dt.datetime(2020, 1, 1, tzinfo=dt.UTC), dt.datetime(2100, 1, 1, tzinfo=dt.UTC)
    fair = reports.fairness(db, start, end)
    names = [r["name"] for r in db.execute("SELECT name FROM users").fetchall()]
    text = json.dumps(fair)
    assert not any(n in text for n in names)
    assert fair["by_lob"] and all(
        r["scored"] == "fewer than 5" or isinstance(r["scored"], int) for r in fair["by_lob"]
    )


def test_report_periods_are_whole_quarters_in_ist() -> None:
    now = dt.datetime(2026, 11, 10, 6, 0, tzinfo=dt.UTC)
    assert reports.current_quarter(now) == "2026-Q4"
    start, end = reports.period("2026-Q3", now)
    assert start == dt.datetime(2026, 6, 30, 18, 30, tzinfo=dt.UTC)  # 1 July 00:00 IST
    assert end == dt.datetime(2026, 9, 30, 18, 30, tzinfo=dt.UTC)
    assert reports.period(None, now)[1] == now  # the current quarter runs up to now
    for bad in ("2026-13-01", "2026-Q5", "2027-Q1"):
        with pytest.raises(ValueError):
            reports.period(bad, now)


# ---- parked groups at the next cycle (§4.7, BLD-228) ---------------------------------------------------------------


def _park_again(q: Any) -> str:
    """The next cycle: the parked group is back for a new round, and the committee parks it again."""
    out = rounds.open_cycle(q["db"], q["chair"], {"presentation_slots": 8})
    assert out["returned"] == [q["cid"]] and len(out["rounds"]) == 1
    rid = str(out["rounds"][0])
    rounds.prescore_round(q["db"], rid)
    _score_all(q, rid, value=1)
    rounds.act(q["db"], rid, q["chair"], {"action": "decide", "outcome": "parked", "reason_code": "CAPACITY",
                                          "note": "Worth doing, but this cycle's capacity is already full."})  # fmt: skip
    d = (
        q["db"]
        .execute(
            "SELECT id FROM decisions WHERE cluster_id = %s ORDER BY decided_at DESC LIMIT 1", (q["cid"],)
        )
        .fetchone()
    )
    return str(d["id"])


def _stage(q: Any) -> tuple[str, Any]:
    c = q["db"].execute("SELECT stage, archived_at FROM clusters WHERE id = %s", (q["cid"],)).fetchone()
    return str(c["stage"]), c["archived_at"]


def test_a_parked_group_comes_back_at_the_next_cycle_and_is_archived_after_two_parks(qualified: Any) -> None:  # noqa: F811
    db = qualified["db"]
    _round_decision(qualified, "parked", "NOT_FEASIBLE_NOW")
    second = _park_again(qualified)
    assert _stage(qualified) == ("parked", None)
    # Two parks and no colleague joined: archived at the next cycle, not back for a third round.
    out = rounds.open_cycle(db, qualified["chair"], {"presentation_slots": 8})
    assert out["archived"] == [qualified["cid"]] and out["returned"] == [] and out["rounds"] == []
    stage, archived_at = _stage(qualified)
    assert stage == "parked" and archived_at is not None  # still "parked" on screen
    # The second park can still be appealed.
    assert appeals.appealable(db, qualified["cid"], "parked", second)
    audit = db.execute(
        "SELECT action FROM audit_log WHERE entity = %s ORDER BY id", (f"cluster:{qualified['cid']}",)
    ).fetchall()
    assert [a["action"] for a in audit][-2:] == ["cluster.returned", "cluster.archived"]
    # A later cycle leaves an archived group alone.
    assert rounds.open_cycle(db, qualified["chair"], {"presentation_slots": 8})["archived"] == []


def test_a_new_joiner_keeps_a_parked_group_coming_back(qualified: Any) -> None:  # noqa: F811
    db = qualified["db"]
    _round_decision(qualified, "parked", "NOT_FEASIBLE_NOW")
    _park_again(qualified)
    code = _owner_of(qualified)["contributor_code"]
    db.execute(
        "INSERT INTO idea_links (cluster_id, contributor_code, link_type) VALUES (%s, %s, 'joiner')",
        (qualified["cid"], code),
    )
    out = rounds.open_cycle(db, qualified["chair"], {"presentation_slots": 8})
    assert out["returned"] == [qualified["cid"]] and out["archived"] == [] and len(out["rounds"]) == 1
