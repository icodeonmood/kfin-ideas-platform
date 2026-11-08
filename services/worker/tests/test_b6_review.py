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

    d = service.disagree(db, desk["idea"], desk["code"], "The desk missed that this affects SIF too")
    row = db.execute("SELECT item_type, ref_id FROM review_items WHERE id = %s", (d["item_id"],)).fetchone()
    assert row == {"item_type": "disagreement", "ref_id": desk["idea_id"]}
