"""Appeals (§4.12) and the fairness and calibration reports (§3.8, §5.4), host-side against a test database, built
on the committee flow so the decision being appealed is real (BLD-222, BLD-223)."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterator
from typing import Any

import pytest

from committee import appeals, decide, reports, rounds
from okf.frontmatter import parse
from okf.validate import check_concept_meta
from repo_writer.writer import RepoWriter
from review.service import ActionRefused
from tests import helpers
from tests.test_cm_committee import _grant, _held, _owner_of, _qualify, _score_all, qualified  # noqa: F401
from tests.test_rd_clustering import _user, pool  # noqa: F401 - fixtures

pytestmark = pytest.mark.stack

STATEMENT = "The committee read this as a single branch problem; it happens at every branch that takes physical forms."
REASONS = "The group spans every branch; the committee should score it again with that in view."


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


@pytest.fixture
def seeded_rules(qualified: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:  # noqa: F811
    """Message rules and templates from this run's seeded repo, not the dev stack's copy."""
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(qualified["repo"]))
    get_settings.cache_clear()
    yield
    monkeypatch.undo()
    get_settings.cache_clear()


def _owner(q: Any) -> str:
    return str(_owner_of(q)["user_id"])


def _file(q: Any, did: str, **extra: Any) -> dict[str, Any]:
    return appeals.file(q["db"], _owner(q), {"decision_id": did, "grounds": ["misunderstood_or_wrongly_merged"],
                                             "statement": STATEMENT, **extra})  # fmt: skip


def test_a_contributor_appeals_a_decline_once_and_a_panel_hears_it(qualified: Any) -> None:  # noqa: F811
    db = qualified["db"]
    did = _round_decision(qualified, "declined", "LOW_VALUE")
    owner = _owner(qualified)
    mine = appeals.mine(db, owner)
    assert any(d["decision_id"] == did and d["can_appeal"] for d in mine)
    out = _file(qualified, did, links=["https://intranet.example/report"], hearing=True)
    aid = out["appeal_id"]
    a = db.execute("SELECT * FROM appeals WHERE id = %s", (aid,)).fetchone()
    panel = [str(p) for p in a["panel"]]
    assert (
        a["heard_by"] == "panel" and len(panel) == 3 and qualified["chair"] not in panel
    )  # the decider never sits
    assert (
        a["hearing_requested"] is True
        and a["statement"] != ""
        and a["links"] == ["https://intranet.example/report"]
    )
    assert (
        db.execute("SELECT stage FROM clusters WHERE id = %s", (qualified["cid"],)).fetchone()["stage"]
        == "appealed"
    )
    with pytest.raises(ActionRefused) as again:
        _file(qualified, did)
    assert again.value.code == "already_appealed"
    # Blind materials for the panel, with medians and spread but never individual scores; nobody else sees it.
    view = appeals.panel_view(db, aid, panel[0])
    assert (
        view is not None
        and view["i_chair"]
        and view["decision"]["medians"]
        and "sealed" not in json.dumps(view)
    )
    assert (
        appeals.panel_view(db, aid, owner) is None and appeals.panel_view(db, aid, qualified["chair"]) is None
    )
    with pytest.raises(ActionRefused) as not_chair:
        appeals.decide(db, aid, panel[1], {"outcome": "upheld", "reasons": REASONS})
    assert not_chair.value.code == "panel_chair_only"
    done = appeals.decide(db, aid, panel[0], {"outcome": "re_score", "reasons": REASONS})
    assert done["stage"] == "ready_for_scoring"
    assert db.execute(
        "SELECT 1 FROM outbox WHERE event_type = 'appeal.decided' AND aggregate_id = %s", (aid,)
    ).fetchone()
    # The next round shows the panel's direction.
    rid = rounds.open_cycle(db, qualified["chair"], {"presentation_slots": 8})["rounds"][0]
    assert rounds.round_view(db, str(rid), qualified["members"][0])["appeal_direction"]


def test_only_contributors_appeal_and_only_in_time(qualified: Any) -> None:  # noqa: F811
    db = qualified["db"]
    did = _round_decision(qualified, "declined", "LOW_VALUE")
    stranger, _ = _user(db)
    with pytest.raises(ActionRefused) as nope:
        appeals.file(db, stranger, {"decision_id": did, "grounds": ["new_evidence"], "statement": STATEMENT})
    assert nope.value.code == "not_found"
    db.execute("UPDATE decisions SET appeal_window_closes = now() - interval '1 day' WHERE id = %s", (did,))
    with pytest.raises(ActionRefused) as late:
        _file(qualified, did)
    assert late.value.code == "window_closed"


def test_a_first_park_is_not_open_to_appeal_but_a_second_is(qualified: Any) -> None:  # noqa: F811
    db = qualified["db"]
    first = _round_decision(qualified, "parked", "NOT_FEASIBLE_NOW")
    row = db.execute("SELECT appeal_window_closes FROM decisions WHERE id = %s", (first,)).fetchone()
    assert row["appeal_window_closes"] is None
    with pytest.raises(ActionRefused) as refused:
        _file(qualified, first)
    assert refused.value.code == "not_appealable"
    assert appeals.appealable(db, qualified["cid"], "parked")  # the next park would be the second


def test_the_statement_is_checked_for_personal_data_and_links_are_web_addresses(qualified: Any) -> None:  # noqa: F811
    did = _round_decision(qualified, "declined", "LOW_VALUE")
    with pytest.raises(ActionRefused) as refused:
        _file(qualified, did, statement=STATEMENT + " Investor PAN QXRPK4821M.")
    assert refused.value.code == "personal_data"
    with pytest.raises(ActionRefused) as bad_link:
        _file(qualified, did, links=["file:///etc/passwd"])
    assert bad_link.value.code == "links_must_be_web_addresses"
    assert not qualified["db"].execute("SELECT 1 FROM appeals").fetchone()


def test_overturning_a_preliminary_decline_sends_an_invitation(qualified: Any) -> None:  # noqa: F811
    db = qualified["db"]
    did = _round_decision(qualified, "declined", "LOW_VALUE")
    aid = _file(qualified, did)["appeal_id"]
    chair = str(db.execute("SELECT panel[1] AS c FROM appeals WHERE id = %s", (aid,)).fetchone()["c"])
    out = appeals.decide(db, aid, chair, {"outcome": "overturned", "reasons": REASONS})
    assert out["stage"] == "shortlisted"
    pres = db.execute("SELECT state FROM presentations WHERE cluster_id = %s", (qualified["cid"],)).fetchone()
    assert pres["state"] == "invited"


def test_overturning_a_decision_after_the_presentation_returns_it_to_the_chair(qualified: Any) -> None:  # noqa: F811
    db = qualified["db"]
    pid = _held(qualified)
    for m in [qualified["chair"], *qualified["members"]]:
        decide.committee_act(db, pid, m, {"action": "assess", "vote": "decline",
                                          "scores": {d: 2 for d in rounds.scorecard()["dimensions"]}})  # fmt: skip
    decide.committee_act(db, pid, qualified["chair"], {"action": "collate"})
    first = decide.committee_act(db, pid, qualified["chair"], {
        "action": "decide", "outcome": "declined", "reason_code": "LOW_VALUE",
        "plain_reason": "The committee does not see enough value for KFintech in this right now.",
        "what_would_change": "Evidence that more branches face it."})["decision_id"]  # fmt: skip
    aid = _file(qualified, first)["appeal_id"]
    a = db.execute("SELECT heard_by, panel FROM appeals WHERE id = %s", (aid,)).fetchone()
    assert a["heard_by"] == "panel" and qualified["chair"] not in {str(p) for p in a["panel"]}
    appeals.decide(db, aid, str(a["panel"][0]), {"outcome": "overturned", "reasons": REASONS})
    assert db.execute("SELECT state FROM presentations WHERE id = %s", (pid,)).fetchone()["state"] == "held"
    with pytest.raises(ActionRefused) as again_declined:
        decide.committee_act(db, pid, qualified["chair"], {
            "action": "decide", "outcome": "declined", "reason_code": "LOW_VALUE",
            "plain_reason": "The committee still does not see enough value in this right now.",
            "what_would_change": "Evidence that more branches face it."})  # fmt: skip
    assert again_declined.value.code == "overturned_on_appeal"
    # Picked although the original votes were to decline: the panel overturned them (§4.12 step 4).
    again = decide.committee_act(db, pid, qualified["chair"], {
        "action": "decide", "outcome": "picked", "route": "build", "sponsor_id": qualified["members"][0],
        "plain_reason": "The appeal panel found the problem reaches every branch; it is picked this cycle."})  # fmt: skip
    assert again["decision_id"] != first and again["outcome"] == "picked"
    view = decide.committee_view(db, pid, qualified["members"][0])
    assert view is not None and view["decision"]["id"] == again["decision_id"]  # the latest decision shows


def test_a_lob_committee_decision_is_heard_by_the_core_committee(qualified: Any) -> None:  # noqa: F811
    db = qualified["db"]
    _qualify(qualified)
    db.execute(
        "UPDATE clusters SET route_to = 'lob', route_lob = 'LOB-mf' WHERE id = %s", (qualified["cid"],)
    )
    lob = [_user(db, "lob_committee")[0] for _ in range(2)]
    for u in lob:
        db.execute(
            "UPDATE role_grants SET scope_id = 'LOB-mf' WHERE user_id = %s AND role = 'lob_committee'", (u,)
        )
    rid = str(rounds.open_cycle(db, qualified["chair"], {"presentation_slots": 8})["rounds"][0])
    assert db.execute("SELECT body FROM scoring_rounds WHERE id = %s", (rid,)).fetchone()["body"] == "lob"
    band = db.execute("SELECT suggested_band FROM scoring_rounds WHERE id = %s", (rid,)).fetchone()[
        "suggested_band"
    ]
    for u in lob:
        scores = {
            d: (band if d == "financial_value" and band else 1) for d in rounds.scorecard()["dimensions"]
        }
        rounds.act(db, rid, u, {"action": "score", "scores": scores})
    rounds.act(db, rid, lob[0], {"action": "decide", "outcome": "declined", "reason_code": "OUT_OF_SCOPE",
                                 "note": "This sits outside the programme for this line of business."})  # fmt: skip
    did = str(db.execute("SELECT id FROM decisions WHERE round_id = %s", (rid,)).fetchone()["id"])
    aid = _file(qualified, did)["appeal_id"]
    a = db.execute("SELECT heard_by, panel FROM appeals WHERE id = %s", (aid,)).fetchone()
    core = {qualified["chair"], *qualified["members"]}
    assert a["heard_by"] == "core_committee" and {str(p) for p in a["panel"]} == core


def test_the_repo_gets_the_appeal_linked_from_the_decision_and_the_counts(qualified: Any) -> None:  # noqa: F811
    db = qualified["db"]
    did = _round_decision(qualified, "declined", "LOW_VALUE")
    aid = _file(qualified, did)["appeal_id"]
    chair = str(db.execute("SELECT panel[1] AS c FROM appeals WHERE id = %s", (aid,)).fetchone()["c"])
    appeals.decide(db, aid, chair, {"outcome": "upheld", "reasons": REASONS})
    writer = RepoWriter(helpers.settings_for(qualified["repo"], qualified["database"]))
    assert writer.acquire()
    try:
        writer.run_once()
    finally:
        writer.release()
    repo = qualified["repo"]
    year = aid.split("-")[1]
    afile, dfile = repo / "appeals" / year / f"{aid}.md", repo / "decisions" / year / f"{did}.md"
    for f in (afile, dfile):
        doc = parse(f.read_text(encoding="utf-8"))
        assert not [
            i for i in check_concept_meta(doc.meta or {}, str(f.relative_to(repo))) if i.level == "error"
        ]
    assert parse(afile.read_text(encoding="utf-8")).meta["kfin"]["outcome"] == "upheld"
    assert f"[{aid}](../../appeals/{year}/{aid}.md), upheld" in dfile.read_text(encoding="utf-8")
    assert "A preliminary review" in dfile.read_text(encoding="utf-8")
    index = (repo / "appeals" / "index.md").read_text(encoding="utf-8")
    assert (
        "| The core committee | fewer than 5 | 0 | fewer than 5 | 0 | 0 |" in index
    )  # small counts suppressed
    names = [r["name"] for r in db.execute("SELECT name FROM users").fetchall()]
    assert not any(n in afile.read_text(encoding="utf-8") + index for n in names)


def test_appeal_messages_render_for_the_panel_and_the_colleagues(qualified: Any, seeded_rules: None) -> None:  # noqa: F811
    from comms.route import route
    from comms.send import message_for

    db = qualified["db"]
    db.execute("TRUNCATE notifications CASCADE")
    did = _round_decision(qualified, "declined", "LOW_VALUE")
    aid = _file(qualified, did)["appeal_id"]
    chair = str(db.execute("SELECT panel[1] AS c FROM appeals WHERE id = %s", (aid,)).fetchone()["c"])
    appeals.decide(db, aid, chair, {"outcome": "upheld", "reasons": REASONS})
    for j in db.execute("SELECT payload FROM jobs WHERE type = 'comms.route' ORDER BY id").fetchall():
        route(db, j["payload"]["event"], dict(j["payload"].get("refs") or {}))
    rows = db.execute("SELECT * FROM notifications WHERE channel = 'email'").fetchall()
    assert {r["event"] for r in rows} >= {"round.not_shortlisted", "appeal.filed", "appeal.decided"}
    for n in rows:
        subject, body, _ = message_for(db, str(n["user_id"]), n["event"], n["template"], n["payload"])
        assert "{{" not in subject + body, n["event"]
        if n["event"] == "round.not_shortlisted":
            assert "You can appeal this decision until" in body
        if n["event"] == "appeal.decided":
            assert "upheld" in body


def test_reports_count_without_naming_anyone(qualified: Any) -> None:  # noqa: F811
    db = qualified["db"]
    _round_decision(qualified, "declined", "LOW_VALUE")
    start, end = dt.datetime(2020, 1, 1, tzinfo=dt.UTC), dt.datetime(2100, 1, 1, tzinfo=dt.UTC)
    fair = reports.fairness(db, start, end)
    cal = reports.calibration(db, start, end)
    names = [r["name"] for r in db.execute("SELECT name FROM users").fetchall()]
    text = json.dumps(fair) + json.dumps(cal)
    assert not any(n in text for n in names)
    assert fair["by_lob"] and all(
        r["scored"] == "fewer than 5" or isinstance(r["scored"], int) for r in fair["by_lob"]
    )
    assert {r["dimension"] for r in cal["prescore_vs_committee"]} == set(rounds.scorecard()["dimensions"])
    assert all(
        r["mean_gap"] == "too few to show" for r in cal["prescore_vs_committee"]
    )  # one round: suppressed


def test_report_periods_are_whole_quarters_in_ist() -> None:
    now = dt.datetime(2026, 11, 10, 6, 0, tzinfo=dt.UTC)
    assert reports.current_quarter(now) == "2026-Q4"
    start, end = reports.period("2026-Q3", now)
    assert start == dt.datetime(2026, 6, 30, 18, 30, tzinfo=dt.UTC)  # 1 July 00:00 IST
    assert end == dt.datetime(2026, 9, 30, 18, 30, tzinfo=dt.UTC)
    assert reports.period(None, now)[1] == now  # the current quarter runs up to now
    assert reports.recent_quarters(3, now) == ["2026-Q4", "2026-Q3", "2026-Q2"]
    for bad in ("2026-13-01", "2026-Q5", "2027-Q1"):
        with pytest.raises(ValueError):
            reports.period(bad, now)


def test_links_are_checked_for_personal_data_too(qualified: Any) -> None:  # noqa: F811
    did = _round_decision(qualified, "declined", "LOW_VALUE")
    with pytest.raises(ActionRefused) as refused:
        _file(qualified, did, links=["https://intranet.example/report?pan=QXRPK4821M"])
    assert refused.value.code == "personal_data"


def test_only_the_latest_decision_can_be_appealed(qualified: Any) -> None:  # noqa: F811
    db = qualified["db"]
    did = _round_decision(qualified, "declined", "LOW_VALUE")
    db.execute(
        "INSERT INTO decisions (id, cluster_id, body, outcome, votes, members_present, decided_by, decided_at) "
        "SELECT 'DEC-2099-0001', cluster_id, body, 'picked', '{}', 0, decided_by, decided_at + interval '1 day' "
        "FROM decisions WHERE id = %s",
        (did,),
    )
    with pytest.raises(ActionRefused) as refused:
        _file(qualified, did)
    assert refused.value.code == "superseded"


def test_the_next_member_records_the_outcome_if_the_chair_cannot(qualified: Any) -> None:  # noqa: F811
    db = qualified["db"]
    did = _round_decision(qualified, "declined", "LOW_VALUE")
    aid = _file(qualified, did)["appeal_id"]
    panel = [
        str(p) for p in db.execute("SELECT panel FROM appeals WHERE id = %s", (aid,)).fetchone()["panel"]
    ]
    db.execute("UPDATE users SET active = false WHERE id = %s", (panel[0],))  # the chair has left
    assert appeals.panel_view(db, aid, panel[1])["i_chair"]
    assert appeals.decide(db, aid, panel[1], {"outcome": "upheld", "reasons": REASONS})["stage"] == "declined"


def test_rotation_keeps_a_member_who_did_not_vote_for_the_outcome(qualified: Any) -> None:  # noqa: F811
    db = qualified["db"]
    pid = _held(qualified)
    for m in [qualified["chair"], *qualified["members"]]:
        decide.committee_act(db, pid, m, {"action": "assess", "vote": "decline",
                                          "scores": {d: 2 for d in rounds.scorecard()["dimensions"]}})  # fmt: skip
    decide.committee_act(db, pid, qualified["chair"], {"action": "collate"})
    did = decide.committee_act(db, pid, qualified["chair"], {
        "action": "decide", "outcome": "declined", "reason_code": "LOW_VALUE",
        "plain_reason": "The committee does not see enough value for KFintech in this right now.",
        "what_would_change": "Evidence that more branches face it."})["decision_id"]  # fmt: skip
    newcomers = [
        _user(db, "core_committee")[0] for _ in range(2)
    ]  # joined after the vote: did not vote decline
    aid = _file(qualified, did)["appeal_id"]
    panel = {
        str(p) for p in db.execute("SELECT panel FROM appeals WHERE id = %s", (aid,)).fetchone()["panel"]
    }
    assert len(panel) == 3 and qualified["chair"] not in panel and panel & set(newcomers)


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
    # The second park can still be appealed; the first never could be.
    assert {d["decision_id"] for d in appeals.mine(db, _owner(qualified)) if d["can_appeal"]} == {second}
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


def test_a_group_under_appeal_waits_for_the_panel(qualified: Any) -> None:  # noqa: F811
    db = qualified["db"]
    _round_decision(qualified, "parked", "NOT_FEASIBLE_NOW")
    second = _park_again(qualified)
    _file(qualified, second)
    out = rounds.open_cycle(db, qualified["chair"], {"presentation_slots": 8})
    assert out["returned"] == [] and out["archived"] == [] and out["rounds"] == []
    assert _stage(qualified) == ("appealed", None)  # the panel decides what happens next
