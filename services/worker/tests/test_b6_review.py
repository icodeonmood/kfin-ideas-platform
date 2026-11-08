"""Review desk actions (B6): AT-B6-03 (a decision writes the idea, one correction per changed field, the outbox
event; the idea file gets `verified: human:REV-…`, `status: stable` and a history line), AT-B6-04 (changing the
person's category or play needs a note, and the note reaches them), AT-B6-05 (a spam or abuse hold needs a
second reviewer), the question-and-answer loop with its timers, and "Disagree with this?" (AT-B6-09)."""

from __future__ import annotations

import secrets
from typing import Any

import pytest

from comms.send import message_for
from okf.frontmatter import parse
from repo_writer.writer import RepoWriter
from review import service
from scan import pipeline, save
from scan.confirm import confirm
from tests import helpers
from tests.conftest import MATCH_TEXT as TEXT
from tests.test_b4_scan import canvas, submitted

pytestmark = pytest.mark.stack


def _user(db: Any, role: str | None) -> str:
    tag = secrets.token_hex(3)
    u = db.execute(
        "INSERT INTO users (emp_id_hash, name, email, source) VALUES (%s, %s, %s, 'hr') RETURNING id",
        (f"test:{tag}", f"Reviewer {tag}", f"r.{tag}@kfintech.example"),
    ).fetchone()
    if role:
        db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, %s)", (u["id"], role))
    return str(u["id"])


@pytest.fixture
def desk(world: Any, company_repo: Any, test_database: str) -> Any:
    db = world
    db.execute("DELETE FROM jobs")
    owner = _user(db, None)
    code = f"CTR-{secrets.token_hex(3)}"
    db.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, owner))
    idea = submitted(db, canvas(TEXT + " (review)."))
    db.execute("UPDATE ideas SET contributor_code = %s, strength = 4 WHERE id = %s", (code, idea))
    assert pipeline.run(db, idea) == "done"
    idea_id = db.execute("SELECT idea_id FROM ideas WHERE id = %s", (idea,)).fetchone()["idea_id"]
    confirm(db, idea, idea_id, {})
    save.save(db, idea, code, {"choice": "new"})
    item = db.execute("SELECT id, proposal FROM review_items WHERE ref_id = %s", (idea_id,)).fetchone()
    return {"db": db, "idea": idea, "idea_id": idea_id, "item": int(item["id"]), "proposal": item["proposal"],
            "owner": owner, "code": code, "r1": _user(db, "reviewer"), "r2": _user(db, "reviewer"),
            "repo": company_repo, "database": test_database}  # fmt: skip


def test_accept_all_writes_what_section_4_3_says(desk: Any) -> None:
    db, item = desk["db"], desk["item"]
    timer = db.execute(
        "SELECT state FROM sla_timers WHERE entity_id = %s AND stage = 'review'", (str(item),)
    ).fetchone()
    assert timer["state"] == "running"
    out = service.act(db, item, desk["r1"], {"action": "decide"})
    assert out == {"state": "decided", "stage": "reviewed"}
    idea = db.execute(
        "SELECT stage, area_ids, lobs, scope FROM ideas WHERE id = %s", (desk["idea"],)
    ).fetchone()
    proposal = desk["proposal"]["system"]
    assert (
        idea["area_ids"] == proposal["areas"]
        and idea["lobs"] == proposal["lobs"]
        and idea["scope"] == proposal["scope"]
    )
    assert (
        db.execute("SELECT count(*) AS n FROM corrections WHERE review_item_id = %s", (item,)).fetchone()["n"]
        == 0
    )
    rev = db.execute("SELECT staff_code FROM users WHERE id = %s", (desk["r1"],)).fetchone()["staff_code"]
    assert rev.startswith("REV-")
    states = {r["stage"]: r["state"] for r in db.execute(
        "SELECT stage, state FROM sla_timers WHERE entity_id = %s", (str(item),)).fetchall()}  # fmt: skip
    assert states == {"review": "stopped", "veto_window": "running"}
    event = db.execute(
        "SELECT actor, payload FROM outbox WHERE aggregate_id = %s AND event_type = 'idea.reviewed'",
        (desk["idea_id"],),
    ).fetchone()
    assert event["actor"] == rev and event["payload"]["verified_by"] == rev

    # The repo writer turns it into the idea file: verified by the reviewer, stable, with a history line.
    writer = RepoWriter(helpers.settings_for(desk["repo"], desk["database"]))
    assert writer.acquire()
    try:
        writer.run_once()
    finally:
        writer.release()
    rel = db.execute("SELECT repo_path FROM ideas WHERE id = %s", (desk["idea"],)).fetchone()["repo_path"]
    doc = parse((desk["repo"] / rel).read_text(encoding="utf-8"))
    assert doc.meta["status"] == "stable" and doc.meta["verified"][0]["by"] == f"human:{rev}"
    assert doc.meta["kfin"]["areas"] == proposal["areas"]
    assert "reviewed" in doc.body and rev in doc.body


