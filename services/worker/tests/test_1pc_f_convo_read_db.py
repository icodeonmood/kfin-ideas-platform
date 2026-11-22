"""L-CONVO reading: who may read (L-CONVO/2), the timeline (/3, /4), the box and its lines (/5), the side panel (/8).
J-TEAMUP steps 5–6: the conversation opens to the new crew member, earlier entries included. Synthetic people only.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from typing import Any

import pytest

from convo import post
from convo.reads import conversation
from convo.store import Refused
from ideapage import read as page_read
from ideapage.shape import at_desk
from tests import convo_fixtures as fx

NOW = fx.at(17, 10, 30)  # Tuesday 17 November 2026, IST


@pytest.fixture
def db(db: Any) -> Iterator[Any]:
    """The shared `db` fixture, plus clean-up: the people and ideas these tests made are deleted when each test ends."""
    yield db
    fx.clean(db)


def texts(view: dict[str, Any]) -> list[str]:
    return [e["text"] for e in view["entries"] if e["type"] == "event"]


def refused(fn: Any, *args: Any, **kwargs: Any) -> Refused:
    with pytest.raises(Refused) as caught:
        fn(*args, **kwargs)
    return caught.value


@pytest.fixture
def cast(db: Any) -> dict[str, Any]:
    kavya = fx.person(db, "Kavya Menon")
    meera = fx.person(db, "Meera Iyer", roles=(("reviewer", None),))
    rohan = fx.person(db, "Rohan Mehta", roles=(("committee", None),))
    ravi = fx.person(db, "Ravi Nair")
    colleague = fx.person(db, "Tara Joshi")
    return {"kavya": kavya, "meera": meera, "rohan": rohan, "ravi": ravi, "colleague": colleague}


def test_l_convo_1_one_conversation_found_by_reference_or_uuid_and_none_for_a_draft(
    db: Any, cast: dict[str, Any]
) -> None:
    idea = fx.idea(db, cast["kavya"])
    by_ref = conversation(db, idea["idea_id"], cast["kavya"]["id"], at=NOW)
    by_uuid = conversation(db, str(idea["id"]), cast["kavya"]["id"], at=NOW)
    assert by_ref["entries"] == by_uuid["entries"] and by_ref["idea"]["id"] == idea["idea_id"]
    draft = fx.idea(db, cast["kavya"], status="draft")
    assert refused(conversation, db, draft["idea_id"], cast["kavya"]["id"]).status == 404


def test_l_convo_2_sharer_desk_and_committee_read_from_the_start_anyone_else_gets_404(
    db: Any, cast: dict[str, Any]
) -> None:
    idea = fx.idea(db, cast["kavya"])
    mine = conversation(db, idea["idea_id"], cast["kavya"]["id"], at=NOW)
    assert mine["audience"] == "you_and_desk"
    assert mine["composer"]["visibility"] == "Only you and the review desk see this conversation."
    assert mine["composer"]["placeholder"] == "Message the review desk"
    assert mine["header"] == {"whose": "Your idea", "line": "Your idea, shared Saturday 14 November"}
    desk = conversation(db, idea["idea_id"], cast["meera"]["id"], at=NOW)
    assert desk["composer"]["placeholder"] == "Reply to Kavya"
    assert desk["composer"]["visibility"] == "Only Kavya and the review desk see this conversation."
    assert desk["header"]["line"] == "Kavya Menon’s idea, Investor service, Hyderabad"
    conversation(db, idea["idea_id"], cast["rohan"]["id"], at=NOW)  # L-AUDIT.permissions: the committee reads
    err = refused(conversation, db, idea["idea_id"], cast["colleague"]["id"])
    assert (err.status, err.code) == (404, "not_found")  # never 403


def test_j_teamup_5_6_l_convo_2_a_crew_member_who_joins_later_reads_earlier_entries(
    db: Any, cast: dict[str, Any]
) -> None:
    ravi, kavya, meera = cast["ravi"], cast["kavya"], cast["meera"]
    idea = fx.idea(
        db,
        ravi,
        title="Rejection SMS codes confuse investors",
        shared_at=fx.at(9, 11),
        opened_by=meera["id"],
        reviewer_id=meera["id"],
        opened_at=fx.at(16, 9, 50),
    )  # as lane B opens it
    post(db, str(idea["id"]), "desk.opened", author_user_id=meera["id"], at=fx.at(16, 9, 50))
    from convo.messages import send

    send(
        db,
        idea["idea_id"],
        ravi["id"],
        {"text": "Branch logs for R07 are attached in the idea."},
        at=fx.at(16, 12),
    )
    assert refused(conversation, db, idea["idea_id"], kavya["id"]).status == 404  # not on the crew yet

    request_id = db.execute(
        "INSERT INTO teamup_requests (idea_uuid, from_code, note_encrypted, state, answered_by_code, answered_at) "
        "VALUES (%s, %s, '\\x00', 'approved_team_only', %s, %s) RETURNING id",
        (idea["id"], kavya["code"], ravi["code"], fx.at(17, 10, 5)),
    ).fetchone()["id"]
    fx.join_crew(db, idea, kavya, fx.at(17, 10, 5))
    post(db, str(idea["id"]), "teamup.approved_team_only", author_code=ravi["code"],
         payload={"request_id": str(request_id)}, at=fx.at(17, 10, 5))  # fmt: skip
    post(db, str(idea["id"]), "crew.joined", author_code=kavya["code"], at=fx.at(17, 10, 5))

    view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
    assert texts(view) == [  # DEC-111: the crew reads the review desk, not the person at it
        "Ravi Nair shared it. Monday 9 November",
        "The review desk opened it. Monday 16 November, 9:50 am",
        "Ravi Nair approved your team-up request. Today, 10:05 am",
        "You joined the crew. 10:05 am",
    ]
    [earlier] = [e for e in view["entries"] if e["type"] == "message"]
    assert (
        earlier["text"] == "Branch logs for R07 are attached in the idea."
        and earlier["from_label"] == "Ravi Nair"
    )
    assert view["audience"] == "crew_and_desk"
    assert view["composer"]["placeholder"] == "Message the crew"
    assert view["composer"]["visibility"] == "The crew and the review desk see this conversation."
    assert view["header"] == {"whose": "The idea", "line": "Ravi Nair’s idea, Investor service, Hyderabad"}
    assert [(p["label"], p["doing"]) for p in view["participants"]] == [
        ("The review desk", "Reviewing it"),
        ("Ravi Nair", "Shared the idea"),
        ("You", "Joined today"),
    ]
    lead = conversation(db, idea["idea_id"], ravi["id"], at=NOW)
    assert "You approved Kavya Menon’s team-up request. Today, 10:05 am" in texts(lead)
    assert "Kavya Menon joined the crew. 10:05 am" in texts(lead)

    fx.leave_crew(db, idea, kavya)
    assert refused(conversation, db, idea["idea_id"], kavya["id"]).status == 404


def test_j_teamup_6_l_convo_5_both_talk_the_new_crew_member_says_hello_and_the_lead_replies(
    db: Any, cast: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """J-TEAMUP/5 hands over "Say hello" (the conversation, open to Kavya); /6 both talk on S-08. Kavya's message
    tells Ravi, the sharer (`comment`); Ravi's reply tells nobody, since only the sharer hears of comments."""
    from convo.messages import send

    told: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "convo.adapters.notify_post", lambda conn, kind, to, **kw: told.append({"kind": kind, "to": to, **kw})
    )
    ravi, kavya = cast["ravi"], cast["kavya"]
    idea = fx.idea(db, ravi, title="Rejection SMS codes confuse investors", shared_at=fx.at(9, 11))
    fx.join_crew(db, idea, kavya, fx.at(17, 10, 5))
    post(db, str(idea["id"]), "crew.joined", author_code=kavya["code"], at=fx.at(17, 10, 5))
    hello = send(db, idea["idea_id"], kavya["id"], {"text": "Hello Ravi, happy to help with the R07 calls."},
                 at=fx.at(17, 10, 6))  # fmt: skip
    assert hello["entry"]["from_label"] == "You" and hello["entry"]["you"]
    assert [(c["kind"], c["to"], c["refs"]) for c in told] == [
        ("comment", [ravi["id"]], {"entry_id": hello["entry"]["id"]})
    ]
    told.clear()
    reply = send(
        db, idea["idea_id"], ravi["id"], {"text": "Welcome to the crew, Kavya."}, at=fx.at(17, 10, 7)
    )
    assert told == []  # the sharer writing tells nobody; the crew reads it in the conversation
    view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
    said = [(e["from_label"], e["text"], e["at_label"]) for e in view["entries"] if e["type"] == "message"]
    assert said == [
        ("You", "Hello Ravi, happy to help with the R07 calls.", "Today, 10:06 am"),
        ("Ravi Nair", "Welcome to the crew, Kavya.", "Today, 10:07 am"),
    ]
    on_lead = conversation(db, idea["idea_id"], ravi["id"], at=NOW)
    assert [e["id"] for e in on_lead["entries"] if e["type"] == "message"] == [
        hello["entry"]["id"],
        reply["entry"]["id"],
    ]
    assert ("Kavya Menon", "Joined today") in [(p["label"], p["doing"]) for p in on_lead["participants"]]


