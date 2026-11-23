"""L-TEAMUP and L-MERGE.request on the database: asking, withdrawing, the lead's three answers and what each does,
closing with the idea, leaving and removal, and a draft's merge request (V-ACC.teamup/4–6 server side,
V-ACC.similar/3–8, L-TEAMUP.rules/1, /4, /6, /11, states, L-MERGE.request/2–8, L-MERGE.effects)."""

from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from typing import Any

import pytest

from core.db import Conn
from onepc.context import open_text
from teamup import adapters, crew, drafts, inbox_ops, merging, requests
from teamup.store import Refused
from tests import f_teamup_fixtures as f

NOTE = "I take these calls at our Hyderabad branch every day, about 40 a day, and most are about R07."


@pytest.fixture
def db(db: Conn) -> Iterator[Conn]:
    """The shared `db` fixture, plus clean-up: every person, idea, request and crew these tests made is removed
    when the test ends, so no user is left behind in the shared test database for a later test (the seed's HR
    import refuses while active users are there)."""
    yield db
    f.clean(db)


@pytest.fixture
def inbox(monkeypatch: pytest.MonkeyPatch) -> f.Inbox:
    return f.record_inbox(monkeypatch)


@pytest.fixture
def cast(db: Conn) -> dict[str, Any]:
    ravi = f.person(db, "Ravi Nair")
    kavya = f.person(db, "Kavya Menon")
    asha = f.person(db, "Asha Sen", city="Pune", area="Operations")
    lead_idea = f.idea(db, ravi, title="Rejection SMS codes confuse investors")
    f.crew(db, lead_idea, asha)
    kavya_idea = f.idea(db, kavya, title="Investors call to ask why a redemption was rejected")
    return {"ravi": ravi, "kavya": kavya, "asha": asha, "lead": lead_idea, "mine": kavya_idea}


def _refused(fn: Any, *args: Any, **kw: Any) -> Refused:
    with pytest.raises(Refused) as exc:
        fn(*args, **kw)
    return exc.value


def _send(db: Conn, c: dict[str, Any], brought: list[str] | None = None, note: str = NOTE) -> dict[str, Any]:
    return requests.send(db, c["lead"]["idea_id"], c["kavya"]["id"],
                         {"note": note, "brought_idea_ids": brought or []})  # fmt: skip


# --- L-TEAMUP.rules/1, /2, /4 ----------------------------------------------------------------------------------
def test_L_TEAMUP_rules_1_who_can_ask(db: Conn, cast: dict[str, Any], inbox: f.Inbox) -> None:
    lead_ref = cast["lead"]["idea_id"]
    body = {"note": NOTE, "brought_idea_ids": []}
    assert _refused(requests.send, db, lead_ref, cast["ravi"]["id"], body).code == "already_on_crew"
    assert _refused(requests.send, db, lead_ref, cast["asha"]["id"], body).code == "already_on_crew"
    for status in ("merged", "not_picked", "not_now"):
        closed = f.idea(db, cast["ravi"], status=status)
        r = _refused(requests.send, db, closed["idea_id"], cast["kavya"]["id"], body)
        assert (r.status, r.code) == (409, "idea_closed")
    # a withdrawn idea is not found for Kavya, who never asked to join it (BLD-E011, L-SUBMIT.withdraw/2)
    withdrawn = f.idea(db, cast["ravi"], status="withdrawn")
    r = _refused(requests.send, db, withdrawn["idea_id"], cast["kavya"]["id"], body)
    assert (r.status, r.code, r.message) == (404, "not_found", "We couldn’t find that.")
    draft = f.draft(db, cast["ravi"])
    assert _refused(requests.send, db, str(draft["id"]), cast["kavya"]["id"], body).status == 404
    assert (
        _refused(requests.send, db, lead_ref, cast["kavya"]["id"], {"note": "x" * 29}).code
        == "note_too_short"
    )
    assert inbox.posts == []