def test_edits_make_corrections_and_a_category_change_needs_a_note(desk: Any) -> None:
    db, item = desk["db"], desk["item"]
    with pytest.raises(service.ActionRefused) as no_note:
        service.act(db, item, desk["r1"], {"action": "decide", "category": "new_revenue"})
    assert no_note.value.code == "text_too_short"
    out = service.act(
        db, item, desk["r1"],
        {"action": "decide", "system": {"areas": ["AREA-technology"]}, "category": "new_revenue",
         "note": "This reads as a new paid service for AMCs"},
    )  # fmt: skip
    assert out["state"] == "decided"
    rows = db.execute(
        "SELECT field, final, note, card_embedding IS NOT NULL AS has_vec FROM corrections WHERE review_item_id = %s "
        "ORDER BY field",
        (item,),
    ).fetchall()
    assert [r["field"] for r in rows] == ["system.areas", "value.category"]
    assert all(r["has_vec"] for r in rows) and rows[1]["note"] == "This reads as a new paid service for AMCs"
    reviewed = next(
        r["payload"]["refs"]
        for r in db.execute("SELECT payload FROM jobs WHERE type = 'comms.route'").fetchall()
        if r["payload"]["event"] == "idea.reviewed"
    )
    _subject, body, _ = message_for(db, desk["owner"], "idea.reviewed", "reviewed", reviewed)
    assert "This reads as a new paid service for AMCs" in body  # the note reaches the submitter


def test_a_hold_needs_a_second_reviewer(desk: Any) -> None:
    db, item = desk["db"], desk["item"]
    assert (
        service.act(db, item, desk["r1"], {"action": "hold", "kind": "spam"})["state"]
        == "awaiting_second_reviewer"
    )
    with pytest.raises(service.ActionRefused) as same:
        service.confirm_hold(db, item, desk["r1"])
    assert same.value.code == "second_reviewer_needed"
    assert service.confirm_hold(db, item, desk["r2"])["stage"] == "declined"
    assert (
        db.execute("SELECT count(*) AS n FROM audit_log WHERE action LIKE 'review.hold_%%'").fetchone()["n"]
        == 2
    )