def test_j_similar_6a_l_merge_effects_a_draft_merged_in_reads_right_on_the_leads_conversation(
    db: Any, cast: dict[str, Any]
) -> None:
    """Ravi merges Kavya's draft into his idea (a draft merge request, BLD-F010): the draft has no reference, so the
    line names whose idea it was; Kavya, now on the crew, reads the lead's conversation."""
    ravi, kavya = cast["ravi"], cast["kavya"]
    lead = fx.idea(db, ravi, title="Rejection SMS codes confuse investors", shared_at=fx.at(9, 11))
    draft = fx.idea(db, kavya, status="merged", idea_id=None, shared_at=None)
    asked = db.execute(
        "INSERT INTO merge_requests (draft_uuid, other_idea_uuid, from_code, note_encrypted, state, answered_by_code, "
        "answered_at) VALUES (%s, %s, %s, '\\x00', 'accepted', %s, %s) RETURNING id",
        (draft["id"], lead["id"], kavya["code"], ravi["code"], fx.at(17, 10, 5)),
    ).fetchone()["id"]
    merge_id = db.execute(
        "INSERT INTO merges (lead_idea_uuid, merged_idea_uuid, via, by_code, merge_request_id) "
        "VALUES (%s, %s, 'lead_accepted', %s, %s) RETURNING id",
        (lead["id"], draft["id"], ravi["code"], asked),
    ).fetchone()["id"]
    fx.join_crew(db, lead, kavya, fx.at(17, 10, 5))
    uuid_, t = str(lead["id"]), fx.at(17, 10, 5)
    with db.transaction():  # one answer writes all three lines at one time, as F1 does
        post(db, uuid_, "teamup.approved_merged", author_code=ravi["code"],
             payload={"request_id": str(asked), "request": "merge"}, at=t)  # fmt: skip
        post(db, uuid_, "crew.joined", author_code=kavya["code"], payload={"via": "merge"}, at=t)
        post(db, uuid_, "merge.from", author_code=ravi["code"], payload={"merge_id": str(merge_id), "idea_id": None},
             at=t)  # fmt: skip
    assert texts(conversation(db, lead["idea_id"], kavya["id"], at=NOW)) == [
        "Ravi Nair shared it. Monday 9 November",
        "Ravi Nair approved your team-up request. Today, 10:05 am",
        "You joined the crew. 10:05 am",
        "Your idea is now part of it, with credit to you. 10:05 am",
    ]
    assert texts(conversation(db, lead["idea_id"], ravi["id"], at=NOW))[1:] == [
        "You approved Kavya Menon’s team-up request. Today, 10:05 am",
        "Kavya Menon joined the crew. 10:05 am",
        "Kavya Menon’s idea is now part of it, with credit to them. 10:05 am",
    ]


