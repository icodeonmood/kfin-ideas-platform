"""Solution write-ups other teams can adopt (BLD-133): the owner drafts and submits, the named sponsor (never the
submitter) approves or sends back, approval queues `solution.published` with IDs only, and the repo writer writes
`solutions/SOL-NNNN.md` from the sealed record. Synthetic people and text only."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from core import killswitch
from delivery import service, writeups
from okf.frontmatter import parse
from okf.validate import check_concept_meta
from repo_writer.render_docs import doc_index_line, render_solution
from tests import helpers, test_delivery
from tests.test_delivery import approved
from tests.test_ones import refused

ones_db = test_delivery.ones_db
cast = test_delivery.cast
crew = test_delivery.crew

PARTS = {
    "title": "Bank detail check before payouts",
    "what_it_does": "Flags likely-wrong bank details on payout files before they go to the bank, so fewer "
    "payouts bounce and fewer investors call the service centre.",
    "where_it_runs": "Mutual fund operations, payout desk, on the redemption file.",
    "result": "Bounced payouts fell from about forty a week to under ten in the first month.",
    "how_to_adopt": "Talk to the payout desk lead. It needs the payout file layout and a day of set-up.",
}


def test_the_solution_file_follows_the_okf_rules_and_escapes_text() -> None:
    at = dt.datetime(2026, 12, 18, 10, 0, tzinfo=dt.UTC)
    parts = {**PARTS, "result": "<script>x</script> [a](javascript:1) fell sharply"}
    text = render_solution("SOL-0007", parts, {"approved_at": at, "owner_team": "LOB-mf", "lobs": ["LOB-mf"],
                                               "areas": ["AREA-process"], "source_cluster": None,
                                               "shipped_on": "2026-12-01", "delivery_id": 3})  # fmt: skip
    doc = parse(text)
    assert not [i for i in check_concept_meta(doc.meta or {}, "solutions/SOL-0007.md") if i.level == "error"]
    assert (
        doc.meta["kfin"]["id"] == "SOL-0007" and doc.meta["verified"][0]["by"] == "process:sponsor-approval"
    )
    assert "<script>" not in text and "[a](javascript" not in text  # brackets escaped: never a link
    assert doc_index_line("SOL-0007", "A [title]") == "- [SOL-0007.md](SOL-0007.md) — A \\[title\\]"


def _shipped(db: Any, crew: dict[str, str]) -> int:
    _idea, did = approved(db, crew)
    db.execute("UPDATE deliveries SET state = 'shipped', shipped_at = now() WHERE id = %s", (did,))
    return did


@pytest.fixture
def repo_settings(company_repo: Any, test_database: str, monkeypatch: pytest.MonkeyPatch) -> Any:
    settings = helpers.settings_for(company_repo, test_database)
    monkeypatch.setattr(writeups, "get_settings", lambda: settings)
    return settings, test_database


@pytest.mark.stack
def test_owner_drafts_sponsor_approves_and_the_writer_publishes(
    ones_db: Any, crew: dict[str, str], repo_settings: Any, company_repo: Any
) -> None:
    from repo_writer.writer import RepoWriter

    db = ones_db
    did = _shipped(db, crew)
    refused("owner_only", writeups.save, db, crew["sponsor"], did, PARTS)
    refused("text_too_short:title", writeups.save, db, crew["owner"], did, {**PARTS, "title": "x"})
    writeups.save(db, crew["owner"], did, PARTS)
    stored = db.execute(
        "SELECT parts_encrypted FROM solution_writeups WHERE delivery_id = %s", (did,)
    ).fetchone()
    assert b"payout desk" not in bytes(stored["parts_encrypted"])  # sealed at rest
    refused("not_submitted", writeups.approve, db, crew["sponsor"], did)
    writeups.submit(db, crew["owner"], did)
    refused("writeup_locked", writeups.save, db, crew["owner"], did, PARTS)
    refused("sponsor_only", writeups.approve, db, crew["owner"], did)
    view = writeups.view(db, service._delivery(db, did), crew["sponsor"], {"sponsor"})
    assert view and view["can_decide"] and view["parts"]["title"] == PARTS["title"]

    killswitch.set_switch(db, "solutions.publish", "off", reason="test: publish paused", actor="test")
    killswitch.clear_cache()
    try:
        refused("publishing_paused", writeups.approve, db, crew["sponsor"], did)
    finally:
        killswitch.set_switch(db, "solutions.publish", "on", reason="test: publish back", actor="test")
        killswitch.clear_cache()
    out = writeups.approve(db, crew["sponsor"], did)
    sol = out["solution_id"]
    event = db.execute(
        "SELECT actor, payload FROM outbox WHERE event_type = 'solution.published' AND aggregate_id = %s",
        (sol,),
    ).fetchone()
    assert set(event["payload"]) == {"writeup_id"}  # IDs only: the writer reads the text from the database
    assert event["actor"] == "process:solution-approval"  # the outbox CHECK allows no user IDs (BLD-143)
    who = db.execute(
        "SELECT actor FROM audit_log WHERE action = 'delivery.writeup_approved' AND entity = %s ORDER BY id DESC",
        (f"delivery:{did}",),
    ).fetchone()
    assert who["actor"] == f"user:{crew['sponsor']}"  # the person is on record in audit_log

    writer = RepoWriter(helpers.settings_for(company_repo, repo_settings[1]))
    assert writer.acquire()
    try:
        writer.run_once()
    finally:
        writer.release()
    text = (company_repo / "solutions" / f"{sol}.md").read_text(encoding="utf-8")
    assert PARTS["title"] in text and "## How another team can adopt it" in text
    assert f"[{sol}.md]({sol}.md)" in (company_repo / "solutions" / "index.md").read_text(encoding="utf-8")
    row = db.execute(
        "SELECT repo_path, repo_commit FROM solution_writeups WHERE delivery_id = %s", (did,)
    ).fetchone()
    assert row["repo_path"] == f"solutions/{sol}.md" and row["repo_commit"]


@pytest.mark.stack
def test_the_submitter_never_approves_their_own_writeup_and_send_back_reopens_it(
    ones_db: Any, crew: dict[str, str], repo_settings: Any
) -> None:
    db = ones_db
    did = _shipped(db, crew)
    db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, 'admin')", (crew["sponsor"],))
    writeups.save(db, crew["sponsor"], did, PARTS)  # an admin may draft
    writeups.submit(db, crew["sponsor"], did)
    refused("own_submission", writeups.approve, db, crew["sponsor"], did)  # separation of duties (BLD-126)
    refused("own_submission", writeups.send_back, db, crew["sponsor"], did)


@pytest.mark.stack
def test_send_back_lets_the_owner_change_it_and_drafts_wait_for_shipping(
    ones_db: Any, crew: dict[str, str], repo_settings: Any
) -> None:
    db = ones_db
    _idea, early = approved(db, crew)
    refused("owner_only", writeups.save, db, crew["owner"], early, PARTS)  # not shipped yet
    did = _shipped(db, crew)
    writeups.save(db, crew["owner"], did, PARTS)
    writeups.submit(db, crew["owner"], did)
    assert writeups.send_back(db, crew["sponsor"], did)["state"] == "sent_back"
    view = writeups.view(db, service._delivery(db, did), crew["owner"], set())
    assert view and view["can_edit"] and not view["can_submit"]
    writeups.save(
        db, crew["owner"], did, {**PARTS, "result": "Bounced payouts fell by three quarters in a month."}
    )
    assert writeups.submit(db, crew["owner"], did)["state"] == "submitted"
    routed = [
        r["payload"]["event"]
        for r in db.execute("SELECT payload FROM jobs WHERE type = 'comms.route' ORDER BY id").fetchall()
    ]
    assert routed.count("delivery.writeup_submitted") == 2 and "delivery.writeup_decided" in routed


@pytest.mark.stack
def test_nobody_who_wrote_any_of_it_approves_it(
    ones_db: Any, crew: dict[str, str], repo_settings: Any
) -> None:
    """BLD-142: an admin who is also the sponsor edited the owner's draft; the owner submits; the sponsor still may
    not approve, because they wrote part of it."""
    db = ones_db
    did = _shipped(db, crew)
    db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, 'admin')", (crew["sponsor"],))
    writeups.save(db, crew["owner"], did, PARTS)
    writeups.save(db, crew["sponsor"], did, {**PARTS, "title": "Bank detail check before every payout"})
    writeups.save(
        db, crew["owner"], did, PARTS
    )  # the owner has the last word, but the sponsor still wrote part
    writeups.submit(db, crew["owner"], did)
    refused("own_submission", writeups.approve, db, crew["sponsor"], did)
    view = writeups.view(db, service._delivery(db, did), crew["sponsor"], {"sponsor", "admin"})
    assert view and not view["can_decide"]


def _approved_writeup(db: Any, crew: dict[str, str]) -> tuple[int, str, int]:
    did = _shipped(db, crew)
    writeups.save(db, crew["owner"], did, PARTS)
    writeups.submit(db, crew["owner"], did)
    out = writeups.approve(db, crew["sponsor"], did)
    w = db.execute("SELECT id FROM solution_writeups WHERE delivery_id = %s", (did,)).fetchone()
    return did, out["solution_id"], int(w["id"])


def _run_writer(company_repo: Any, test_database: str) -> list[Any]:
    from repo_writer.writer import RepoWriter

    writer = RepoWriter(helpers.settings_for(company_repo, test_database))
    assert writer.acquire()
    try:
        return writer.run_once()
    finally:
        writer.release()


@pytest.mark.stack
def test_a_hand_added_file_dead_letters_the_event_and_later_writes_carry_on(
    ones_db: Any, crew: dict[str, str], repo_settings: Any, company_repo: Any
) -> None:
    """BLD-143, BLD-146: the writer never overwrites a file the product team added by hand, and that event never
    blocks the queue: it is dead-lettered with an alert, and the next event is written."""
    db = ones_db
    _did, sol, _wid = _approved_writeup(db, crew)
    (company_repo / "solutions" / f"{sol}.md").write_text("hand-written\n", encoding="utf-8")
    later = helpers.insert_idea(db, stage="scanned")
    helpers.insert_event(db, later)
    _run_writer(company_repo, repo_settings[1])
    row = db.execute(
        "SELECT id, dead_lettered_at, last_error, committed_at FROM outbox WHERE aggregate_id = %s", (sol,)
    ).fetchone()
    assert (
        row["dead_lettered_at"] is not None
        and row["last_error"] == "doc_exists"
        and row["committed_at"] is None
    )
    assert (company_repo / "solutions" / f"{sol}.md").read_text() == "hand-written\n"
    assert db.execute(
        "SELECT 1 FROM audit_log WHERE action = 'alert.repo_writer_dead_letter' AND entity = %s",
        (f"outbox:{row['id']}",),
    ).fetchone()
    committed = db.execute("SELECT committed_at FROM outbox WHERE aggregate_id = %s", (later,)).fetchone()
    assert committed["committed_at"] is not None  # the queue moved on


@pytest.mark.stack
def test_personal_data_is_refused_at_approval_and_dead_lettered_if_it_slips_in_later(
    ones_db: Any, crew: dict[str, str], repo_settings: Any, company_repo: Any
) -> None:
    import generators as g

    from ones.text import seal_json

    db = ones_db
    pan = g.pan(g.default_rng())
    # At approval: the writer's own check runs first, so a write-up it would refuse is refused there.
    did = _shipped(db, crew)
    writeups.save(db, crew["owner"], did, PARTS)
    writeups.submit(db, crew["owner"], did)
    w = db.execute("SELECT id FROM solution_writeups WHERE delivery_id = %s", (did,)).fetchone()
    db.execute(  # what slipping past the save checks would look like
        "UPDATE solution_writeups SET parts_encrypted = %s WHERE id = %s",
        (seal_json({**PARTS, "result": f"Fewer bounces for investor {pan}."}, f"writeup:{w['id']}"), w["id"]),
    )
    refused("writeup_needs_changes", writeups.approve, db, crew["sponsor"], did)
    # After approval: the record changed under the writer; it dead-letters instead of retrying forever.
    _did2, sol, wid = _approved_writeup(db, crew)
    db.execute(
        "UPDATE solution_writeups SET parts_encrypted = %s WHERE id = %s",
        (seal_json({**PARTS, "result": f"Fewer bounces for investor {pan}."}, f"writeup:{wid}"), wid),
    )
    _run_writer(company_repo, repo_settings[1])
    row = db.execute(
        "SELECT dead_lettered_at, last_error FROM outbox WHERE aggregate_id = %s", (sol,)
    ).fetchone()
    assert row["dead_lettered_at"] is not None and row["last_error"] == "personal_data_in_doc"
    assert not (company_repo / "solutions" / f"{sol}.md").exists()