def test_question_answer_and_disagree(desk: Any) -> None:
    db, item = desk["db"], desk["item"]
    out = service.act(
        db, item, desk["r1"], {"action": "ask", "question": "Which branches see this the most?"}
    )
    assert out["stage"] == "needs_info"
    timers = {r["stage"]: r["state"] for r in db.execute(
        "SELECT stage, state FROM sla_timers WHERE entity_id IN (%s, %s)", (str(item), desk["idea_id"])).fetchall()}  # fmt: skip
    assert timers == {"review": "paused", "needs_info": "running"}
    q = next(
        r["payload"]["refs"]
        for r in db.execute("SELECT payload FROM jobs WHERE type = 'comms.route'").fetchall()
        if r["payload"]["event"] == "idea.question"
    )
    _s, body, _ = message_for(db, desk["owner"], "idea.question", "question", q)
    assert "Which branches see this the most?" in body
    assert service.answer(db, desk["idea"], desk["code"], "Mostly Hyderabad and Pune")["stage"] == "scanned"
    timers = {r["stage"]: r["state"] for r in db.execute(
        "SELECT stage, state FROM sla_timers WHERE entity_id IN (%s, %s)", (str(item), desk["idea_id"])).fetchall()}  # fmt: skip
    assert timers == {"review": "running", "needs_info": "stopped"}
    with pytest.raises(service.ActionRefused):
        service.answer(db, desk["idea"], desk["code"], "again")  # no open question now

    with pytest.raises(service.ActionRefused) as early:  # nothing has been decided yet
        service.disagree(db, desk["idea"], desk["code"], "The desk missed that this affects SIF too")
    assert early.value.code == "nothing_to_disagree_with"
    service.act(db, item, desk["r1"], {"action": "decide"})
    d = service.disagree(db, desk["idea"], desk["code"], "The desk missed that this affects SIF too")
    row = db.execute("SELECT item_type, ref_id FROM review_items WHERE id = %s", (d["item_id"],)).fetchone()
    assert row == {"item_type": "disagreement", "ref_id": desk["idea_id"]}
    with pytest.raises(service.ActionRefused) as again:  # one open disagreement per idea
        service.disagree(db, desk["idea"], desk["code"], "And it affects NPS as well, I think")
    assert again.value.code == "already_raised"


def test_core_committee_veto_within_the_window(desk: Any) -> None:

    from review import veto as v

    db, item = desk["db"], desk["item"]
    member = _user(db, "core_committee")
    service.act(db, item, desk["r1"], {"action": "decide"})
    listed = next(d for d in v.desk_decisions(db)["decisions"] if d["item_id"] == item)
    assert listed["veto_open"] and listed["decided_by"].startswith("REV-")
    with pytest.raises(service.ActionRefused) as short:
        v.veto(db, item, member, "no")
    assert short.value.code == "text_too_short"
    out = v.veto(db, item, member, "The committee wants this grouped with the SIF work")
    assert out == {"state": "open", "assigned_to": member}
    assert db.execute(
        "SELECT 1 FROM audit_log WHERE action = 'review.veto' AND entity = %s", (f"review_item:{item}",)
    ).fetchone()
    assert db.execute(
        "SELECT 1 FROM corrections WHERE review_item_id = %s AND field = 'desk_decision'", (item,)
    ).fetchone()
    with pytest.raises(service.ActionRefused) as desk_blocked:
        service.act(db, item, desk["r1"], {"action": "decide"})
    assert desk_blocked.value.code == "assigned_to_someone_else"
    db.execute("DELETE FROM jobs WHERE type = 'comms.route'")
    service.act(db, item, member, {"action": "decide", "system": {"areas": ["AREA-technology"]}})
    events = [
        r["payload"]["event"]
        for r in db.execute("SELECT payload FROM jobs WHERE type = 'comms.route'").fetchall()
    ]
    assert events == ["idea.reconsidered"]  # only the final outcome, saying it was reconsidered
    windows = db.execute(
        "SELECT count(*) AS n FROM sla_timers WHERE entity_id = %s AND stage = 'veto_window' AND state = 'running'",
        (str(item),),
    ).fetchone()["n"]
    assert windows == 0  # a member's final call is not vetoed again


def test_veto_after_the_window_answers_409(desk: Any) -> None:
    import datetime as dt

    from review import veto as v

    db, item = desk["db"], desk["item"]
    member = _user(db, "core_committee")
    service.act(db, item, desk["r1"], {"action": "decide"})
    due = db.execute(
        "SELECT due_at FROM sla_timers WHERE entity_id = %s AND stage = 'veto_window'", (str(item),)
    ).fetchone()["due_at"]
    with pytest.raises(service.ActionRefused) as late:
        v.veto(db, item, member, "Reconsider this decision please", now=due + dt.timedelta(minutes=1))
    assert late.value.code == "veto_window_closed"