def test_l_convo_2_the_build_team_reads_once_chosen(db: Any, cast: dict[str, Any]) -> None:
    arjun = fx.person(db, "Arjun Rao")
    idea = fx.idea(db, cast["kavya"], title="Plain words for transaction rejections", status="being_built")
    assert refused(conversation, db, idea["idea_id"], arjun["id"]).status == 404
    fx.build_team(db, idea, arjun)
    view = conversation(db, idea["idea_id"], arjun["id"], at=NOW)
    assert view["audience"] == "build_team"
    mine = conversation(db, idea["idea_id"], cast["kavya"]["id"], at=NOW)
    assert mine["composer"]["placeholder"] == "Message the build team"
    assert mine["composer"]["visibility"] == "You, the build team and the review desk see this conversation."
    assert mine["header"]["line"] == "Your idea, being built by Arjun Rao’s team"  # S-08.layout/1
    assert ("Arjun Rao", "Leads the build team") in [(p["label"], p["doing"]) for p in mine["participants"]]


def test_l_convo_3_event_lines_render_at_read_time_with_names_and_you(db: Any, cast: dict[str, Any]) -> None:
    kavya, meera, rohan = cast["kavya"], cast["meera"], cast["rohan"]
    idea = fx.idea(db, kavya)
    other_a, other_b = fx.idea(db, cast["ravi"]), fx.idea(db, cast["ravi"])
    db.execute(
        "INSERT INTO idea_status_history (idea_uuid, from_status, to_status, at) VALUES (%s, 'checking', "
        "'with_review_desk', %s)",
        (idea["id"], fx.at(14, 10, 6)),
    )
    db.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked) VALUES (%s, 'message', 'm1', "
        "'folio', 'Folio ••••89')",
        (idea["id"],),
    )
    for other in (other_a, other_b):
        db.execute(
            "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason) VALUES (%s, %s, 'close', 'R07')",
            (idea["id"], other["id"]),
        )
    uuid_ = str(idea["id"])
    post(db, uuid_, "desk.opened", author_user_id=meera["id"], at=fx.at(16, 9, 50))
    post(db, uuid_, "desk.decided", author_user_id=meera["id"], payload={"choice": "pick"}, at=fx.at(16, 15))
    post(
        db,
        uuid_,
        "committee.reversed",
        author_user_id=rohan["id"],
        payload={"to": "not_now"},
        at=fx.at(17, 9),
    )
    post(db, uuid_, "desk.back_from_not_now", at=fx.at(17, 9, 30))
    view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
    assert texts(view) == [
        "You shared it. Saturday 14 November, 10:05 am",
        "Checked and matched. 1 folio number hidden, 2 similar ideas found. 10:06 am",
        "The review desk opened it. Monday 16 November, 9:50 am",  # DEC-111
        "The review desk picked it. 3:00 pm",
        "The Ones Committee reversed the decision. It’s now Not now. Today, 9:00 am",  # DEC-113
        "It’s back with the review desk. 9:30 am",
    ]
    as_meera = texts(conversation(db, idea["idea_id"], meera["id"], at=NOW))
    assert "You opened it. Monday 16 November, 9:50 am" in as_meera
    assert "Kavya Menon shared it. Saturday 14 November, 10:05 am" in as_meera
    as_rohan = texts(
        conversation(db, idea["idea_id"], rohan["id"], at=NOW)
    )  # the committee sees the desk's names
    assert "Meera from the review desk opened it. Monday 16 November, 9:50 am" in as_rohan
    assert "You reversed the decision. It’s now Not now. Today, 9:00 am" in as_rohan


