"""L-TEAMUP on the database: asking, withdrawing, the lead's three answers and what each does, closing with the
idea, leaving and removal (V-ACC.teamup/4–6 server side, V-ACC.similar/8, L-TEAMUP.rules/1, /4, /6, states)."""

from __future__ import annotations

from typing import Any

import pytest

from core.db import Conn
from onepc.context import open_text
from teamup import adapters, crew, requests
from teamup.store import Refused
from tests import f_teamup_fixtures as f

NOTE = "I take these calls at our Hyderabad branch every day, about 40 a day, and most are about R07."


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
    for status in ("withdrawn", "merged", "not_picked", "not_now"):
        closed = f.idea(db, cast["ravi"], status=status)
        r = _refused(requests.send, db, closed["idea_id"], cast["kavya"]["id"], body)
        assert (r.status, r.code) == (409, "idea_closed")
    draft = f.draft(db, cast["ravi"])
    assert _refused(requests.send, db, str(draft["id"]), cast["kavya"]["id"], body).status == 404
    assert _refused(requests.send, db, lead_ref, cast["kavya"]["id"], {"note": "x" * 29}).code == "note_too_short"
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


def test_L_TEAMUP_rules_4_one_open_request_per_person_per_idea(db: Conn, cast: dict[str, Any], inbox: f.Inbox) -> None:
    first = _send(db, cast)
    again = _refused(_send, db, cast)
    assert (again.status, again.code, again.message) == (409, "already_requested", "Waiting for Ravi")
    requests.withdraw(db, first["id"], cast["kavya"]["id"])
    second = _send(db, cast)
    assert second["id"] != first["id"]
    assert inbox.resolved == [f"teamup_request:{first['id']}"]


def test_the_same_idempotency_key_returns_the_first_request(db: Conn, cast: dict[str, Any], inbox: f.Inbox) -> None:
    body = {"note": NOTE, "brought_idea_ids": []}
    a = requests.send(db, cast["lead"]["idea_id"], cast["kavya"]["id"], body, "key-0001-teamup")
    b = requests.send(db, cast["lead"]["idea_id"], cast["kavya"]["id"], body, "key-0001-teamup")
    assert a["id"] == b["id"] and len(inbox.of("teamup_request")) == 1


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
    assert b["id"] == cast["mine"]["idea_id"] and b["byline"].startswith("Kavya Menon, Investor service, Hyderabad.")
    assert b["summary"] == cast["mine"]["summary"]
    assert [a["label"] for a in page["answers"]] == ["Decline", "Team up only", "Merge it"]
    assert page["reader"]["kind"] == "Merge request"
    (item,) = inbox.of("teamup_request")
    assert item["refs"]["brought"] == 1 and [a.op for a in item["actions"]] == [
        "teamup.answer.decline", "teamup.answer.team_only", "teamup.answer.merge",
    ]  # fmt: skip
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
    assert out["say_hello"] == {"label": "Say hello to Kavya", "to": f"/ideas/{cast['lead']['idea_id']}/conversation"}
    assert out["request"]["state"] == "approved_merged"
    # L-MERGE.effects/1, /4, /5
    assert f.status_of(db, cast["mine"]) == {"status": "merged", "merged_into": cast["lead"]["id"]}
    m = db.execute("SELECT * FROM merges WHERE merged_idea_uuid = %s", (cast["mine"]["id"],)).fetchone()
    assert m["via"] == "lead_accepted" and m["by_code"] == cast["ravi"]["code"]
    assert str(m["teamup_request_id"]) == sent["id"] and m["prior_status"] == "with_review_desk"
    assert db.execute("SELECT state FROM question_sets WHERE idea_uuid = %s", (cast["mine"]["id"],)).fetchone()[
        "state"
    ] == "closed"
    crew_now = f.live_crew(db, cast["lead"])
    assert crew_now[cast["kavya"]["code"]] == "crew" and crew_now[kavya_crew["code"]] == "crew"
    assert crew_now[cast["ravi"]["code"]] == "lead" and list(crew_now.values()).count("lead") == 1
    vias = {r["contributor_code"]: r["via"] for r in f.crew_rows(db, cast["lead"])}
    assert vias[cast["kavya"]["code"]] == "merge"
    # conversation lines, IDs only
    lead_events = [e for e, _ in f.events(db, cast["lead"])]
    assert lead_events[:2] == ["teamup.approved_merged", "crew.joined"] and "merge.from" in lead_events
    assert ("merge.into", {"merge_id": str(m["id"]), "idea_id": cast["lead"]["idea_id"]}) in f.events(db, cast["mine"])
    # the requester is told at once; the crew already there hears who joined; the lead's ask is resolved
    (told,) = inbox.of("teamup_answer")
    assert told["recipients"] == [cast["kavya"]["id"]]
    assert told["refs"] == {"request_id": sent["id"], "request": "teamup", "answer": "merge", "has_reason": False}
    joined = inbox.of("crew_joined")
    assert joined and all(p["recipients"] == [cast["asha"]["id"]] and p["refs"] == {"via": "merge"} for p in joined)
    assert f"teamup_request:{sent['id']}" in inbox.resolved
    after = requests.my_state(db, cast["lead"]["idea_id"], cast["kavya"]["id"])
    assert after["me"] == "crew" and after["after"]["line"] == f"Merged into {cast['lead']['idea_id']}, with credit to you."


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
    assert mine["can_request"] is True and mine["after"]["line"].startswith("Ravi declined: “The crew is full for now")
    for a in f.audit_rows(db, "teamup."):
        assert "full" not in str(a["after"]) and "9876543210" not in str(a["after"])