# --- B6 review regressions -------------------------------------------------------------------------------------


def test_nothing_else_changes_while_a_hold_waits(desk: Any) -> None:
    db, item = desk["db"], desk["item"]
    service.act(db, item, desk["r1"], {"action": "hold", "kind": "abuse"})
    for body in (
        {"action": "decide"},
        {"action": "ask", "question": "Can you say which team this is?"},
        {"action": "redirect", "kind": "it_ticket"},
        {"action": "hold", "kind": "spam"},
    ):
        with pytest.raises(service.ActionRefused) as locked:
            service.act(db, item, desk["r2"], body)
        assert locked.value.code == "awaiting_hold_confirmation", body["action"]
    assert (
        db.execute("SELECT stage FROM ideas WHERE id = %s", (desk["idea"],)).fetchone()["stage"] == "scanned"
    )


def test_nobody_reviews_or_vetoes_their_own_idea(desk: Any) -> None:
    from review import veto as v

    db, item = desk["db"], desk["item"]
    db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, 'reviewer')", (desk["owner"],))
    db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, 'core_committee')", (desk["owner"],))
    with pytest.raises(service.ActionRefused) as own:
        service.act(db, item, desk["owner"], {"action": "decide"})
    assert (own.value.status, own.value.code) == (409, "own_idea")
    service.act(db, item, desk["r1"], {"action": "decide"})
    with pytest.raises(service.ActionRefused) as own_veto:
        v.veto(db, item, desk["owner"], "I would like this looked at again")
    assert own_veto.value.code == "own_idea"
    audits = db.execute(
        "SELECT after FROM audit_log WHERE action = 'review.own_idea_refused' AND entity = %s ORDER BY id",
        (f"idea:{desk['idea_id']}",),
    ).fetchall()
    assert [a["after"]["action"] for a in audits] == ["decide", "veto"]  # kept although the work was undone
    assert (
        db.execute("SELECT state FROM review_items WHERE id = %s", (item,)).fetchone()["state"] == "decided"
    )


def test_decisions_only_use_known_tags_and_choices(desk: Any) -> None:
    db, item = desk["db"], desk["item"]
    for body, code in (
        ({"system": {"areas": ["AREA-made-up"]}}, "unknown_areas"),
        ({"system": {"lobs": ["LOB-nowhere"]}}, "unknown_lobs"),
        ({"system": {"scope": "galaxy"}}, "bad_scope"),
        ({"category": "free_money", "note": "Changed for testing only"}, "bad_category"),
        ({"play": "moonshot", "note": "Changed for testing only"}, "bad_play"),
        ({"system": "AREA-technology"}, "bad_request"),
    ):
        with pytest.raises(service.ActionRefused) as bad:
            service.act(db, item, desk["r1"], {"action": "decide", **body})
        assert bad.value.code == code
    assert (
        db.execute("SELECT state FROM review_items WHERE id = %s", (item,)).fetchone()["state"] != "decided"
    )


def test_a_decision_ends_the_wait_for_an_answer(desk: Any) -> None:
    db, item = desk["db"], desk["item"]
    service.act(db, item, desk["r1"], {"action": "ask", "question": "Which branches see this the most?"})
    service.act(db, item, desk["r1"], {"action": "redirect", "kind": "it_ticket"})
    states = {
        r["stage"]: r["state"]
        for r in db.execute(
            "SELECT stage, state FROM sla_timers WHERE entity_id IN (%s, %s) AND stage IN ('review', 'needs_info')",
            (str(item), desk["idea_id"]),
        ).fetchall()
    }
    assert states == {"review": "stopped", "needs_info": "stopped"}  # no withdrawal message can follow