def test_L_TEAMUP_rules_2_nothing_is_brought_by_default_and_only_own_open_ideas_can_be(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    sent = _send(db, cast)
    assert sent["brought"] == [] and sent["state"] == "sent"
    requests.withdraw(db, sent["id"], cast["kavya"]["id"])
    asha_idea = f.idea(db, cast["asha"])
    r = _refused(_send, db, cast, [asha_idea["idea_id"]])
    assert (r.code, r.field) == ("brought_invalid", "brought_idea_ids")
    closed = f.idea(db, cast["kavya"], status="withdrawn")
    assert _refused(_send, db, cast, [closed["idea_id"]]).code == "brought_invalid"


def test_draft_note_is_pre_filled_from_the_closest_own_idea_and_lists_what_can_be_brought(
    db: Conn, cast: dict[str, Any]
) -> None:
    older = f.idea(db, cast["kavya"], title="Older idea about forms", shared_at=f.at(2))
    f.similar(db, cast["lead"], older)
    f.idea(db, cast["kavya"], title="A closed one", status="not_picked")
    out = requests.draft_note(db, cast["lead"]["idea_id"], cast["kavya"]["id"])
    assert "“Older idea about forms”" in out["note"] and out["note"].startswith("I’m in Investor service")
    assert [o["title"] for o in out["own_ideas"]] == [
        "Investors call to ask why a redemption was rejected",
        "Older idea about forms",
    ]
    assert out["own_ideas"][0]["meta"].endswith(", with the review desk")
    assert out["lead"]["first_name"] == "Ravi" and out["min_chars"] == 30


def test_L_TEAMUP_rules_4_one_open_request_per_person_per_idea(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    first = _send(db, cast)
    again = _refused(_send, db, cast)
    assert (again.status, again.code, again.message) == (409, "already_requested", "Waiting for Ravi")
    requests.withdraw(db, first["id"], cast["kavya"]["id"])
    second = _send(db, cast)
    assert second["id"] != first["id"]
    assert inbox.resolved == [f"teamup_request:{first['id']}"]


def test_the_same_idempotency_key_returns_the_first_request(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    body = {"note": NOTE, "brought_idea_ids": []}
    a = requests.send(db, cast["lead"]["idea_id"], cast["kavya"]["id"], body, "key-0001-teamup")
    b = requests.send(db, cast["lead"]["idea_id"], cast["kavya"]["id"], body, "key-0001-teamup")
    assert a["id"] == b["id"] and len(inbox.of("teamup_request")) == 1
    # BLD-F026: the same key on another idea, or with other words, is refused, never answered with the first
    other = f.idea(db, cast["asha"])
    for ref, sent in ((other["idea_id"], body), (cast["lead"]["idea_id"], {**body, "note": NOTE + " More."})):
        r = _refused(requests.send, db, ref, cast["kavya"]["id"], sent, "key-0001-teamup")
        assert (r.status, r.code) == (409, "key_reused")
    draft = f.draft(db, cast["kavya"])
    r = _refused(drafts.ask, db, str(draft["id"]), cast["kavya"]["id"],
                 {"other_idea_id": other["idea_id"], "note": NOTE}, "key-0001-teamup")  # fmt: skip
    assert r.code == "key_reused"
    assert len(inbox.of("teamup_request")) == 1


# --- V-ACC.teamup/4–6 -------------------------------------------------------------------------------------------
def test_V_ACC_teamup_4_a_sent_request_reads_waiting_for_the_lead_with_withdraw(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    sent = _send(db, cast)
    assert sent["after"]["line"] == "Waiting for Ravi"
    mine = requests.my_state(db, cast["lead"]["idea_id"], cast["kavya"]["id"])
    assert mine["can_request"] is False and mine["why_not"] == "already_requested"
    assert mine["after"]["line"] == "Waiting for Ravi" and mine["after"]["action"]["label"] == "Withdraw"
    assert mine["request"]["note"] == NOTE and mine["request"]["id"] == sent["id"]
    requests.withdraw(db, sent["id"], cast["kavya"]["id"])
    back = requests.my_state(db, cast["lead"]["idea_id"], cast["kavya"]["id"])
    assert back["can_request"] is True and back["after"] is None and back["request"]["state"] == "withdrawn"
    # the lead's item carries IDs only, and is resolved on withdraw
    (item,) = inbox.of("teamup_request")
    assert item["recipients"] == [cast["ravi"]["id"]] and item["needs_you"] is True
    assert item["refs"] == {"request_id": sent["id"], "request": "teamup", "brought": 0}
    assert item["dedupe_key"] == f"teamup_request:{sent['id']}"
    assert [a.label for a in item["actions"]] == ["Decline", "Approve"]


def test_V_ACC_teamup_5_the_lead_sees_the_note_the_idea_brought_and_three_answers(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    sent = _send(db, cast, [cast["mine"]["idea_id"]])
    page = requests.read(db, sent["id"], cast["ravi"]["id"])
    assert page["note"] == NOTE and page["from"]["name"] == "Kavya Menon"
    (b,) = page["brought"]
    assert b["id"] == cast["mine"]["idea_id"] and b["byline"].startswith(
        "Kavya Menon, Investor service, Hyderabad."
    )
    assert b["summary"] == cast["mine"]["summary"]
    assert [a["label"] for a in page["answers"]] == ["Decline", "Team up only", "Merge it"]
    assert page["reader"]["kind"] == "Merge request"
    (item,) = inbox.of("teamup_request")
    assert item["refs"]["brought"] == 1 and [a.op for a in item["actions"]] == [
        "decline",
        "team_only",
        "merge",
    ]
    # nobody else can read it
    assert _refused(requests.read, db, sent["id"], cast["asha"]["id"]).status == 404


def test_V_ACC_teamup_6_merge_it(db: Conn, cast: dict[str, Any], inbox: f.Inbox) -> None:
    kavya_crew = f.person(db, "Pradeep Kumar")
    f.crew(db, cast["mine"], kavya_crew)
    db.execute(
        "INSERT INTO question_sets (idea_uuid, by_user_id, state, sent_at, due_at) VALUES (%s, %s, 'sent', now(), now())",
        (cast["mine"]["id"], cast["ravi"]["id"]),
    )
    sent = _send(db, cast, [cast["mine"]["idea_id"]])
    out = requests.answer(db, sent["id"], cast["ravi"]["id"], {"answer": "merge"})
    assert out["result"]["text"] == (
        "Merged. Kavya’s idea is now part of yours, and they are on your crew, credited. We’ve told them."
    )
    assert out["say_hello"] == {
        "label": "Say hello to Kavya",
        "to": f"/ideas/{cast['lead']['idea_id']}/conversation#say-hello",  # BLD-F069
    }
    assert out["request"]["state"] == "approved_merged"
    # L-MERGE.effects/1, /4, /5
    assert f.status_of(db, cast["mine"]) == {"status": "merged", "merged_into": cast["lead"]["id"]}
    m = db.execute("SELECT * FROM merges WHERE merged_idea_uuid = %s", (cast["mine"]["id"],)).fetchone()
    assert m["via"] == "lead_accepted" and m["by_code"] == cast["ravi"]["code"]
    assert str(m["teamup_request_id"]) == sent["id"] and m["prior_status"] == "with_review_desk"
    assert (
        db.execute("SELECT state FROM question_sets WHERE idea_uuid = %s", (cast["mine"]["id"],)).fetchone()[
            "state"
        ]
        == "closed"
    )
    crew_now = f.live_crew(db, cast["lead"])
    assert crew_now[cast["kavya"]["code"]] == "crew" and crew_now[kavya_crew["code"]] == "crew"
    assert crew_now[cast["ravi"]["code"]] == "lead" and list(crew_now.values()).count("lead") == 1
    vias = {r["contributor_code"]: r["via"] for r in f.crew_rows(db, cast["lead"])}
    assert vias[cast["kavya"]["code"]] == "merge"
    # conversation lines, IDs only
    # in the order they were said, though one answer writes them all at one time (ids are random)
    lead_events = [e for e, _ in f.events(db, cast["lead"])]
    assert lead_events == ["teamup.approved_merged", "crew.joined", "crew.joined", "merge.from"]
    assert ("merge.into", {"merge_id": str(m["id"]), "idea_id": cast["lead"]["idea_id"]}) in f.events(
        db, cast["mine"]
    )
    # the requester is told at once; the crew already there hears who joined; the lead's ask is resolved
    (told,) = inbox.of("teamup_answer")
    assert told["recipients"] == [cast["kavya"]["id"]]
    assert told["refs"] == {
        "request_id": sent["id"],
        "request": "teamup",
        "answer": "merge",
        "has_reason": False,
    }
    joined = inbox.of("crew_joined")
    assert joined and all(
        p["recipients"] == [cast["asha"]["id"]] and p["refs"] == {"via": "merge"} for p in joined
    )
    assert f"teamup_request:{sent['id']}" in inbox.resolved
    after = requests.my_state(db, cast["lead"]["idea_id"], cast["kavya"]["id"])
    assert (
        after["me"] == "crew"
        and after["after"]["line"] == f"Merged into {cast['lead']['idea_id']}, with credit to you."
    )


def test_V_ACC_teamup_6_team_up_only(db: Conn, cast: dict[str, Any], inbox: f.Inbox) -> None:
    sent = _send(db, cast, [cast["mine"]["idea_id"]])
    out = requests.answer(db, sent["id"], cast["ravi"]["id"], {"answer": "team_only"})
    assert out["result"]["text"] == (
        "Teamed up. Kavya is on your crew. Their idea stays separate, and they send it on its own. We’ve told them."
    )
    assert f.status_of(db, cast["mine"])["status"] == "with_review_desk"
    assert db.execute("SELECT count(*) AS n FROM merges").fetchone()["n"] == 0
    rows = {r["contributor_code"]: r for r in f.crew_rows(db, cast["lead"])}
    assert rows[cast["kavya"]["code"]]["via"] == "teamup"
    assert str(rows[cast["kavya"]["code"]]["teamup_request_id"]) == sent["id"]
    assert ("crew.joined", {"via": "teamup", "request_id": sent["id"]}) in f.events(db, cast["lead"])
    assert inbox.of("teamup_answer")[0]["refs"]["answer"] == "team_only"
    mine = requests.my_state(db, cast["lead"]["idea_id"], cast["kavya"]["id"])
    assert mine["after"]["line"] == "You’re on the crew. You’ll get its updates."
    # BLD-F069: every "Say hello" opens the conversation with the cursor in the box (#say-hello, no words): the
    # lead's, the requester's Inbox action and the sheet's
    hello = f"/ideas/{cast['lead']['idea_id']}/conversation#say-hello"
    assert out["say_hello"] == {"label": "Say hello to Kavya", "to": hello}
    assert [(a.label, a.style, a.to, a.op) for a in inbox.of("teamup_answer")[0]["actions"]] == [
        ("Say hello", "primary", hello, None)
    ]
    assert mine["after"]["action"] == {"label": "Say hello", "to": hello}


def test_V_ACC_teamup_6_decline_with_a_masked_reason(db: Conn, cast: dict[str, Any], inbox: f.Inbox) -> None:
    sent = _send(db, cast, [cast["mine"]["idea_id"]])
    out = requests.answer(db, sent["id"], cast["ravi"]["id"],
                          {"answer": "decline", "reason": "The crew is full for now, call 9876543210"})  # fmt: skip
    assert out["result"]["state"] == "declined" and out["say_hello"] is None
    assert "9876543210" not in out["result"]["text"] and "••••10" in out["result"]["text"]
    row = db.execute("SELECT * FROM teamup_requests WHERE id = %s", (sent["id"],)).fetchone()
    stored = open_text("teamup_requests", "lead_reason_encrypted", sent["id"], row["lead_reason_encrypted"])
    assert stored is not None and "9876543210" not in stored
    assert row["state"] == "declined" and cast["kavya"]["code"] not in f.live_crew(db, cast["lead"])
    assert inbox.of("teamup_answer")[0]["refs"]["has_reason"] is True
    mine = requests.my_state(db, cast["lead"]["idea_id"], cast["kavya"]["id"])
    assert mine["can_request"] is True and mine["after"]["line"].startswith(
        "Ravi declined: “The crew is full for now"
    )
    for a in f.audit_rows(db, "teamup."):
        assert "full" not in str(a["after"]) and "9876543210" not in str(a["after"])


def test_L_TEAMUP_rules_6_with_nothing_brought_merge_is_refused(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    sent = _send(db, cast)
    r = _refused(requests.answer, db, sent["id"], cast["ravi"]["id"], {"answer": "merge"})
    assert (r.status, r.code, r.field) == (422, "nothing_brought", "answer")
    ok = requests.answer(db, sent["id"], cast["ravi"]["id"], {"answer": "team_only"})
    assert ok["result"]["text"] == "Teamed up. Kavya is on your crew. We’ve told them."


def test_V_ACC_similar_8_nobody_but_the_lead_can_answer_and_the_attempt_is_audited(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    sent = _send(db, cast, [cast["mine"]["idea_id"]])
    for who in ("kavya", "asha"):
        r = _refused(requests.answer, db, sent["id"], cast[who]["id"], {"answer": "merge"})
        assert (r.status, r.code) == (403, "not_lead")
    assert len(f.audit_rows(db, "teamup.answer_refused", sent["id"])) == 2
    assert f.status_of(db, cast["mine"])["status"] == "with_review_desk"
    assert db.execute("SELECT count(*) AS n FROM merges").fetchone()["n"] == 0


def test_an_answer_is_given_once(db: Conn, cast: dict[str, Any], inbox: f.Inbox) -> None:
    sent = _send(db, cast)
    requests.answer(db, sent["id"], cast["ravi"]["id"], {"answer": "decline"})
    assert (
        _refused(requests.answer, db, sent["id"], cast["ravi"]["id"], {"answer": "team_only"}).code
        == "not_waiting"
    )
    assert _refused(requests.withdraw, db, sent["id"], cast["kavya"]["id"]).code == "not_waiting"
    assert (
        _refused(requests.answer, db, sent["id"], cast["ravi"]["id"], {"answer": "maybe"}).code
        == "answer_required"
    )


def test_L_TEAMUP_states_closed_when_the_idea_closes_first(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    sent = _send(db, cast)
    db.execute("UPDATE ideas SET status = 'withdrawn' WHERE id = %s", (cast["lead"]["id"],))
    # V-ACC.similar/8: someone who is not the lead hears only that, audited, and nothing changes
    r = _refused(requests.answer, db, sent["id"], cast["asha"]["id"], {"answer": "team_only"})
    assert (r.status, r.code) == (403, "not_lead")
    assert len(f.audit_rows(db, "teamup.answer_refused", sent["id"])) == 1
    state = db.execute("SELECT state FROM teamup_requests WHERE id = %s", (sent["id"],)).fetchone()["state"]
    assert state == "sent" and inbox.resolved == []
    r = _refused(requests.answer, db, sent["id"], cast["ravi"]["id"], {"answer": "team_only"})
    assert r.code == "idea_closed"
    state = db.execute("SELECT state FROM teamup_requests WHERE id = %s", (sent["id"],)).fetchone()["state"]
    assert state == "closed" and f"teamup_request:{sent['id']}" in inbox.resolved
    mine = requests.my_state(db, cast["lead"]["idea_id"], cast["kavya"]["id"])
    assert mine["why_not"] == "idea_closed" and mine["after"] is None
    # withdrawing a request that closed with its idea says so; it was never answered
    late = _refused(requests.withdraw, db, sent["id"], cast["kavya"]["id"])
    assert (late.status, late.code, late.message) == (
        409,
        "idea_closed",
        "This idea is no longer open to team up.",
    )
    gone = _refused(requests.withdraw, db, "0b6c3d2e-0000-4000-8000-00000000dead", cast["kavya"]["id"])
    assert (gone.status, gone.code, gone.message) == (404, "not_found", "We couldn’t find that.")


def test_L_SUBMIT_withdraw_2_a_withdrawn_idea_is_not_found_by_strangers_in_team_up(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    """BLD-E011: hidden from everyone but its sharer, its crew (past or present) and the people who asked to join."""
    left = f.person(db, "Meera Iyer")
    f.crew(db, cast["lead"], left)
    crew.leave(db, cast["lead"]["idea_id"], left["id"])
    _send(db, cast)  # Kavya asked to join it
    pradeep = f.person(db, "Pradeep Kumar")
    pradeep_draft = f.draft(db, pradeep)
    db.execute("UPDATE ideas SET status = 'withdrawn' WHERE id = %s", (cast["lead"]["id"],))
    ref = cast["lead"]["idea_id"]
    body = {"note": NOTE, "brought_idea_ids": []}
    for call in (
        lambda: requests.my_state(db, ref, pradeep["id"]),
        lambda: requests.draft_note(db, ref, pradeep["id"]),
        lambda: requests.send(db, ref, pradeep["id"], body),
        lambda: drafts.ask(db, str(pradeep_draft["id"]), pradeep["id"], {"other_idea_id": ref, "note": NOTE}),
    ):
        r = _refused(call)
        assert (r.status, r.code, r.message) == (404, "not_found", "We couldn’t find that.")
    assert (
        db.execute(
            "SELECT count(*) AS n FROM teamup_requests WHERE idea_uuid = %s AND from_code = %s",
            (cast["lead"]["id"], pradeep["code"]),
        ).fetchone()["n"]
        == 0
    )
    # the sharer, the crew, someone who left it and someone who asked still find it, closed
    assert requests.my_state(db, ref, cast["ravi"]["id"])["me"] == "lead"
    assert requests.my_state(db, ref, cast["asha"]["id"])["me"] == "crew"
    for who in (left, cast["kavya"]):
        mine = requests.my_state(db, ref, who["id"])
        assert mine["why_not"] == "idea_closed" and mine["can_request"] is False
        assert _refused(requests.send, db, ref, who["id"], body).code == "idea_closed"


def test_a_merge_closes_requests_waiting_on_the_merged_idea(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    pradeep = f.person(db, "Pradeep Kumar")
    on_mine = requests.send(
        db, cast["mine"]["idea_id"], pradeep["id"], {"note": NOTE, "brought_idea_ids": []}
    )
    sent = _send(db, cast, [cast["mine"]["idea_id"]])
    requests.answer(db, sent["id"], cast["ravi"]["id"], {"answer": "merge"})
    state = db.execute("SELECT state FROM teamup_requests WHERE id = %s", (on_mine["id"],)).fetchone()[
        "state"
    ]
    assert state == "closed" and f"teamup_request:{on_mine['id']}" in inbox.resolved


# --- L-TEAMUP.rules/11: leaving and removal ---------------------------------------------------------------------
def test_L_TEAMUP_rules_11_a_member_leaves_and_the_lead_removes(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    ref = cast["lead"]["idea_id"]
    assert _refused(crew.leave, db, ref, cast["ravi"]["id"]).code == "lead_stays"
    assert _refused(crew.leave, db, ref, cast["kavya"]["id"]).code == "not_on_crew"
    out = crew.leave(db, ref, cast["asha"]["id"])
    assert out["crew_count"] == 1 and cast["asha"]["code"] not in f.live_crew(db, cast["lead"])
    assert ("crew.left", {}) in f.events(db, cast["lead"])
    f.crew(db, cast["lead"], cast["kavya"])
    r = _refused(crew.remove, db, ref, cast["kavya"]["id"], cast["kavya"]["id"])
    assert (r.status, r.code) == (403, "not_lead") and f.audit_rows(db, "crew.remove_refused")
    assert _refused(crew.remove, db, ref, cast["ravi"]["id"], cast["ravi"]["id"]).code == "lead_stays"
    crew.remove(db, ref, cast["kavya"]["id"], cast["ravi"]["id"])
    gone = [r for r in f.crew_rows(db, cast["lead"]) if r["contributor_code"] == cast["kavya"]["code"]]
    assert gone[0]["left_how"] == "removed" and gone[0]["removed_by_code"] == cast["ravi"]["code"]
    assert ("crew.removed", {"member_code": cast["kavya"]["code"]}) in f.events(db, cast["lead"])
    assert [a["action"] for a in f.audit_rows(db, "crew.") if a["entity"] == f"idea:{ref}"] == [
        "crew.leave",
        "crew.remove_refused",
        "crew.remove",
    ]
    # a member who left can ask again, and join again
    again = _send(db, cast)
    assert again["state"] == "sent"
    requests.answer(db, again["id"], cast["ravi"]["id"], {"answer": "team_only"})
    assert f.live_crew(db, cast["lead"])[cast["kavya"]["code"]] == "crew"
    kavya_rows = [r for r in f.crew_rows(db, cast["lead"]) if r["contributor_code"] == cast["kavya"]["code"]]
    assert [r["left_how"] for r in kavya_rows] == ["removed", None]


def test_L_SUBMIT_withdraw_2_a_stranger_cannot_leave_or_remove_on_a_withdrawn_idea(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    """BLD-F023: leave and remove say "not found" to a stranger, so neither confirms that a withdrawn idea exists;
    the people BLD-E011 names still get their usual answers."""
    pradeep = f.person(db, "Pradeep Kumar")
    db.execute("UPDATE ideas SET status = 'withdrawn' WHERE id = %s", (cast["lead"]["id"],))
    ref = cast["lead"]["idea_id"]
    for call in (
        lambda: crew.leave(db, ref, pradeep["id"]),
        lambda: crew.remove(db, ref, cast["asha"]["id"], pradeep["id"]),
    ):
        r = _refused(call)
        assert (r.status, r.code, r.message) == (404, "not_found", "We couldn’t find that.")
    assert [a for a in f.audit_rows(db, "crew.") if a["entity"] == f"idea:{ref}"] == []
    assert cast["asha"]["code"] in f.live_crew(db, cast["lead"])
    assert _refused(crew.leave, db, ref, cast["ravi"]["id"]).code == "lead_stays"
    assert _refused(crew.remove, db, ref, pradeep["id"], cast["ravi"]["id"]).code == "not_on_crew"
    assert _refused(crew.remove, db, ref, cast["ravi"]["id"], cast["asha"]["id"]).code == "not_lead"
    assert crew.leave(db, ref, cast["asha"]["id"])["crew_count"] == 1


# --- adapters --------------------------------------------------------------------------------------------------
def test_adapters_resolve_calls_lane_A_with_the_request_key(inbox: f.Inbox) -> None:
    adapters.resolve(None, "0b6c3d2e-0000-4000-8000-000000000001")  # type: ignore[arg-type]
    assert inbox.resolved == ["teamup_request:0b6c3d2e-0000-4000-8000-000000000001"]


def test_adapters_resolve_logs_the_id_when_lane_A_has_not_landed(monkeypatch: pytest.MonkeyPatch) -> None:
    import notify

    monkeypatch.delattr(notify, "resolve", raising=False)
    adapters.resolve(None, "0b6c3d2e-0000-4000-8000-000000000002")  # type: ignore[arg-type]


def test_adapters_say_uses_convo_post_when_lane_F3_has_published_it(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    calls: list[tuple[Any, ...]] = []

    def post(conn: Any, idea_uuid: str, event: str, **kw: Any) -> str:
        calls.append((idea_uuid, event, kw))
        return "id"

    fake = types.ModuleType("convo")
    fake.post = post
    monkeypatch.setitem(sys.modules, "convo", fake)
    when = f.at(17)
    adapters.say(_NoLines(), "idea-uuid", "crew.left", author_code="CTR-0a1b2c", at=when)  # type: ignore[arg-type]
    assert calls == [("idea-uuid", "crew.left", {"author_user_id": None, "author_code": "CTR-0a1b2c", "payload": None,
                                                  "question_set_id": None, "entry_type": "event", "at": when})]  # fmt: skip


class _NoLines:
    """A connection whose idea has no conversation lines yet."""

    def execute(self, *_: Any) -> Any:
        return self

    def fetchone(self) -> dict[str, Any]:
        return {"last": None}


def test_L_CONVO_lines_said_at_one_time_keep_the_order_they_were_said(db: Conn, cast: dict[str, Any]) -> None:
    lead = cast["lead"]
    when = f.at(17)
    for event in ("teamup.approved_merged", "crew.joined", "crew.joined", "merge.from", "crew.left"):
        adapters.say(db, str(lead["id"]), event, at=when)
    adapters.say(
        db, str(lead["id"]), "crew.removed", at=f.at(16)
    )  # a time before the last line goes after it
    assert [e for e, _ in f.events(db, lead)] == [
        "teamup.approved_merged", "crew.joined", "crew.joined", "merge.from", "crew.left", "crew.removed",
    ]  # fmt: skip


# --- L-MERGE.request: a draft asks to be merged in (J-SIMILAR 3–6c, V-ACC.similar/3–8) -----------------------
REASON = "Mine is about the SMS wording, yours is about the calls it causes. Better as two."


@pytest.fixture
def held(db: Conn, cast: dict[str, Any], inbox: f.Inbox) -> dict[str, Any]:
    """Kavya's unsent draft, close to Ravi's idea, with a merge request waiting on Ravi."""
    draft = f.draft(db, cast["kavya"])
    f.similar(db, draft, cast["lead"])
    out = drafts.ask(db, str(draft["id"]), cast["kavya"]["id"],
                     {"other_idea_id": cast["lead"]["idea_id"], "note": NOTE + " Call 9876543210."})  # fmt: skip
    return {"draft": draft, "asked": out}


def _check_it(db: Conn, c: dict[str, Any], h: dict[str, Any]) -> dict[str, Any]:
    return drafts.state(db, str(h["draft"]["id"]), c["kavya"]["id"])


def test_V_ACC_similar_3_asking_to_merge_holds_the_draft(
    db: Conn, cast: dict[str, Any], held: dict[str, Any], inbox: f.Inbox
) -> None:
    asked, draft = held["asked"], held["draft"]
    assert asked["state"] == "waiting" and asked["other_idea_id"] == cast["lead"]["idea_id"]
    after = asked["after"]
    assert after["label"] == "Waiting on Ravi to merge" and after["can_submit"] is False
    assert (
        after["line"]
        == "Waiting for Ravi to accept the merge. If Ravi declines, you can send yours on its own."
    )
    assert after["action"] == {"label": "Withdraw the request", "op": "withdraw"}
    assert _check_it(db, cast, held)["id"] == asked["id"]
    # L-MERGE.request/4: lane C's Submit reads this to refuse `merge_waiting`
    assert drafts.waiting_merge_request(db, draft["id"]) == asked["id"]
    # L-MERGE.request/3, BLD-F097: the ask is masked when stored and for the lead (test_1pc_f_teamup_hide_db.py pins
    # both); its typer, the draft's owner, reads their own words back (DEC-103). The draft itself is not shared
    assert "9876543210" in asked["note"] and f.status_of(db, draft)["status"] == "draft"
    # V-ACC.similar/7's neighbour for L-AUDIT.metrics
    outcome = db.execute("SELECT outcome FROM similar_links WHERE idea_uuid = %s", (draft["id"],)).fetchone()
    assert outcome["outcome"] == "merge_asked"
    (item,) = inbox.of("teamup_request")
    assert item["recipients"] == [cast["ravi"]["id"]] and item["needs_you"] is True
    assert item["refs"] == {"request_id": asked["id"], "request": "merge", "brought": 1}
    assert item["dedupe_key"] == f"teamup_request:{asked['id']}"
    assert [a.label for a in item["actions"]] == ["Decline", "Team up only", "Merge it"]
    # L-TEAMUP.rules/4: one open request per person per idea, either kind
    again = _refused(drafts.ask, db, str(draft["id"]), cast["kavya"]["id"],
                     {"other_idea_id": cast["lead"]["idea_id"], "note": NOTE})  # fmt: skip
    assert (again.code, again.message) == ("already_requested", "Waiting on Ravi to merge")
    assert _refused(_send, db, cast).code == "already_requested"
    other = f.draft(db, cast["kavya"])
    own = _refused(drafts.ask, db, str(other["id"]), cast["kavya"]["id"],
                   {"other_idea_id": cast["mine"]["idea_id"], "note": NOTE})  # fmt: skip
    assert own.code == "already_on_crew"  # Kavya leads that idea
    short = _refused(drafts.ask, db, str(other["id"]), cast["kavya"]["id"],
                     {"other_idea_id": f.idea(db, cast["asha"])["idea_id"], "note": "x" * 29})  # fmt: skip
    assert (short.code, short.field) == ("note_too_short", "note")
    assert (
        _refused(
            drafts.ask,
            db,
            str(other["id"]),
            cast["asha"]["id"],
            {"other_idea_id": cast["lead"]["idea_id"], "note": NOTE},
        ).status
        == 404
    )  # not her draft
    for a in f.audit_rows(db, "merge_request."):
        assert "branch" not in str(a["after"]) and "9876543210" not in str(a["after"])


def test_L_MERGE_request_3_only_the_lead_reads_it_with_the_draft_summary(
    db: Conn, cast: dict[str, Any], held: dict[str, Any]
) -> None:
    rid = held["asked"]["id"]
    page = requests.read(db, rid, cast["ravi"]["id"])
    assert page["request"] == "merge" and page["state"] == "sent"
    assert page["reader"]["kind"] == "Merge request"
    assert page["reader"]["line"] == "Kavya Menon asks to team up and merge their idea into yours"
    (b,) = page["brought"]
    assert (
        b["id"] == str(held["draft"]["id"])
        and b["status"] == "draft"
        and b["summary"] == held["draft"]["summary"]
    )
    assert [a["label"] for a in page["answers"]] == ["Decline", "Team up only", "Merge it"]
    assert _refused(requests.read, db, rid, cast["asha"]["id"]).status == 404
    assert _refused(drafts.state, db, str(held["draft"]["id"]), cast["ravi"]["id"]).status == 404


def test_V_ACC_similar_4_merge_it_closes_the_draft_as_merged(
    db: Conn, cast: dict[str, Any], held: dict[str, Any], inbox: f.Inbox
) -> None:
    rid, draft = held["asked"]["id"], held["draft"]
    out = requests.answer(db, rid, cast["ravi"]["id"], {"answer": "merge"})
    assert out["request"]["state"] == "approved_merged"
    assert out["result"]["text"] == (
        "Merged. Kavya’s idea is now part of yours, and they are on your crew, credited. We’ve told them."
    )
    row = db.execute("SELECT state FROM merge_requests WHERE id = %s", (rid,)).fetchone()
    assert row["state"] == "accepted"
    assert f.status_of(db, draft) == {"status": "merged", "merged_into": cast["lead"]["id"]}
    m = db.execute("SELECT * FROM merges WHERE merged_idea_uuid = %s", (draft["id"],)).fetchone()
    assert (
        m["via"] == "lead_accepted" and str(m["merge_request_id"]) == rid and m["teamup_request_id"] is None
    )
    assert m["prior_status"] == "draft"
    assert f.live_crew(db, cast["lead"])[cast["kavya"]["code"]] == "crew"
    # a draft has no conversation, so only the lead idea gets its lines
    assert [e for e, _ in f.events(db, cast["lead"])] == [
        "teamup.approved_merged",
        "crew.joined",
        "merge.from",
    ]
    assert f.events(db, draft) == []
    after = _check_it(db, cast, held)
    ref = cast["lead"]["idea_id"]
    assert after["state"] == "accepted" and after["after"]["label"] == f"Merged into {ref}"
    assert (
        after["after"]["line"]
        == f"Ravi accepted. Yours is now part of {ref}, with credit to you. Nothing else to send."
    )
    assert after["after"]["can_submit"] is False and drafts.waiting_merge_request(db, draft["id"]) is None
    (told,) = inbox.of("teamup_answer")
    assert told["refs"] == {"request_id": rid, "request": "merge", "answer": "merge", "has_reason": False}
    assert f"teamup_request:{rid}" in inbox.resolved


def test_V_ACC_similar_5_declined_with_a_reason_then_send_mine_on_its_own(
    db: Conn, cast: dict[str, Any], held: dict[str, Any], inbox: f.Inbox
) -> None:
    rid, draft = held["asked"]["id"], held["draft"]
    out = requests.answer(db, rid, cast["ravi"]["id"], {"answer": "decline", "reason": REASON})
    assert (
        out["result"]["text"]
        == f"Declined. Kavya sees your reason: “{REASON}” They can send theirs on its own."
    )
    after = _check_it(db, cast, held)
    assert after["state"] == "declined" and after["lead_reason"] == REASON
    assert after["after"]["label"] == "Ravi kept it separate"
    assert after["after"]["line"] == f"Ravi kept that idea separate: “{REASON}” Send yours on its own."
    assert after["after"]["action"] == {"label": "Send mine on its own", "op": "submit"}
    assert after["after"]["can_submit"] is True and drafts.waiting_merge_request(db, draft["id"]) is None
    assert f.status_of(db, draft)["status"] == "draft" and cast["kavya"]["code"] not in f.live_crew(
        db, cast["lead"]
    )
    assert inbox.of("teamup_answer")[0]["refs"]["has_reason"] is True


def test_V_ACC_similar_6_team_up_only_puts_them_on_the_crew_and_the_draft_stays_theirs(
    db: Conn, cast: dict[str, Any], held: dict[str, Any]
) -> None:
    rid, draft = held["asked"]["id"], held["draft"]
    out = requests.answer(db, rid, cast["ravi"]["id"], {"answer": "team_only"})
    assert out["result"]["text"] == (
        "Teamed up. Kavya is on your crew. Their idea stays separate, and they send it on its own. We’ve told them."
    )
    assert (
        db.execute("SELECT state FROM merge_requests WHERE id = %s", (rid,)).fetchone()["state"]
        == "team_only"
    )
    rows = {r["contributor_code"]: r for r in f.crew_rows(db, cast["lead"])}
    assert (
        rows[cast["kavya"]["code"]]["via"] == "teamup"
        and rows[cast["kavya"]["code"]]["teamup_request_id"] is None
    )
    assert f.status_of(db, draft)["status"] == "draft"
    after = _check_it(db, cast, held)["after"]
    assert (
        after["line"] == "You’re on the crew. You’ll get its updates. Send yours on its own."
        and after["can_submit"]
    )


def test_V_ACC_similar_7_keep_mine_separate_is_recorded_for_the_reviewer(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    draft = f.draft(db, cast["kavya"])
    f.similar(db, draft, cast["lead"])
    sent = requests.send(db, cast["lead"]["idea_id"], cast["kavya"]["id"],
                         {"note": NOTE, "brought_idea_ids": [], "draft_id": str(draft["id"])})  # fmt: skip
    assert sent["state"] == "sent" and sent["request"] == "teamup"
    kept = db.execute("SELECT kept_separate FROM ideas WHERE id = %s", (draft["id"],)).fetchone()
    assert kept["kept_separate"] is True
    link = db.execute("SELECT outcome FROM similar_links WHERE idea_uuid = %s", (draft["id"],)).fetchone()
    assert link["outcome"] == "kept_separate"
    assert drafts.waiting_merge_request(db, draft["id"]) is None  # Submit stays available
    # someone else's draft cannot be marked
    asha_draft = f.draft(db, cast["asha"])
    pradeep = f.person(db, "Pradeep Kumar")
    r = _refused(requests.send, db, cast["lead"]["idea_id"], pradeep["id"],
                 {"note": NOTE, "brought_idea_ids": [], "draft_id": str(asha_draft["id"])})  # fmt: skip
    assert r.status == 404
    assert (
        db.execute("SELECT kept_separate FROM ideas WHERE id = %s", (asha_draft["id"],)).fetchone()[
            "kept_separate"
        ]
        is False
    )


def test_V_ACC_similar_8_no_route_merges_a_draft_without_the_lead(
    db: Conn, cast: dict[str, Any], held: dict[str, Any], inbox: f.Inbox
) -> None:
    rid, draft = held["asked"]["id"], held["draft"]
    for who in ("kavya", "asha"):
        r = _refused(requests.answer, db, rid, cast[who]["id"], {"answer": "merge"})
        assert (r.status, r.code) == (403, "not_lead")
    assert len(f.audit_rows(db, "teamup.answer_refused", rid)) == 2
    # the merge itself refuses anyone but the lead, whoever calls it
    r = _refused(merging.apply_lead_merge, db, lead_uuid=cast["lead"]["id"], merged_uuid=draft["id"],
                 by_code=cast["kavya"]["code"], requester_code=cast["kavya"]["code"], note_masked="x")  # fmt: skip
    assert (r.status, r.code) == (403, "not_lead")
    assert f.status_of(db, draft)["status"] == "draft"
    assert db.execute("SELECT count(*) AS n FROM merges").fetchone()["n"] == 0
    assert (
        db.execute("SELECT state FROM merge_requests WHERE id = %s", (rid,)).fetchone()["state"] == "waiting"
    )


def test_L_MERGE_request_8_withdrawing_returns_the_draft_to_normal(
    db: Conn, cast: dict[str, Any], held: dict[str, Any], inbox: f.Inbox
) -> None:
    rid, draft = held["asked"]["id"], held["draft"]
    back = drafts.withdraw(db, str(draft["id"]), cast["kavya"]["id"])
    assert back["state"] == "withdrawn" and back["after"] is None
    assert drafts.waiting_merge_request(db, draft["id"]) is None and f"teamup_request:{rid}" in inbox.resolved
    assert drafts.withdraw(db, str(draft["id"]), cast["kavya"]["id"])["state"] == "withdrawn"  # idempotent
    late = _refused(requests.answer, db, rid, cast["ravi"]["id"], {"answer": "merge"})
    assert (late.code, late.message) == ("not_waiting", "Kavya withdrew this request.")
    assert [a["action"] for a in f.audit_rows(db, "merge_request.", rid)] == [
        "merge_request.ask",
        "merge_request.withdraw",
    ]
    again = drafts.ask(
        db, str(draft["id"]), cast["kavya"]["id"], {"other_idea_id": cast["lead"]["idea_id"], "note": NOTE}
    )
    assert again["state"] == "waiting" and again["id"] != rid


def test_L_MERGE_request_3_the_lead_reads_the_draft_only_while_the_request_waits(
    db: Conn, cast: dict[str, Any], held: dict[str, Any], inbox: f.Inbox
) -> None:
    """BLD-F022: once the request has left `waiting`, the lead gets the draft's id and status only."""
    draft = held["draft"]
    bare = [{"id": str(draft["id"]), "title": "", "status": "draft"}]
    page = requests.read(db, held["asked"]["id"], cast["ravi"]["id"])
    assert page["brought"][0]["title"] == draft["title"] and page["brought"][0]["summary"] == draft["summary"]
    # after a withdraw
    drafts.withdraw(db, str(draft["id"]), cast["kavya"]["id"])
    page = requests.read(db, held["asked"]["id"], cast["ravi"]["id"])
    assert page["state"] == "withdrawn" and page["brought"] == bare and page["answers"] == []
    # after a decline
    again = drafts.ask(db, str(draft["id"]), cast["kavya"]["id"],
                       {"other_idea_id": cast["lead"]["idea_id"], "note": NOTE})  # fmt: skip
    out = requests.answer(db, again["id"], cast["ravi"]["id"], {"answer": "decline", "reason": REASON})
    assert out["request"]["brought"] == bare
    page = requests.read(db, again["id"], cast["ravi"]["id"])
    assert page["state"] == "declined" and page["brought"] == bare
    # the sharer still reads their own draft's title
    theirs = requests.read(db, again["id"], cast["kavya"]["id"])
    assert theirs["brought"][0]["title"] == draft["title"]


def test_BLD_F022_the_lead_never_reads_a_brought_idea_its_sharer_withdrew(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    sent = _send(db, cast, [cast["mine"]["idea_id"]])
    db.execute("UPDATE ideas SET status = 'withdrawn' WHERE id = %s", (cast["mine"]["id"],))
    page = requests.read(db, sent["id"], cast["ravi"]["id"])
    assert page["brought"] == [{"id": cast["mine"]["idea_id"], "title": "", "status": "withdrawn"}]


def test_L_TEAMUP_rules_5_what_the_lead_reads_passes_the_summary_checks(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    """BLD-C090, DEC-104: a title or summary that fails the tag, pattern and name checks is not shown."""
    risky = f.idea(db, cast["kavya"], title="Calls from 9876543210 about R07",
                   summary="[[KFIN_EMPLOYEE_1]] takes these calls every day.")  # fmt: skip
    sent = _send(db, cast, [risky["idea_id"]])
    (b,) = requests.read(db, sent["id"], cast["ravi"]["id"])["brought"]
    assert b["title"] == risky["idea_id"] and b["summary"] == "A short summary is on its way."


def test_L_MERGE_request_4_a_draft_sent_or_archived_while_its_request_waits_ends_the_request(
    db: Conn, cast: dict[str, Any], held: dict[str, Any], inbox: f.Inbox
) -> None:
    """BLD-F024: lane C's Submit refuses `merge_waiting`; a draft sent before that check, or archived, ends its
    request as if withdrawn, instead of leaving the lead a request that fails with `brought_not_open`."""
    rid, draft = held["asked"]["id"], held["draft"]
    db.execute("UPDATE ideas SET status = 'with_review_desk' WHERE id = %s", (draft["id"],))  # sent anyway
    page = requests.read(db, rid, cast["ravi"]["id"])
    assert page["state"] == "withdrawn" and page["answers"] == [] and "result" not in page
    assert page["brought"] == [{"id": str(draft["id"]), "title": "", "status": "with_review_desk"}]
    assert f"teamup_request:{rid}" in inbox.resolved
    assert [a["action"] for a in f.audit_rows(db, "merge_request.ended", rid)] == [
        "merge_request.ended_with_draft"
    ]
    late = _refused(requests.answer, db, rid, cast["ravi"]["id"], {"answer": "merge"})
    assert (late.status, late.code, late.message) == (409, "not_waiting", "Kavya withdrew this request.")
    # archived while waiting, and the lead answers before anyone reads it: ended by the answer itself
    other = f.draft(db, cast["kavya"])
    asked = drafts.ask(db, str(other["id"]), cast["kavya"]["id"],
                       {"other_idea_id": cast["lead"]["idea_id"], "note": NOTE})  # fmt: skip
    db.execute("UPDATE ideas SET archived_at = now() WHERE id = %s", (other["id"],))
    late = _refused(requests.answer, db, asked["id"], cast["ravi"]["id"], {"answer": "team_only"})
    assert (late.code, late.message) == ("not_waiting", "Kavya withdrew this request.")
    row = db.execute("SELECT state FROM merge_requests WHERE id = %s", (asked["id"],)).fetchone()
    assert row["state"] == "withdrawn" and f"teamup_request:{asked['id']}" in inbox.resolved
    assert cast["kavya"]["code"] not in f.live_crew(db, cast["lead"])
    assert db.execute("SELECT count(*) AS n FROM merges").fetchone()["n"] == 0
    # nothing is left waiting on Ravi, so Kavya can ask again
    assert requests.my_state(db, cast["lead"]["idea_id"], cast["kavya"]["id"])["can_request"] is True


def test_L_TEAMUP_states_a_draft_merge_request_ends_when_the_idea_closes(
    db: Conn, cast: dict[str, Any], held: dict[str, Any], inbox: f.Inbox
) -> None:
    rid, draft = held["asked"]["id"], held["draft"]
    db.execute("UPDATE ideas SET status = 'not_picked' WHERE id = %s", (cast["lead"]["id"],))
    assert requests.close_requests_for(db, cast["lead"]["id"]) == 1
    assert (
        _check_it(db, cast, held)["state"] == "withdrawn"
        and drafts.waiting_merge_request(db, draft["id"]) is None
    )
    assert f"teamup_request:{rid}" in inbox.resolved
    closed = _refused(drafts.ask, db, str(draft["id"]), cast["kavya"]["id"],
                      {"other_idea_id": cast["lead"]["idea_id"], "note": NOTE})  # fmt: skip
    assert closed.code == "idea_closed"
    db.execute("UPDATE ideas SET status = 'with_review_desk' WHERE id = %s", (draft["id"],))  # sent since
    sent = _refused(drafts.ask, db, str(draft["id"]), cast["kavya"]["id"],
                    {"other_idea_id": f.idea(db, cast["asha"])["idea_id"], "note": NOTE})  # fmt: skip
    assert sent.code == "draft_closed"


# --- BLD-F028: the lead's answers as Inbox buttons (J-TEAMUP/4, J-SIMILAR/5–6c) ---------------------------------
def _item(inbox: f.Inbox) -> dict[str, Any]:
    """The lead's latest `teamup_request` item as lane A's Inbox hands it over: its refs are stored as `payload`."""
    item = inbox.of("teamup_request")[-1]
    return {
        "kind": "teamup_request",
        "payload": dict(item["refs"]),
        "actions": [{"op": a.op} for a in item["actions"]],
    }


def test_BLD_F028_V_ACC_teamup_6_the_inbox_buttons_answer_like_the_route(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    """Each op answers through `requests.answer` with no reason and returns what `POST /team-up/:id/answer` does."""
    # Decline, with nothing brought (the buttons are Decline and Approve)
    sent = _send(db, cast)
    row = _item(inbox)
    assert [a["op"] for a in row["actions"]] == ["decline", "team_only"]
    out = inbox_ops.decline(db, cast["ravi"]["id"], row)
    assert out["request"]["state"] == "declined" and "lead_reason" not in out["request"]
    assert (
        out["result"] == {"state": "declined", "text": "Declined. We’ve told Kavya."}
        and out["say_hello"] is None
    )
    assert [a["after"]["answer"] for a in f.audit_rows(db, "teamup.answer", sent["id"])] == ["decline"]
    (told,) = inbox.of("teamup_answer")
    assert told["refs"] == {
        "request_id": sent["id"],
        "request": "teamup",
        "answer": "decline",
        "has_reason": False,
    }
    # Approve: Kavya is on the crew
    again = _send(db, cast)
    out = inbox_ops.team_only(db, cast["ravi"]["id"], _item(inbox))
    assert out["request"]["id"] == again["id"] and out["result"]["state"] == "teamed_up"
    assert f.live_crew(db, cast["lead"])[cast["kavya"]["code"]] == "crew"
    # Merge it, from a draft's merge request (J-SIMILAR/6a)
    pradeep = f.person(db, "Pradeep Kumar")
    draft = f.draft(db, pradeep)
    asked = drafts.ask(
        db, str(draft["id"]), pradeep["id"], {"other_idea_id": cast["lead"]["idea_id"], "note": NOTE}
    )
    row = _item(inbox)
    assert row["payload"]["request"] == "merge" and [a["op"] for a in row["actions"]] == [
        "decline", "team_only", "merge",
    ]  # fmt: skip
    out = inbox_ops.merge(db, cast["ravi"]["id"], row)
    assert out["request"]["id"] == asked["id"] and out["result"]["state"] == "merged"
    assert f.status_of(db, draft)["status"] == "merged"


def test_BLD_F028_V_ACC_similar_8_an_inbox_button_is_refused_and_audited_like_the_route(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _send(db, cast, [cast["mine"]["idea_id"]])
    row = _item(inbox)
    # without lane A's Inbox module: the route's own refusal
    monkeypatch.setitem(sys.modules, "notify.inbox", None)
    r = _refused(inbox_ops.merge, db, cast["asha"]["id"], row)
    assert (r.status, r.code) == (403, "not_lead")
    assert [a["after"]["answer"] for a in f.audit_rows(db, "teamup.answer_refused", sent["id"])] == ["merge"]
    gone = _refused(inbox_ops.decline, db, cast["ravi"]["id"], {"kind": "teamup_request", "payload": {}})
    assert (gone.status, gone.code) == (404, "not_found")
    # with it: the same code and status as lane A's refusal, the route's refusal as its cause
    fake = types.ModuleType("notify.inbox")

    class InboxRefused(Exception):
        def __init__(self, code: str, status: int = 409) -> None:
            super().__init__(code)
            self.code, self.status = code, status

    fake.InboxRefused = InboxRefused
    monkeypatch.setitem(sys.modules, "notify.inbox", fake)
    with pytest.raises(InboxRefused) as exc:
        inbox_ops.team_only(db, cast["asha"]["id"], row)
    assert (exc.value.code, exc.value.status) == ("not_lead", 403) and isinstance(
        exc.value.__cause__, Refused
    )
    assert len(f.audit_rows(db, "teamup.answer_refused", sent["id"])) == 2
    inbox_ops.decline(db, cast["ravi"]["id"], row)
    with pytest.raises(InboxRefused) as exc:
        inbox_ops.merge(db, cast["ravi"]["id"], row)
    assert (exc.value.code, exc.value.status) == ("not_waiting", 409)
    assert db.execute("SELECT count(*) AS n FROM merges").fetchone()["n"] == 0


def test_BLD_F093_V_ACC_similar_8_a_stale_inbox_item_is_refused_once_its_reader_no_longer_leads(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The lead's item outlives their lead: the crew's live lead row moves to Asha (the sharer stays the fallback
    only while no live row exists, L-TEAMUP.rules/10). Ravi's old button is refused as not_lead and audited, and
    nothing is answered; the new lead answers it (f-teamup-5.delta review's stale-lead test)."""
    monkeypatch.setitem(sys.modules, "notify.inbox", None)  # the route's own refusal
    sent = _send(db, cast)
    row = _item(inbox)
    lead = cast["lead"]
    db.execute(
        "UPDATE crew_members SET role = 'crew' WHERE idea_uuid = %s AND contributor_code = %s",
        (lead["id"], cast["ravi"]["code"]),
    )
    db.execute(
        "UPDATE crew_members SET role = 'lead' WHERE idea_uuid = %s AND contributor_code = %s",
        (lead["id"], cast["asha"]["code"]),
    )
    stale = _refused(inbox_ops.team_only, db, cast["ravi"]["id"], row)
    assert (stale.status, stale.code) == (403, "not_lead")
    assert [a["after"]["answer"] for a in f.audit_rows(db, "teamup.answer_refused", sent["id"])] == [
        "team_only"
    ]
    assert requests.read(db, sent["id"], cast["kavya"]["id"])["state"] == "sent"
    assert inbox_ops.decline(db, cast["asha"]["id"], row)["request"]["state"] == "declined"


def test_BLD_F028_the_handlers_register_in_lane_A_registry_when_it_is_there(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "notify.ops", None)
    assert inbox_ops.register() is False
    registered: dict[tuple[str, str], Any] = {}
    fake = types.ModuleType("notify.ops")

    def register(kind: str, op: str) -> Any:
        def wrap(fn: Any) -> Any:
            registered[(kind, op)] = fn
            return fn

        return wrap

    fake.register = register
    monkeypatch.setitem(sys.modules, "notify.ops", fake)
    assert inbox_ops.register() is True
    assert registered == {
        ("teamup_request", "decline"): inbox_ops.decline,
        ("teamup_request", "team_only"): inbox_ops.team_only,
        ("teamup_request", "merge"): inbox_ops.merge,
    }


def test_BLD_F028_lane_A_registry_holds_the_three_handlers_once_teamup_has_loaded() -> None:
    from notify import ops  # lane A's Inbox registry is on main: no skip (BLD-F093)

    inbox_ops.register()
    for op in ("decline", "team_only", "merge"):
        assert ops.handler("teamup_request", op) is inbox_ops.HANDLERS[op]


# --- BLD-F027 lock order, BLD-F024 reads that write only when something ended ------------------------------------
_LOCK_IDEA = "SELECT * FROM ideas WHERE id = %s FOR UPDATE"  # `store.lock_ideas`
_WRITES = ("INSERT", "UPDATE", "DELETE")


def _sql_log(db: Conn, monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    """Every statement the connection runs from now on, with its parameters."""
    log: list[tuple[str, Any]] = []
    real = db.execute

    def spy(query: Any, params: Any = None, **kw: Any) -> Any:
        log.append((str(query).strip(), params))
        return real(query, params, **kw)

    monkeypatch.setattr(db, "execute", spy)
    return log


_GATED = "-- the gatekeeper was asked (BLD-F100)"


def _gate_marked(log: list[tuple[str, Any]], monkeypatch: pytest.MonkeyPatch) -> None:
    """Mark in `log` where lane C's gatekeeper ask ends (`adapters.gate`, BLD-F100). The ask runs before the write's
    transaction, in the gateway's own short one, and writes there (`llm_calls`); the write's locks come after it."""
    real = adapters.gate

    def gate(conn: Conn, idea_uuid: str, text: str) -> Any:
        out = real(conn, idea_uuid, text)
        log.append((_GATED, None))
        return out

    monkeypatch.setattr(adapters, "gate", gate)


def _locks_before_anything_else(log: list[tuple[str, Any]]) -> list[str]:
    """The ideas `lock_ideas` locked, in the order it locked them, before the first write or any other lock. Read
    from the end of the gatekeeper's ask when there was one (`_gate_marked`): it runs before the transaction."""
    marks = [i for i, (sql, _) in enumerate(log) if sql == _GATED]
    out: list[str] = []
    for sql, params in log[marks[-1] + 1 :] if marks else log:
        if sql == _LOCK_IDEA:
            out.append(str(params[0]))
        elif "FOR UPDATE" in sql or sql.split(None, 1)[0].upper() in _WRITES:
            break
    return out


def _writes(log: list[tuple[str, Any]]) -> list[str]:
    return [sql for sql, _ in log if sql.split(None, 1)[0].upper() in _WRITES or "FOR UPDATE" in sql]


def test_BLD_F027_answer_send_with_a_draft_and_ask_lock_every_idea_first_in_id_order(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L-TEAMUP, L-MERGE.request: the three writes that touch two ideas lock both, sorted by row id, before any
    other lock or write, so two of them at once wait for each other instead of deadlocking."""
    lead, mine = str(cast["lead"]["id"]), str(cast["mine"]["id"])
    # POST /ideas/:id/team-up with draft_id ("Keep mine separate"): the idea and the draft it marks
    kept = f.draft(db, cast["kavya"])
    f.similar(db, kept, cast["lead"])
    log = _sql_log(db, monkeypatch)
    _gate_marked(log, monkeypatch)
    sent = requests.send(db, cast["lead"]["idea_id"], cast["kavya"]["id"],
                         {"note": NOTE, "brought_idea_ids": [cast["mine"]["idea_id"]],
                          "draft_id": str(kept["id"])})  # fmt: skip
    assert (_GATED, None) in log  # the note went to the gatekeeper before the transaction (BLD-F100)
    locked = _locks_before_anything_else(log)
    assert locked == sorted(locked) and set(locked) == {lead, mine, str(kept["id"])}
    # POST /team-up/:id/answer: the lead's idea and every idea brought, then the request row
    log.clear()
    requests.answer(db, sent["id"], cast["ravi"]["id"], {"answer": "merge"})
    locked = _locks_before_anything_else(log)
    assert locked == sorted(locked) and set(locked) == {lead, mine}
    # POST /drafts/:id/merge-request: the draft and the idea it asks to join
    pradeep = f.person(db, "Pradeep Kumar")
    asking = f.draft(db, pradeep)
    log.clear()
    drafts.ask(db, str(asking["id"]), pradeep["id"], {"other_idea_id": cast["lead"]["idea_id"], "note": NOTE})
    assert (_GATED, None) in log  # the ask, likewise
    locked = _locks_before_anything_else(log)
    assert locked == sorted(locked) and set(locked) == {lead, str(asking["id"])}


def test_BLD_F024_a_read_writes_only_when_a_brought_draft_has_left_draft(
    db: Conn, cast: dict[str, Any], held: dict[str, Any], inbox: f.Inbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    rid, draft = held["asked"]["id"], held["draft"]
    ref = cast["lead"]["idea_id"]
    log = _sql_log(db, monkeypatch)
    requests.my_state(db, ref, cast["kavya"]["id"])
    requests.my_state(db, ref, cast["asha"]["id"])
    requests.read(db, rid, cast["ravi"]["id"])
    _check_it(db, cast, held)
    assert _writes(log) == []
    # the draft is sent while its request waits: the next read ends it, once
    db.execute("UPDATE ideas SET status = 'with_review_desk' WHERE id = %s", (draft["id"],))
    log.clear()
    mine = requests.my_state(db, ref, cast["kavya"]["id"])
    assert mine["request"]["state"] == "withdrawn" and mine["can_request"] is True
    assert any(sql.startswith("UPDATE merge_requests") for sql in _writes(log))
    log.clear()
    requests.my_state(db, ref, cast["kavya"]["id"])
    requests.read(db, rid, cast["ravi"]["id"])
    assert _writes(log) == []


# --- BLD-F029, DEC-104: a lead who hid their name from the Wall, or has left, is "the lead" to someone asking ------
def _unnamed(db: Conn, person: dict[str, str], how: str) -> None:
    """The lead hides their name from the Wall in Profile, or is no longer active (lane C's `person_refs` rule)."""
    if how == "hidden":
        db.execute(
            "INSERT INTO person_settings (user_id, show_name_on_wall) VALUES (%s, false) "
            "ON CONFLICT (user_id) DO UPDATE SET show_name_on_wall = false",
            (person["id"],),
        )
    else:
        db.execute("UPDATE users SET active = false WHERE id = %s", (person["id"],))


def _no_trace_of(person: dict[str, str], *payloads: Any) -> None:
    """Neither the lead's name nor their users.id is anywhere in what the requester receives."""
    for payload in payloads:
        text = str(payload)
        for secret in (person["name"], person["first_name"], person["name"].split()[-1], person["id"]):
            assert secret not in text, secret


def _hidden_lead(ref: dict[str, Any]) -> None:
    assert (ref["name"], ref["first_name"], ref["initials"]) == ("A colleague", "A colleague", "")
    assert ref["id"].startswith("p") and "area" not in ref and "city" not in ref


@pytest.mark.parametrize("how", ["hidden", "inactive"])
def test_BLD_F029_DEC_104_a_lead_who_is_not_named_stays_the_lead_until_the_requester_is_on_the_crew(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, how: str
) -> None:
    ravi, kavya, ref = cast["ravi"], cast["kavya"]["id"], cast["lead"]["idea_id"]
    _unnamed(db, ravi, how)
    # The sheet's two reads (C-SHEET-TEAMUP.compose): the lead is lane C's hidden person, with no users.id.
    note = requests.draft_note(db, ref, kavya)
    before = requests.my_state(db, ref, kavya)
    _hidden_lead(note["lead"])
    _hidden_lead(before["lead"])
    _no_trace_of(ravi, note, before)
    # Sent: "Waiting for the lead" on the opener (C-SHEET-TEAMUP.after), in every read the requester makes.
    sent = _send(db, cast)
    assert sent["after"]["line"] == "Waiting for the lead"
    assert (
        sent["after"]["detail"]
        == "The lead reads your note, then approves or declines. You’ll hear in your Inbox."
    )
    waiting = requests.my_state(db, ref, kavya)
    assert waiting["after"]["line"] == "Waiting for the lead" and waiting["why_not"] == "already_requested"
    again = _refused(_send, db, cast)
    assert (again.status, again.code, again.message) == (409, "already_requested", "Waiting for the lead")
    read = requests.read(db, sent["id"], kavya)
    assert read["after"]["line"] == "Waiting for the lead"
    _no_trace_of(ravi, sent, waiting, again.body(), read)
    # Declined: Kavya is not on the crew, so the lead stays unnamed in the reason line.
    requests.answer(db, sent["id"], ravi["id"], {"answer": "decline", "reason": "The crew is full for now"})
    declined = requests.read(db, sent["id"], kavya)
    assert declined["after"]["line"] == "The lead declined: “The crew is full for now”."
    after_no = requests.my_state(db, ref, kavya)
    _hidden_lead(after_no["lead"])
    _no_trace_of(ravi, declined, after_no)
    # Approved: Kavya is on the crew now, and the crew sees the lead's name (BLD-F042).
    second = _send(db, cast)
    requests.answer(db, second["id"], ravi["id"], {"answer": "team_only"})
    on_crew = requests.my_state(db, ref, kavya)
    assert on_crew["me"] == "crew"
    assert (on_crew["lead"]["id"], on_crew["lead"]["name"]) == (ravi["id"], ravi["name"])
    assert requests.read(db, second["id"], kavya)["after"]["state"] == "on_crew"


@pytest.mark.parametrize("how", ["hidden", "inactive"])
def test_BLD_F029_a_draft_merge_request_says_the_lead_and_carries_no_users_id(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, how: str
) -> None:
    ravi, kavya = cast["ravi"], cast["kavya"]["id"]
    _unnamed(db, ravi, how)
    draft = f.draft(db, cast["kavya"])
    body = {"other_idea_id": cast["lead"]["idea_id"], "note": NOTE}
    asked = drafts.ask(db, str(draft["id"]), kavya, body)
    _hidden_lead(asked["lead"])
    assert asked["after"]["label"] == "Waiting on the lead to merge"
    assert asked["after"]["line"] == (
        "Waiting for the lead to accept the merge. If the lead declines, you can send yours on its own."
    )
    again = _refused(drafts.ask, db, str(draft["id"]), kavya, body)
    assert (again.code, again.message) == ("already_requested", "Waiting on the lead to merge")
    state = drafts.state(db, str(draft["id"]), kavya)
    _no_trace_of(ravi, asked, again.body(), state)
    requests.answer(db, asked["id"], ravi["id"], {"answer": "decline", "reason": REASON})
    kept = drafts.state(db, str(draft["id"]), kavya)
    assert kept["after"]["label"] == "The lead kept it separate"
    _no_trace_of(ravi, kept)


def test_BLD_F029_DEC_104_the_desk_and_the_committee_and_the_crew_always_see_the_lead(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    ravi, ref = cast["ravi"], cast["lead"]["idea_id"]
    _unnamed(db, ravi, "hidden")
    for role in ("reviewer", "committee", "core_chair"):
        desk = f.person(db, f"Meera Pillai {role.title()}", roles=(role,))
        seen = requests.my_state(db, ref, desk["id"])
        assert (seen["lead"]["id"], seen["lead"]["name"]) == (ravi["id"], ravi["name"]), role
        assert requests.draft_note(db, ref, desk["id"])["lead"]["first_name"] == "Ravi", role
    # Asha is on Ravi's crew: she sees his name too; Ravi sees his own.
    assert requests.my_state(db, ref, cast["asha"]["id"])["lead"]["name"] == ravi["name"]
    assert requests.my_state(db, ref, ravi["id"])["lead"]["name"] == ravi["name"]
    # A lead who shows their name is named to everyone, as before.
    shown = f.person(db, "Gopal Iyengar")
    open_idea = f.idea(db, shown, title="Branch tokens run out by noon")
    seen = requests.my_state(db, open_idea["idea_id"], cast["kavya"]["id"])
    assert (seen["lead"]["id"], seen["lead"]["first_name"]) == (shown["id"], "Gopal")
    sent = requests.send(
        db, open_idea["idea_id"], cast["kavya"]["id"], {"note": NOTE, "brought_idea_ids": []}
    )
    assert sent["after"]["line"] == "Waiting for Gopal"


@pytest.mark.parametrize("how", ["hidden", "inactive"])
def test_BLD_F029_DEC_104_C_SHEET_TEAMUP_after_a_member_who_left_the_crew_reads_the_lead_again_and_team_up(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, how: str
) -> None:
    """Once off the crew, a requester whose request was approved is a stranger to a lead who is not named again: no
    name or users.id, and their approved request no longer shows "You’re on the crew" (`after_for`: an `approved_*`
    request with no crew role gives no `after`, so the screen offers Team up again). BLD-F093 pins it."""
    ravi, kavya, ref = cast["ravi"], cast["kavya"]["id"], cast["lead"]["idea_id"]
    _unnamed(db, ravi, how)
    sent = _send(db, cast)
    requests.answer(db, sent["id"], ravi["id"], {"answer": "team_only"})
    assert requests.my_state(db, ref, kavya)["lead"]["name"] == ravi["name"]  # on the crew: named (BLD-F042)
    crew.leave(db, ref, kavya)
    gone = requests.my_state(db, ref, kavya)
    _hidden_lead(gone["lead"])
    assert gone["me"] is None and gone["request"]["state"] == "approved_team_only"
    assert gone["after"] is None and gone["can_request"] is True and gone["why_not"] is None
    read = requests.read(db, sent["id"], kavya)
    assert read["after"] is None
    note = requests.draft_note(db, ref, kavya)
    _hidden_lead(note["lead"])
    _no_trace_of(ravi, gone, read, note)


def test_BLD_F029_DEC_104_a_core_committee_viewer_reads_a_hidden_leads_name(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    """`lead_seen_by` names the lead to anyone `similar.preview.Viewer.of(...).desk` counts: DESK_ROLES there are
    reviewer, committee, core_committee and core_chair, so a core_committee holder reads the name of a lead who hid
    it, as the review desk and the Ones Committee do (DEC-104, P-PRODUCT.privacy; DEC-121: committee members hold
    core_committee at launch). Pinned by BLD-F093 beside the reviewer, committee and core_chair cases above."""
    ravi, ref = cast["ravi"], cast["lead"]["idea_id"]
    _unnamed(db, ravi, "hidden")
    core = f.person(db, "Sunita Bhatt", roles=("core_committee",))
    seen = requests.my_state(db, ref, core["id"])
    assert (seen["lead"]["id"], seen["lead"]["name"]) == (ravi["id"], ravi["name"])
    assert requests.draft_note(db, ref, core["id"])["lead"]["first_name"] == "Ravi"
    # Without the role, the same person reads "the lead"
    db.execute("UPDATE role_grants SET valid_to = now() WHERE user_id = %s", (core["id"],))
    _hidden_lead(requests.my_state(db, ref, core["id"])["lead"])


def test_BLD_F075_the_lead_still_reads_the_name_of_a_requester_who_hid_theirs_from_the_wall(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    """The sheet tells the requester "Ravi sees your name, your note." before they send (Crew.md), and Profile's
    switch is about the Wall next to their shared ideas (S-H6), so the lead they chose to ask reads who they are."""
    _unnamed(db, cast["kavya"], "hidden")
    sent = _send(db, cast, [cast["mine"]["idea_id"]])
    lead_view = requests.read(db, sent["id"], cast["ravi"]["id"])
    assert lead_view["reader"]["line"] == "Kavya Menon asks to team up and merge their idea into yours"
    assert lead_view["from"]["name"] == "Kavya Menon"
    assert lead_view["brought"][0]["byline"].startswith("Kavya Menon, Investor service, Hyderabad.")


def test_the_fixtures_leave_no_people_or_ideas_behind(
    db: Conn, cast: dict[str, Any], held: dict[str, Any]
) -> None:
    requests.answer(db, held["asked"]["id"], cast["ravi"]["id"], {"answer": "merge"})
    f.clean(db)
    for table in ("users", "contributor_map", "ideas", "crew_members", "merge_requests", "merges"):
        assert db.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == 0, table  # noqa: S608