def test_l_convo_3_dec_127_bld_c223_checked_counts_only_the_ideas_own_files_never_a_conversation_file(
    db: Any, cast: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """L-CONVO/3, DEC-127 (2), BLD-C223: "Checked and matched. N … hidden" counts what the check hid in what was shared,
    the idea's own files included. A file added for the conversation, sent or not, found or not, and its name's
    detail never change the line the lead, the crew or anyone else reads (lane C's finding, 22 Nov)."""
    from convo.messages import send

    monkeypatch.setattr("convo.adapters.notify_post", lambda conn, kind, to, **kw: None)
    kavya, meera, ravi = cast["kavya"], cast["meera"], cast["ravi"]
    idea = fx.idea(db, kavya, status="picked")
    fx.join_crew(db, idea, ravi)
    db.execute(
        "INSERT INTO idea_status_history (idea_uuid, from_status, to_status, at) VALUES (%s, 'checking', "
        "'with_review_desk', %s)",
        (idea["id"], fx.at(14, 10, 6)),
    )
    own = fx.attachment(db, idea, kavya, purpose="idea", name="proof-screenshot.png")
    unsent = fx.attachment(db, idea, meera, file_state="personal_data_found", name="calls-week-47.xlsx")
    sent = fx.attachment(db, idea, kavya, name="branch-call-log.pdf")
    send(db, idea["idea_id"], kavya["id"], {"text": "Here it is.", "file_ids": [sent]}, at=fx.at(17, 10, 6))
    for source, source_id in (("message", "m1"), ("file", own)):  # what was shared: 2 folio numbers
        db.execute(
            "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked) VALUES (%s, %s, %s, 'folio', "
            "'Folio ••••89')",
            (idea["id"], source, source_id),
        )
    for source_id in (unsent, f"{unsent}:name", sent, f"{sent}:name"):  # conversation files: never counted
        db.execute(
            "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked) VALUES (%s, 'file', %s, "
            "'folio', 'Folio ••••89')",
            (idea["id"], source_id),
        )
    for who in (kavya, meera, ravi):  # the sharer, the desk and the crew read the same line
        [line] = [
            t for t in texts(conversation(db, idea["idea_id"], who["id"], at=NOW)) if t.startswith("Checked")
        ]
        assert line.startswith("Checked and matched. 2 folio numbers hidden, no similar ideas found."), who[
            "name"
        ]


def test_l_convo_3_bld_f103_checked_never_counts_an_answers_file_sent_or_not(
    db: Any, cast: dict[str, Any]
) -> None:
    """L-CONVO/3, BLD-F103 (lane C's note after r4): a file added with an answer to the review desk is the idea's
    (`purpose` 'idea', no conversation entry) but was never shared at the check, so its details, sent or not, never
    change the "Checked and matched" line the sharer, the desk and the crew read (as lane B's BLD-B247 leaves an
    unsent answer's files out at the desk)."""
    kavya, meera, ravi = cast["kavya"], cast["meera"], cast["ravi"]
    idea = fx.idea(db, kavya, status="picked")
    fx.join_crew(db, idea, ravi)
    db.execute(
        "INSERT INTO idea_status_history (idea_uuid, from_status, to_status, at) VALUES (%s, 'checking', "
        "'with_review_desk', %s)",
        (idea["id"], fx.at(14, 10, 6)),
    )
    set_id = fx.question_set(db, idea, meera, ("evidence", "often"), fx.at(16, 9))
    fx.answer_all(db, set_id, kavya, fx.at(16, 9, 30))
    answers = [
        str(r["id"])
        for r in db.execute(
            "SELECT a.id FROM answers a JOIN questions q ON q.id = a.question_id WHERE q.set_id = %s ORDER BY q.seq",
            (set_id,),
        ).fetchall()
    ]
    db.execute("UPDATE answers SET sent_at = NULL WHERE id = %s", (answers[1],))  # one answer not yet sent
    db.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked) VALUES (%s, 'message', 'm1', "
        "'folio', 'Folio ••••89')",
        (idea["id"],),
    )
    for answer in answers:  # each answer's file, and its name's detail: never counted
        shot = fx.attachment(db, idea, kavya, purpose="idea", name="sms-screenshot.png")
        db.execute("UPDATE attachments SET answer_id = %s WHERE id = %s", (answer, shot))
        for source_id in (shot, f"{shot}:name"):
            db.execute(
                "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked) VALUES (%s, 'file', %s, "
                "'folio', 'Folio ••••89')",
                (idea["id"], source_id),
            )
    for who in (kavya, meera, ravi):
        [line] = [
            t for t in texts(conversation(db, idea["idea_id"], who["id"], at=NOW)) if t.startswith("Checked")
        ]
        assert line.startswith("Checked and matched. 1 folio number hidden, no similar ideas found."), who[
            "name"
        ]


def test_l_convo_3_a_desk_merge_closes_the_merged_ideas_conversation_with_a_link(
    db: Any, cast: dict[str, Any]
) -> None:
    lead, merged = fx.idea(db, cast["ravi"]), fx.idea(db, cast["kavya"], status="merged")
    merge_id = db.execute(
        "INSERT INTO merges (lead_idea_uuid, merged_idea_uuid, via, by_user_id) VALUES (%s, %s, 'review_desk', %s) "
        "RETURNING id",
        (lead["id"], merged["id"], cast["meera"]["id"]),
    ).fetchone()["id"]
    for i in (lead, merged):
        post(db, str(i["id"]), "desk.merged", author_user_id=cast["meera"]["id"], payload={"merge_id": str(merge_id)},
             at=fx.at(17, 9))  # fmt: skip
    view = conversation(db, merged["idea_id"], cast["kavya"]["id"], at=NOW)
    [line] = [e for e in view["entries"] if e.get("code") == "desk.merged"]
    assert line["text"] == (  # DEC-111
        f"The review desk joined it with {lead['idea_id']}. The conversation carries on there. Today, 9:00 am"
    )
    assert line["link"] == {"label": lead["idea_id"], "to": f"/ideas/{lead['idea_id']}/conversation"}
    assert (
        view["composer"]["closed"]
        == f"This idea is now part of another one. Write in {lead['idea_id']}’s conversation."
    )
    on_lead = conversation(db, lead["idea_id"], cast["ravi"]["id"], at=NOW)
    assert f"The review desk joined it with {merged['idea_id']}. Today, 9:00 am" in texts(on_lead)