def test_L_TEAMUP_rules_6_with_nothing_brought_merge_is_refused(db: Conn, cast: dict[str, Any], inbox: f.Inbox) -> None:
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
    assert len(f.audit_rows(db, "teamup.answer_refused")) == 2
    assert f.status_of(db, cast["mine"])["status"] == "with_review_desk"
    assert db.execute("SELECT count(*) AS n FROM merges").fetchone()["n"] == 0


def test_an_answer_is_given_once(db: Conn, cast: dict[str, Any], inbox: f.Inbox) -> None:
    sent = _send(db, cast)
    requests.answer(db, sent["id"], cast["ravi"]["id"], {"answer": "decline"})
    assert _refused(requests.answer, db, sent["id"], cast["ravi"]["id"], {"answer": "team_only"}).code == "not_waiting"
    assert _refused(requests.withdraw, db, sent["id"], cast["kavya"]["id"]).code == "not_waiting"
    assert _refused(requests.answer, db, sent["id"], cast["ravi"]["id"], {"answer": "maybe"}).code == "answer_required"


def test_L_TEAMUP_states_closed_when_the_idea_closes_first(db: Conn, cast: dict[str, Any], inbox: f.Inbox) -> None:
    sent = _send(db, cast)
    db.execute("UPDATE ideas SET status = 'withdrawn' WHERE id = %s", (cast["lead"]["id"],))
    r = _refused(requests.answer, db, sent["id"], cast["ravi"]["id"], {"answer": "team_only"})
    assert r.code == "idea_closed"
    state = db.execute("SELECT state FROM teamup_requests WHERE id = %s", (sent["id"],)).fetchone()["state"]
    assert state == "closed" and f"teamup_request:{sent['id']}" in inbox.resolved
    mine = requests.my_state(db, cast["lead"]["idea_id"], cast["kavya"]["id"])
    assert mine["why_not"] == "idea_closed" and mine["after"] is None


def test_a_merge_closes_requests_waiting_on_the_merged_idea(db: Conn, cast: dict[str, Any], inbox: f.Inbox) -> None:
    pradeep = f.person(db, "Pradeep Kumar")
    on_mine = requests.send(db, cast["mine"]["idea_id"], pradeep["id"], {"note": NOTE, "brought_idea_ids": []})
    sent = _send(db, cast, [cast["mine"]["idea_id"]])
    requests.answer(db, sent["id"], cast["ravi"]["id"], {"answer": "merge"})
    state = db.execute("SELECT state FROM teamup_requests WHERE id = %s", (on_mine["id"],)).fetchone()["state"]
    assert state == "closed" and f"teamup_request:{on_mine['id']}" in inbox.resolved


# --- L-TEAMUP.rules/11: leaving and removal ---------------------------------------------------------------------
def test_L_TEAMUP_rules_11_a_member_leaves_and_the_lead_removes(db: Conn, cast: dict[str, Any], inbox: f.Inbox) -> None:
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
    assert [a["action"] for a in f.audit_rows(db, "crew.")] == ["crew.leave", "crew.remove_refused", "crew.remove"]
    # a member who left can ask again
    assert _send(db, cast)["state"] == "sent"


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
    fake = types.ModuleType("convo")
    fake.post = lambda conn, idea_uuid, event, **kw: calls.append((idea_uuid, event, kw)) or "id"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "convo", fake)
    adapters.say(None, "idea-uuid", "crew.left", author_code="CTR-0a1b2c")  # type: ignore[arg-type]
    assert calls == [("idea-uuid", "crew.left", {"author_user_id": None, "author_code": "CTR-0a1b2c", "payload": None,
                                                  "question_set_id": None, "entry_type": "event", "at": None})]  # fmt: skip
