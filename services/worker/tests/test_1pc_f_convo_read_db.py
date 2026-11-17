"""L-CONVO reading: who may read (L-CONVO/2), the timeline (/3, /4), the box and its lines (/5), the side panel (/8).
J-TEAMUP steps 5–6: the conversation opens to the new crew member, earlier entries included. Synthetic people only.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from convo import post
from convo.reads import conversation
from convo.store import Refused
from tests import convo_fixtures as fx

NOW = fx.at(17, 10, 30)  # Tuesday 17 November 2026, IST


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


def test_l_convo_1_one_conversation_found_by_reference_or_uuid_and_none_for_a_draft(db: Any, cast: dict) -> None:
    idea = fx.idea(db, cast["kavya"])
    by_ref = conversation(db, idea["idea_id"], cast["kavya"]["id"], at=NOW)
    by_uuid = conversation(db, str(idea["id"]), cast["kavya"]["id"], at=NOW)
    assert by_ref["entries"] == by_uuid["entries"] and by_ref["idea"]["id"] == idea["idea_id"]
    draft = fx.idea(db, cast["kavya"], status="draft")
    assert refused(conversation, db, draft["idea_id"], cast["kavya"]["id"]).status == 404


def test_l_convo_2_sharer_desk_and_committee_read_from_the_start_anyone_else_gets_404(db: Any, cast: dict) -> None:
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


def test_j_teamup_5_6_l_convo_2_a_crew_member_who_joins_later_reads_earlier_entries(db: Any, cast: dict) -> None:
    ravi, kavya, meera = cast["ravi"], cast["kavya"], cast["meera"]
    idea = fx.idea(db, ravi, title="Rejection SMS codes confuse investors", shared_at=fx.at(9, 11))
    post(db, str(idea["id"]), "desk.opened", author_user_id=meera["id"], at=fx.at(16, 9, 50))
    from convo.messages import send

    send(db, idea["idea_id"], ravi["id"], {"text": "Branch logs for R07 are attached in the idea."}, at=fx.at(16, 12))
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
    assert texts(view) == [
        "Ravi Nair shared it. Monday 9 November",
        "Meera from the review desk opened it. Monday 16 November, 9:50 am",
        "Ravi Nair approved your team-up request. Today, 10:05 am",
        "You joined the crew. 10:05 am",
    ]
    [earlier] = [e for e in view["entries"] if e["type"] == "message"]
    assert earlier["text"] == "Branch logs for R07 are attached in the idea." and earlier["from_label"] == "Ravi Nair"
    assert view["audience"] == "crew_and_desk"
    assert view["composer"]["placeholder"] == "Message the crew"
    assert view["composer"]["visibility"] == "The crew and the review desk see this conversation."
    assert view["header"] == {"whose": "The idea", "line": "Ravi Nair’s idea, Investor service, Hyderabad"}
    assert [(p["label"], p["doing"]) for p in view["participants"]] == [
        ("Meera from the review desk", "Reviewing it"),
        ("Ravi Nair", "Shared the idea"),
        ("You", "Joined today"),
    ]
    lead = conversation(db, idea["idea_id"], ravi["id"], at=NOW)
    assert "You approved Kavya Menon’s team-up request. Today, 10:05 am" in texts(lead)
    assert "Kavya Menon joined the crew. 10:05 am" in texts(lead)

    fx.leave_crew(db, idea, kavya)
    assert refused(conversation, db, idea["idea_id"], kavya["id"]).status == 404


def test_l_convo_2_the_build_team_reads_once_chosen(db: Any, cast: dict) -> None:
    arjun = fx.person(db, "Arjun Rao")
    idea = fx.idea(db, cast["kavya"], title="Plain words for transaction rejections", status="being_built")
    assert refused(conversation, db, idea["idea_id"], arjun["id"]).status == 404
    fx.build_team(db, idea, arjun)
    view = conversation(db, idea["idea_id"], arjun["id"], at=NOW)
    assert view["audience"] == "build_team"
    mine = conversation(db, idea["idea_id"], cast["kavya"]["id"], at=NOW)
    assert mine["composer"]["placeholder"] == "Message the build team"
    assert mine["composer"]["visibility"] == "You, the build team and the review desk see this conversation."
    assert mine["header"]["line"] == "Your idea, being built by Arjun’s team"
    assert ("Arjun Rao", "Leads the build team") in [(p["label"], p["doing"]) for p in mine["participants"]]


def test_l_convo_3_event_lines_render_at_read_time_with_names_and_you(db: Any, cast: dict) -> None:
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
    post(db, uuid_, "committee.reversed", author_user_id=rohan["id"], payload={"to": "not_now"}, at=fx.at(17, 9))
    post(db, uuid_, "desk.back_from_not_now", at=fx.at(17, 9, 30))
    view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
    assert texts(view) == [
        "You shared it. Saturday 14 November, 10:05 am",
        "Checked and matched. 1 folio number hidden, 2 similar ideas found. 10:06 am",
        "Meera from the review desk opened it. Monday 16 November, 9:50 am",
        "Meera from the review desk picked it. 3:00 pm",
        "Rohan Mehta from the Ones Committee reversed the decision. It’s now Not now. Today, 9:00 am",
        "It’s back with the review desk. 9:30 am",
    ]
    as_meera = texts(conversation(db, idea["idea_id"], meera["id"], at=NOW))
    assert "You opened it. Monday 16 November, 9:50 am" in as_meera
    assert "Kavya Menon shared it. Saturday 14 November, 10:05 am" in as_meera


def test_l_convo_3_a_desk_merge_closes_the_merged_ideas_conversation_with_a_link(db: Any, cast: dict) -> None:
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
    assert line["text"] == (
        f"Meera from the review desk joined it with {lead['idea_id']}. The conversation carries on there. "
        "Today, 9:00 am"
    )
    assert line["link"] == {"label": lead["idea_id"], "to": f"/ideas/{lead['idea_id']}/conversation"}
    assert view["composer"]["closed"] == f"This idea is now part of another one. Write in {lead['idea_id']}’s conversation."
    on_lead = conversation(db, lead["idea_id"], cast["ravi"]["id"], at=NOW)
    assert f"Meera from the review desk joined it with {merged['idea_id']}. Today, 9:00 am" in texts(on_lead)


def test_l_convo_3_f1_merge_and_crew_codes(db: Any, cast: dict) -> None:
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
    db: Any, cast: dict, captured_logs: Any
) -> None:
    idea = fx.idea(db, cast["kavya"])
    entry_id = post(db, str(idea["id"]), "lane.something_new", payload={"ref": "x1"})
    view = conversation(db, idea["idea_id"], cast["kavya"]["id"], at=NOW)
    assert all(e["id"] != entry_id for e in view["entries"])
    logged = [line for line in captured_logs.getvalue().splitlines() if "convo.render.unknown_code" in line]
    assert logged and "lane.something_new" in logged[-1] and entry_id in logged[-1]


def test_l_convo_4_questions_by_reference_with_the_line_above_the_box_then_answers(db: Any, cast: dict) -> None:
    kavya, meera = cast["kavya"], cast["meera"]
    idea = fx.idea(db, kavya, status="needs_you")
    set_id = fx.question_set(db, idea, meera, ("summary", "often", "evidence"), fx.at(16, 11, 20))
    post(db, str(idea["id"]), "desk.asked", author_user_id=meera["id"], payload={"set_id": set_id, "count": 3},
         question_set_id=set_id, entry_type="questions", at=fx.at(16, 11, 20))  # fmt: skip
    view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
    [q] = [e for e in view["entries"] if e["type"] == "questions"]
    assert (q["set_id"], q["state"], q["count"], q["answered"]) == (set_id, "sent", 3, 0)
    assert q["by_label"] == "Meera from the review desk" and q["at_label"] == "Monday 16 November, 11:20 am"
    assert view["composer"]["questions_line"] == (
        "Answer Meera’s 3 questions with Answer the questions, so each answer lands on its part of your idea. "
        "Write here for anything else."
    )
    assert "empty" not in view
    assert "questions_line" not in conversation(db, idea["idea_id"], meera["id"], at=NOW)["composer"]

    fx.answer_all(db, set_id, kavya, fx.at(16, 16, 32))
    post(db, str(idea["id"]), "sharer.answered", author_code=kavya["code"], payload={"set_id": set_id, "count": 3},
         question_set_id=set_id, entry_type="answers", at=fx.at(16, 16, 32))  # fmt: skip
    view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
    [a] = [e for e in view["entries"] if e["type"] == "answers"]
    assert a["title"] == "Your answers to Meera’s 3 questions"
    assert [(x["text"], x["added_to_label"]) for x in a["answers"]] == [
        ("Synthetic answer 1.", "The problem"),
        ("Synthetic answer 2.", "How often"),
        ("Synthetic answer 3.", "Attached"),
    ]
    assert "questions_line" not in view["composer"]
    [a2] = [e for e in conversation(db, idea["idea_id"], meera["id"], at=NOW)["entries"] if e["type"] == "answers"]
    assert a2["title"] == "Kavya’s answers to your 3 questions"


def test_l_convo_8_s_08_no_messages_yet_and_the_side_panel(db: Any, cast: dict) -> None:
    idea = fx.idea(db, cast["kavya"], opened_by=cast["meera"]["id"], reviewer_id=cast["meera"]["id"])
    view = conversation(db, idea["idea_id"], cast["kavya"]["id"], at=NOW)
    assert view["empty"]["title"] == "No messages yet"
    assert [(p["label"], p["doing"], p["you"]) for p in view["participants"]] == [
        ("Meera from the review desk", "Reviewing it", False),
        ("You", "Shared the idea", True),
    ]


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