def test_l_convo_3_f1_merge_and_crew_codes(db: Any, cast: dict[str, Any]) -> None:
    ravi, kavya = cast["ravi"], cast["kavya"]
    lead, merged = fx.idea(db, ravi), fx.idea(db, kavya, status="merged")
    fx.join_crew(db, lead, kavya)
    post(db, str(merged["id"]), "merge.into", author_code=ravi["code"], payload={"idea_id": lead["idea_id"]},
         at=fx.at(17, 10))  # fmt: skip
    post(db, str(lead["id"]), "merge.from", author_code=ravi["code"], payload={"idea_id": str(merged["id"])},
         at=fx.at(17, 10))  # fmt: skip
    post(db, str(lead["id"]), "crew.removed", author_code=ravi["code"], payload={"member_code": kavya["code"]},
         at=fx.at(17, 10, 10))  # fmt: skip
    assert texts(conversation(db, merged["idea_id"], kavya["id"], at=NOW))[-1] == (
        f"It’s now part of {lead['idea_id']}. The conversation carries on there. Today, 10:00 am"
    )
    on_lead = texts(conversation(db, lead["idea_id"], ravi["id"], at=NOW))
    assert f"{merged['idea_id']} is now part of it, with credit to Kavya Menon. Today, 10:00 am" in on_lead
    assert "You took Kavya Menon off the crew. 10:10 am" in on_lead


def test_l_convo_3_an_unknown_code_renders_nothing_and_is_logged_by_code_only(
    db: Any, cast: dict[str, Any], captured_logs: Any
) -> None:
    idea = fx.idea(db, cast["kavya"])
    entry_id = post(db, str(idea["id"]), "lane.something_new", payload={"ref": "x1"})
    view = conversation(db, idea["idea_id"], cast["kavya"]["id"], at=NOW)
    assert all(e["id"] != entry_id for e in view["entries"])
    logged = [line for line in captured_logs.getvalue().splitlines() if "convo.render.unknown_code" in line]
    assert logged and "lane.something_new" in logged[-1] and entry_id in logged[-1]


def test_l_convo_4_questions_by_reference_with_the_line_above_the_box_then_answers(
    db: Any, cast: dict[str, Any]
) -> None:
    kavya, meera = cast["kavya"], cast["meera"]
    idea = fx.idea(db, kavya, status="needs_you")
    set_id = fx.question_set(db, idea, meera, ("summary", "often", "evidence"), fx.at(16, 11, 20))
    post(db, str(idea["id"]), "desk.asked", author_user_id=meera["id"], payload={"set_id": set_id, "count": 3},
         question_set_id=set_id, entry_type="questions", at=fx.at(16, 11, 20))  # fmt: skip
    view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
    [q] = [e for e in view["entries"] if e["type"] == "questions"]
    assert (q["set_id"], q["state"], q["count"], q["answered"]) == (set_id, "sent", 3, 0)
    assert q["by_label"] == "The review desk" and q["at_label"] == "Monday 16 November, 11:20 am"  # DEC-111
    assert q["by"] == {"id": "", "name": "The review desk", "first_name": "The review desk", "initials": ""}
    # BLD-F065: the card's plain words, for S-08 until lane B's C-QCARD is on main; the deadline as lane B words it.
    assert q["title"] == "The review desk has 3 questions about your idea"
    assert q["deadline"] == (
        "Answer by Thursday 19 November, 11:20 am. One at a time, typed or spoken, and each answer is added to its "
        "part of your idea."
    )
    assert q["answer_url"] == f"/ideas/{idea['idea_id']}/answer"
    [dq] = [
        e
        for e in conversation(db, idea["idea_id"], meera["id"], at=NOW)["entries"]
        if e["type"] == "questions"
    ]
    assert dq["title"] == "You asked 3 questions." and "deadline" not in dq and "answer_url" not in dq
    assert view["composer"]["questions_line"] == (
        "Answer the review desk’s 3 questions with Answer the questions, so each answer lands on its part of your "
        "idea. Write here for anything else."
    )
    assert "empty" not in view
    assert "questions_line" not in conversation(db, idea["idea_id"], meera["id"], at=NOW)["composer"]

    fx.answer_all(db, set_id, kavya, fx.at(16, 16, 32))
    post(db, str(idea["id"]), "sharer.answered", author_code=kavya["code"], payload={"set_id": set_id, "count": 3},
         question_set_id=set_id, entry_type="answers", at=fx.at(16, 16, 32))  # fmt: skip
    view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
    [a] = [e for e in view["entries"] if e["type"] == "answers"]
    assert a["title"] == "Your answers to the review desk’s 3 questions"
    [q] = [e for e in view["entries"] if e["type"] == "questions"]
    if q["state"] == "answered":
        assert q["title"] == "The review desk’s 3 questions, answered" and "answer_url" not in q
    assert [(x["text"], x["added_to_label"]) for x in a["answers"]] == [
        ("Synthetic answer 1.", "The problem"),
        ("Synthetic answer 2.", "How often"),
        ("Synthetic answer 3.", "Attached"),
    ]
    assert "questions_line" not in view["composer"]
    [a2] = [
        e for e in conversation(db, idea["idea_id"], meera["id"], at=NOW)["entries"] if e["type"] == "answers"
    ]
    assert a2["title"] == "Kavya’s answers to your 3 questions"


def test_l_convo_8_s_08_no_messages_yet_and_the_side_panel(db: Any, cast: dict[str, Any]) -> None:
    idea = fx.idea(db, cast["kavya"], opened_by=cast["meera"]["id"], reviewer_id=cast["meera"]["id"])
    view = conversation(db, idea["idea_id"], cast["kavya"]["id"], at=NOW)
    assert view["empty"]["title"] == "No messages yet"
    assert [(p["label"], p["doing"], p["you"]) for p in view["participants"]] == [
        ("The review desk", "Reviewing it", False),  # DEC-111
        ("You", "Shared the idea", True),
    ]


@pytest.mark.parametrize("status", ["checking", "with_review_desk", "needs_you"])
def test_s_08_l_convo_8_bld_f088_no_messages_yet_while_the_idea_is_at_the_review_desk(
    db: Any, cast: dict[str, Any], status: str
) -> None:
    """Messages.md draws "No messages yet" with the review desk: the sharer of an idea being checked or waiting on
    the desk, with no entries yet, reads it under the idea's own lines. `needs_you` is at the desk too (lane E's
    `at_desk`); seeded with no question set, so no questions entry hides the block (f-convo-empty review, BLD-F093)."""
    idea = fx.idea(db, cast["kavya"], status=status)
    assert at_desk(idea)
    view = conversation(db, idea["idea_id"], cast["kavya"]["id"], at=NOW)
    assert {e["type"] for e in view["entries"]} == {"event"}
    assert view["empty"]["title"] == "No messages yet"
    assert view["empty"]["body"].startswith(
        "If the review desk has a question, it shows here and in your Inbox"
    )
    # Only the sharer is told the desk may ask them something
    assert "empty" not in conversation(db, idea["idea_id"], cast["meera"]["id"], at=NOW)


def test_s_08_l_convo_8_bld_f088_a_picked_idea_with_only_event_lines_shows_no_empty_block(
    db: Any, cast: dict[str, Any]
) -> None:
    """Once the desk has decided, the empty block's words (the desk's questions) no longer fit; the board does not
    draw it there, so the sharer reads the event lines alone (NOT DRAWN default)."""
    kavya, meera = cast["kavya"], cast["meera"]
    idea = fx.idea(db, kavya, status="picked", reviewer_id=meera["id"], opened_by=meera["id"])
    post(db, str(idea["id"]), "desk.opened", author_user_id=meera["id"], at=fx.at(16, 9, 50))
    post(db, str(idea["id"]), "desk.decided", author_user_id=meera["id"], payload={"choice": "pick"},
         at=fx.at(16, 15))  # fmt: skip
    view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
    assert {e["type"] for e in view["entries"]} == {"event"}
    assert "The review desk picked it. 3:00 pm" in texts(view)
    assert "empty" not in view


@pytest.mark.parametrize(
    "status", ["picked", "being_built", "shipped", "not_now", "not_picked", "merged", "withdrawn"]
)
def test_s_08_l_convo_8_bld_f088_no_empty_block_once_the_idea_has_left_the_review_desk(
    db: Any, cast: dict[str, Any], status: str
) -> None:
    idea = fx.idea(db, cast["kavya"], status=status)
    view = conversation(db, idea["idea_id"], cast["kavya"]["id"], at=NOW)
    assert not any(e["type"] in ("message", "questions", "answers") for e in view["entries"])
    assert "empty" not in view


def test_s_08_l_convo_8_l_merge_effects_6_bld_f090_a_merge_line_on_the_lead_at_the_desk_drops_the_empty_block(
    db: Any, cast: dict[str, Any]
) -> None:
    """J-SIMILAR/7, J-REVIEW/M3: the lead idea is still with the review desk after Kavya's idea was merged into it.
    S-06's "You and the review desk" counts the merge line (lane E's BLD-E065), so S-08 does not say "No messages
    yet" beside it."""
    ravi, kavya = cast["ravi"], cast["kavya"]
    lead, merged = fx.idea(db, ravi), fx.idea(db, kavya, status="merged")
    post(db, str(lead["id"]), "merge.from", author_code=ravi["code"], payload={"idea_id": str(merged["id"])},
         at=fx.at(17, 10))  # fmt: skip
    view = conversation(db, lead["idea_id"], ravi["id"], at=NOW)
    assert {e["type"] for e in view["entries"]} == {"event"}
    assert "merge.from" in [e["code"] for e in view["entries"]]
    assert "empty" not in view
    assert page_read.merge_line_count(db, str(lead["id"])) == 1  # the line S-06 counts


def test_s_08_l_convo_8_l_merge_effects_6_bld_f090_the_seeds_desk_merge_line_drops_the_empty_block(
    db: Any, cast: dict[str, Any]
) -> None:
    """The seed writes a desk merge as `desk_merged` (BLD-F061); S-08 matches the stored code, as S-06 does."""
    ravi, kavya, meera = cast["ravi"], cast["kavya"], cast["meera"]
    lead, merged = fx.idea(db, ravi), fx.idea(db, kavya, status="merged")
    merge_id = db.execute(
        "INSERT INTO merges (lead_idea_uuid, merged_idea_uuid, via, by_user_id) VALUES (%s, %s, 'review_desk', %s) "
        "RETURNING id",
        (lead["id"], merged["id"], meera["id"]),
    ).fetchone()["id"]
    _seed_line(db, lead, "desk_merged", fx.at(17, 9), {"merge_id": str(merge_id)})
    view = conversation(db, lead["idea_id"], ravi["id"], at=NOW)
    assert f"The review desk joined it with {merged['idea_id']}. Today, 9:00 am" in texts(view)
    assert "desk_merged" in [e["code"] for e in view["entries"]]
    assert "empty" not in view
    assert page_read.merge_line_count(db, str(lead["id"])) == 1


def test_s_08_l_convo_8_bld_f090_any_other_event_line_keeps_the_empty_block(
    db: Any, cast: dict[str, Any]
) -> None:
    """Only a merge line counts: the shared and checked lines and a crew line keep "No messages yet" (Messages.md),
    and S-06 counts none of them."""
    kavya, tara = cast["kavya"], cast["colleague"]
    idea = fx.idea(db, kavya)
    db.execute(
        "INSERT INTO idea_status_history (idea_uuid, from_status, to_status, at) VALUES (%s, 'checking', "
        "'with_review_desk', %s)",
        (idea["id"], fx.at(14, 10, 6)),
    )
    fx.join_crew(db, idea, tara, fx.at(17, 9))
    post(db, str(idea["id"]), "crew.joined", author_code=tara["code"], at=fx.at(17, 9))
    view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
    codes = [e["code"] for e in view["entries"]]
    assert {"idea.shared", "idea.checked", "crew.joined"} <= set(codes)
    assert view["empty"]["title"] == "No messages yet"
    assert page_read.merge_line_count(db, str(idea["id"])) == 0


def test_l_convo_3_times_today_this_week_and_older(db: Any) -> None:
    from convo.render import when

    now = fx.at(17, 10, 30)
    assert when(fx.at(17, 10, 5), now) == "Today, 10:05 am"
    assert when(fx.at(17, 10, 5), now, time_only=True) == "10:05 am"
    assert when(fx.at(14, 10, 5), now) == "Saturday 14 November, 10:05 am"
    assert when(fx.at(15, 18, 40), now) == "Sunday 15 November, 6:40 pm"
    assert when(fx.at(2, 9), now) == "Monday 2 November"
    assert when(fx.at(16, 12, 0), now) == "Monday 16 November, 12:00 pm"
    assert when(dt.datetime(2025, 11, 3, 9, tzinfo=fx.IST), now) == "Monday 3 November 2025"


def test_j_track_9_s_08_layout_1_l_convo_5_bld_f060_a_build_teams_idea_with_a_crew_reads_as_the_board_draws_it(
    db: Any, cast: dict[str, Any]
) -> None:
    """J-TRACK/9 (seed A1): the sharer opens a picked idea being built by a team that has its own name, with a crew
    member on it. The header names the team by its lead, and the sharer reads the board's visibility line."""
    from convo.messages import send

    kavya, ravi = cast["kavya"], cast["ravi"]
    arjun = fx.person(db, "Arjun Rao")
    idea = fx.idea(db, kavya, title="Plain words for transaction rejections", status="being_built")
    fx.join_crew(db, idea, ravi, fx.at(2, 10))
    fx.build_team(db, idea, arjun)
    db.execute("UPDATE build_teams SET name = 'Plain words team' WHERE idea_uuid = %s", (idea["id"],))
    asked = "The first rewritten reasons are ready to try. Please check them before Thursday."
    send(db, idea["idea_id"], arjun["id"], {"text": asked}, at=fx.at(16, 18, 40))

    mine = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
    assert mine["header"] == {"whose": "Your idea", "line": "Your idea, being built by Arjun Rao’s team"}
    assert mine["composer"]["visibility"] == "You, the build team and the review desk see this conversation."
    assert mine["composer"]["placeholder"] == "Message the build team"
    [said] = [e for e in mine["entries"] if e["type"] == "message"]
    assert (said["from_label"], said["text"]) == ("Arjun Rao", asked)

    crew = conversation(db, idea["idea_id"], ravi["id"], at=NOW)
    assert crew["header"]["line"] == "Kavya Menon’s idea, being built by Arjun Rao’s team"
    assert (
        crew["composer"]["visibility"]
        == "The crew, the build team and the review desk see this conversation."
    )
    assert crew["composer"]["placeholder"] == "Message the build team"


def _seed_line(db: Any, idea: dict[str, Any], code: str, at: dt.datetime, payload: dict[str, Any]) -> None:
    """A line as lane E's seed writes it (bootstrap/club_seed.py `_event`): its own code, an ID, no author."""
    from psycopg.types.json import Jsonb

    db.execute(
        "INSERT INTO conversation_entries (idea_uuid, type, event, payload, at) VALUES (%s, 'event', %s, %s, %s)",
        (idea["id"], code, Jsonb(payload), at),
    )


def test_l_convo_3_bld_f061_the_seeds_lines_read_as_the_codes_they_stand_for(
    db: Any, cast: dict[str, Any], captured_logs: Any
) -> None:
    kavya, meera, rohan, ravi = cast["kavya"], cast["meera"], cast["rohan"], cast["ravi"]
    logged_before = len(captured_logs.getvalue())  # the buffer is shared with earlier tests
    arjun = fx.person(db, "Arjun Rao")
    idea = fx.idea(db, kavya, status="being_built")
    db.execute(
        "INSERT INTO idea_status_history (idea_uuid, from_status, to_status, at) VALUES (%s, 'checking', "
        "'with_review_desk', %s)",
        (idea["id"], fx.at(14, 10, 8)),
    )
    decision = db.execute(
        "INSERT INTO idea_decisions (idea_uuid, choice, reason_encrypted, by_user_id, at) "
        "VALUES (%s, 'pick', '\\x00', %s, %s) RETURNING id",
        (idea["id"], meera["id"], fx.at(16, 15)),
    ).fetchone()["id"]
    fx.build_team(db, idea, arjun)
    request = db.execute(
        "INSERT INTO teamup_requests (idea_uuid, from_code, note_encrypted, state, answered_by_code, answered_at) "
        "VALUES (%s, %s, '\\x00', 'approved_team_only', %s, %s) RETURNING id",
        (idea["id"], ravi["code"], kavya["code"], fx.at(17, 9, 30)),
    ).fetchone()["id"]
    _seed_line(db, idea, "shared", fx.at(14, 10, 5), {})
    _seed_line(db, idea, "checked_matched", fx.at(14, 10, 8), {"hidden": 0, "similar": 0})
    _seed_line(db, idea, "opened_by_desk", fx.at(16, 9, 50), {"reviewer_id": meera["id"]})
    _seed_line(db, idea, "decided", fx.at(16, 15), {"decision_id": str(decision)})
    _seed_line(db, idea, "team_chosen", fx.at(17, 9), {"team": "Plain words team"})
    _seed_line(db, idea, "crew_joined", fx.at(17, 9, 30), {"request_id": str(request)})
    _seed_line(db, idea, "shipped", fx.at(17, 10), {})

    assert texts(conversation(db, idea["idea_id"], kavya["id"], at=NOW)) == [
        "You shared it. Saturday 14 November, 10:05 am",
        "Checked and matched. Nothing to hide, no similar ideas found. 10:08 am",
        "The review desk opened it. Monday 16 November, 9:50 am",  # DEC-111
        "The review desk picked it. 3:00 pm",
        "Arjun Rao’s team started building it. Today, 9:00 am",
        "Ravi Nair joined the crew. 9:30 am",
    ]
    assert "Your team started building it. Today, 9:00 am" in texts(
        conversation(db, idea["idea_id"], arjun["id"], at=NOW)
    )

    # A reversal by the committee, and a desk merge, as the seed writes them (T9; R2 and T11).
    turned = fx.idea(db, kavya)
    no = db.execute(
        "INSERT INTO idea_decisions (idea_uuid, choice, reason_encrypted, by_user_id, at) "
        "VALUES (%s, 'not_picked', '\\x00', %s, %s) RETURNING id",
        (turned["id"], meera["id"], fx.at(15, 11)),
    ).fetchone()["id"]
    window = db.execute(
        "INSERT INTO decision_windows (decision_id, state, opens_at, closes_at, max_closes_at) "
        "VALUES (%s, 'reversed', %s, %s, %s) RETURNING id",
        (no, fx.at(15, 11), fx.at(15, 11) + dt.timedelta(days=30), fx.at(15, 11) + dt.timedelta(days=91)),
    ).fetchone()["id"]
    reversal = db.execute(
        "INSERT INTO decision_reversals (window_id, to_choice, note_encrypted, by_user_id, at) "
        "VALUES (%s, 'pick', '\\x00', %s, %s) RETURNING id",
        (window, rohan["id"], fx.at(17, 9)),
    ).fetchone()["id"]
    _seed_line(db, turned, "decision_reversed", fx.at(17, 9), {"reversal_id": str(reversal)})
    lead = fx.idea(db, ravi)
    merge = db.execute(
        "INSERT INTO merges (lead_idea_uuid, merged_idea_uuid, via, by_user_id) VALUES (%s, %s, 'review_desk', %s) "
        "RETURNING id",
        (lead["id"], turned["id"], meera["id"]),
    ).fetchone()["id"]
    _seed_line(db, lead, "desk_merged", fx.at(17, 9, 15), {"merge_id": str(merge)})
    assert texts(conversation(db, turned["idea_id"], kavya["id"], at=NOW))[-1] == (
        "The Ones Committee reversed the decision. It’s now Picked. Today, 9:00 am"  # DEC-113
    )
    assert texts(conversation(db, lead["idea_id"], ravi["id"], at=NOW))[-1] == (
        f"The review desk joined it with {turned['idea_id']}. Today, 9:15 am"
    )
    assert texts(conversation(db, lead["idea_id"], meera["id"], at=NOW))[-1] == (
        f"You joined it with {turned['idea_id']}. Today, 9:15 am"
    )
    assert "convo.render.unknown_code" not in captured_logs.getvalue()[logged_before:]


def test_l_convo_4_s_08_answers_sent_tell_the_sharer_when_the_desk_decides(
    db: Any, cast: dict[str, Any]
) -> None:
    kavya, meera = cast["kavya"], cast["meera"]
    idea = fx.idea(db, kavya, decide_by=fx.at(20, 18))
    set_id = fx.question_set(db, idea, meera, ("summary", "often"), fx.at(16, 11, 20))
    fx.answer_all(db, set_id, kavya, fx.at(16, 16, 32))
    post(db, str(idea["id"]), "sharer.answered", author_code=kavya["code"], payload={"set_id": set_id, "count": 2},
         question_set_id=set_id, entry_type="answers", at=fx.at(16, 16, 32))  # fmt: skip
    [a] = [
        e for e in conversation(db, idea["idea_id"], kavya["id"], at=NOW)["entries"] if e["type"] == "answers"
    ]
    assert a["at_label"] == "Monday 16 November, 4:32 pm"
    assert (
        a["footer"]
        == "Each answer was added to its part of your idea. The review desk decides by Friday 20 November."
    )
    [seen] = [
        e for e in conversation(db, idea["idea_id"], meera["id"], at=NOW)["entries"] if e["type"] == "answers"
    ]
    assert "footer" not in seen


def test_bld_f065_s_08_a_closed_question_set_is_not_worded_answered(db: Any, cast: dict[str, Any]) -> None:
    """The desk decided before every answer came (the J-TRACK/3 path): the set is closed, not answered (review of
    f/convo-7, item 2)."""
    kavya, meera = cast["kavya"], cast["meera"]
    idea = fx.idea(db, kavya, status="needs_you")
    set_id = fx.question_set(db, idea, meera, ("summary", "often"), fx.at(16, 11, 20))
    post(db, str(idea["id"]), "desk.asked", author_user_id=meera["id"], payload={"set_id": set_id, "count": 2},
         question_set_id=set_id, entry_type="questions", at=fx.at(16, 11, 20))  # fmt: skip

    def sharers_card() -> dict[str, Any]:
        view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
        [q] = [e for e in view["entries"] if e["type"] == "questions"]
        return q

    db.execute("UPDATE question_sets SET state = 'closed' WHERE id = %s", (set_id,))
    q = sharers_card()
    assert (
        q["title"] == "The review desk’s 2 questions, now closed"
        and "deadline" not in q
        and "answer_url" not in q
    )
    db.execute("UPDATE question_sets SET state = 'answered' WHERE id = %s", (set_id,))
    assert sharers_card()["title"] == "The review desk’s 2 questions, answered"
