"""L-QUESTIONS against the database: the desk asks, the sharer answers (A-API.questions, S-R3, C-QCARD).

Needs Postgres with the handoff cut-over applied (`make up`, then the tests migrate their own database).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import asking, decide
from desk.questions import AFTER_DECIDE_BY, desk_line
from desk.store import Refused, unseal
from tests import desk_fixtures as f

SENT = f.at(16, 11, 20)  # Monday 16 November 2026, 11:20 am IST
QS: list[dict[str, Any]] = [
    {"part": "summary", "text": "Is it mostly R07, or all rejection codes?"},
    {"part": "often", "text": "Is the 40 calls a day at one branch, or across Hyderabad?"},
    {
        "part": "evidence",
        "text": "Can you add a screenshot of the SMS, with the folio hidden?",
        "suggested": True,
    },
]
REASON = "A clear problem, a real number and a simple fix that the branch can try."


@pytest.fixture
def repo(company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    get_settings.cache_clear()
    yield company_repo
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def cast(db: Conn, repo: Path) -> dict[str, Any]:
    kavya = f.person(db, "Kavya Menon")
    meera = f.person(db, "Meera Iyer", roles=("reviewer",))
    return {"kavya": kavya, "meera": meera, "idea": f.idea(db, kavya)}


def _send(db: Conn, cast: dict[str, Any], t: dt.datetime = SENT, **body: Any) -> dict[str, Any]:
    return asking.send_set(
        db, cast["idea"]["idea_id"], cast["meera"]["id"], {"questions": QS, "time_to_answer": "3d", **body}, t
    )


def _idea_row(db: Conn, cast: dict[str, Any]) -> dict[str, Any]:
    row = db.execute("SELECT * FROM ideas WHERE id = %s", (cast["idea"]["id"],)).fetchone()
    assert row is not None
    return row


def _qids(sent: dict[str, Any]) -> list[str]:
    return [q["id"] for q in sent["questions"]]


def _when(value: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(value) if value else None


def test_L_QUESTIONS_ask_5_sending_three_with_3_days_moves_the_idea_to_needs_you(
    db: Conn, cast: dict[str, Any]
) -> None:
    got = _send(db, cast)
    assert _when(got["due_at"]) == f.at(19, 18)  # Thursday 19 November, 6 pm
    assert got["due_label"] == "Kavya has until Thursday 19 November, 6 pm."
    assert got["countdown"] == {"label": "3 days to answer", "variant": "normal"}
    assert (got["after_decide_by"], got["after_decide_by_line"]) == (False, None)
    assert (got["state"], got["count"], got["answered"], got["time_to_answer"]) == ("sent", 3, 0, "3d")
    assert [(q["part"], q["text"], q["suggested"]) for q in got["questions"]] == [
        (q["part"], q["text"], bool(q.get("suggested"))) for q in QS
    ]
    assert got["by"]["first_name"] == "Meera"
    idea = _idea_row(db, cast)
    assert idea["status"] == "needs_you"
    assert idea["opened_at"] == SENT and str(idea["reviewer_id"]) == cast["meera"]["id"]  # asking is opening
    stored = db.execute("SELECT * FROM questions WHERE set_id = %s ORDER BY seq", (got["id"],)).fetchall()
    assert [unseal(r["text_encrypted"], "questions", "text_encrypted", str(r["id"])) for r in stored] == [
        q["text"] for q in QS
    ]
    entry = db.execute(
        "SELECT type, question_set_id FROM conversation_entries WHERE idea_uuid = %s AND type = 'questions'",
        (idea["id"],),
    ).fetchone()
    assert entry is not None and str(entry["question_set_id"]) == got["id"]
    assert set(f.events(db, idea["id"])) == {"desk.opened", "desk.asked"}
    assert "desk.ask" in f.audit_actions(db, f"idea:{idea['idea_id']}")
    logged = db.execute(
        "SELECT after FROM audit_log WHERE action = 'desk.ask' AND entity = %s", (f"idea:{idea['idea_id']}",)
    ).fetchone()
    assert logged is not None and "R07" not in str(logged["after"])  # IDs and enums only


def test_L_QUESTIONS_ask_4_a_deadline_after_the_decide_by_date_is_said_or_moved(
    db: Conn, cast: dict[str, Any]
) -> None:
    week = _send(db, cast, time_to_answer="1w")  # Monday 23 November, after Friday 20 November
    assert week["after_decide_by"] is True and week["after_decide_by_line"] == AFTER_DECIDE_BY
    assert _idea_row(db, cast)["decide_by"] == f.at(20, 18)
    other = {**cast, "idea": f.idea(db, cast["kavya"], title="Track couriered redemption forms")}
    moved = _send(db, other, time_to_answer="1w", move_decide_by=True)
    assert moved["after_decide_by"] is False
    assert _when(moved["decide_by"]) == f.at(24, 18)  # the working day after the deadline
    assert _idea_row(db, other)["decide_by"] == f.at(24, 18)
    assert "desk.move_decide_by" in f.audit_actions(db, f"idea:{other['idea']['idea_id']}")


def test_L_QUESTIONS_ask_6_one_open_set_at_a_time(db: Conn, cast: dict[str, Any]) -> None:
    _send(db, cast)
    with pytest.raises(Refused) as refused:
        _send(db, cast, t=f.at(16, 15))
    assert (refused.value.status, refused.value.code) == (409, "set_open")
    assert refused.value.message == "Kavya still has questions open. Ask a follow-up once they are answered."
    n = db.execute("SELECT count(*) AS n FROM question_sets WHERE idea_uuid = %s", (cast["idea"]["id"],))
    assert n.fetchone() == {"n": 1}


def test_L_QUESTIONS_ask_a_reviewer_never_asks_about_their_own_idea(db: Conn, cast: dict[str, Any]) -> None:
    mine = f.idea(db, cast["meera"])
    for call in (
        lambda: asking.send_set(db, mine["idea_id"], cast["meera"]["id"], {"questions": QS}),
        lambda: asking.suggested(db, mine["idea_id"], cast["meera"]["id"]),
    ):
        with pytest.raises(Refused) as refused:
            call()
        assert (refused.value.status, refused.value.code) == (403, "own_idea")
    assert f.audit_actions(db, f"idea:{mine['idea_id']}") == ["desk.own_idea_refused"] * 2
    row = db.execute("SELECT status FROM ideas WHERE id = %s", (mine["id"],)).fetchone()
    assert row == {"status": "with_review_desk"}


def test_V_FIELDS_review_1_an_empty_or_overlong_question_is_refused(db: Conn, cast: dict[str, Any]) -> None:
    for questions, code, field, message in (
        ([], "no_questions", "questions", "Add a question first."),
        ([{"part": "summary", "text": "   "}], "question_empty", "questions.0.text", "Write the question first."),
        ([QS[0], {"part": "often", "text": "x" * 301}], "question_too_long", "questions.1.text",
         "Keep it under 300 characters."),
        ([{"text": "Which branches see it most?"}], "part_required", "questions.0.part",
         "Choose the part it is about."),
    ):  # fmt: skip
        with pytest.raises(Refused) as refused:
            asking.send_set(db, cast["idea"]["idea_id"], cast["meera"]["id"], {"questions": questions}, SENT)
        got = refused.value
        assert (got.status, got.code, got.field, got.message) == (422, code, field, message)
    assert db.execute("SELECT count(*) AS n FROM question_sets").fetchone() == {"n": 0}
    assert _idea_row(db, cast)["status"] == "with_review_desk"


def test_L_QUESTIONS_ask_3_suggestions_follow_the_gaps_and_skip_what_was_asked(
    db: Conn, cast: dict[str, Any]
) -> None:
    ref, meera = cast["idea"]["idea_id"], cast["meera"]["id"]
    # The idea has a summary and how often; nobody affected, no worth, no files, no fix.
    assert [s["part"] for s in asking.suggested(db, ref, meera)] == [
        "who", "cost", "evidence", "summary", "often", "fix"
    ]  # fmt: skip
    db.execute(
        "INSERT INTO idea_worth (idea_uuid, by_side, by_code, hours_low) VALUES (%s, 'sharer', %s, 10)",
        (cast["idea"]["id"], cast["kavya"]["code"]),
    )
    found = asking.suggested(db, ref, meera)
    assert [s["part"] for s in found] == ["who", "evidence", "summary", "often", "cost", "fix"]
    who = found[0]
    asking.send_set(db, ref, meera, {"questions": [{**who, "suggested": True}]}, SENT)
    assert who["text"] not in [s["text"] for s in asking.suggested(db, ref, meera)]


def test_L_QUESTIONS_clock_1_the_sharer_opening_the_set_marks_it_seen_once(
    db: Conn, cast: dict[str, Any]
) -> None:
    sent = _send(db, cast)
    ref, kavya = cast["idea"]["idea_id"], cast["kavya"]["id"]
    got = asking.open_set_for_sharer(db, ref, kavya, f.at(16, 12, 5))
    assert got is not None and got["id"] == sent["id"] and got["state"] == "seen"
    assert _when(got["seen_at"]) == f.at(16, 12, 5)
    assert got["countdown"] == {"label": "3 days left to answer", "variant": "normal"}
    assert got["deadline"] == "Answer by Thursday 19 November, 6 pm"
    assert (got["progress"], got["send_label"]) == ("0 of 3 answered", "Answer at least one question")
    assert [q["part_name"] for q in got["questions"]] == ["The problem", "How often", "Attached"]
    again = asking.open_set_for_sharer(db, ref, kavya, f.at(16, 13))
    assert again is not None and _when(again["seen_at"]) == f.at(16, 12, 5)
    late = asking.open_set_for_sharer(db, ref, kavya, f.at(19, 10, 22))
    assert late is not None and late["countdown"] == {"label": "07:38 left to answer", "variant": "warn"}
    assert late["deadline"] == "Answer by 6 pm today"
    # Anyone but the sharer: the set does not exist for them.
    arjun = f.person(db, "Arjun Rao")
    with pytest.raises(Refused) as refused:
        asking.open_set_for_sharer(db, ref, arjun["id"])
    assert refused.value.code == "not_found"


def test_L_QUESTIONS_answer_6_a_saved_answer_is_masked(db: Conn, cast: dict[str, Any]) -> None:
    sent = _send(db, cast)
    kavya = cast["kavya"]["id"]
    saved = asking.save_answer(
        db, _qids(sent)[0], kavya, "Mostly R07. Folio 1234567890 got it twice last week.", at=f.at(16, 12, 10)
    )
    assert "1234567890" not in saved["text"] and "••••90" in saved["text"]
    assert (saved["hidden"], saved["added_to"], saved["sent"]) == (1, "summary", False)
    row = db.execute("SELECT * FROM answers WHERE id = %s", (saved["id"],)).fetchone()
    assert row is not None and row["sent_at"] is None and row["by_code"] == cast["kavya"]["code"]
    assert unseal(row["text_encrypted"], "answers", "text_encrypted", saved["id"]) == saved["text"]
    # Saving again keeps the one answer; the sharer sees the draft, the desk does not yet.
    again = asking.save_answer(db, _qids(sent)[0], kavya, "Mostly R07, about half the calls.")
    assert again["id"] == saved["id"]
    mine = asking.open_set_for_sharer(db, cast["idea"]["idea_id"], kavya, f.at(16, 12, 15))
    assert mine is not None and mine["questions"][0]["answer"]["text"] == "Mostly R07, about half the calls."
    assert (mine["progress"], mine["send_label"]) == ("1 of 3 answered", "Send 1 answer to Meera")
    assert asking.answers_by_part(db, cast["idea"]["id"])["summary"][0]["answer"] is None
    with pytest.raises(Refused) as refused:
        asking.save_answer(db, _qids(sent)[1], kavya, "x" * 2001)
    assert (refused.value.code, refused.value.field) == ("answer_too_long", "text")


def test_V_FIELDS_answer_2_sending_with_nothing_answered_is_refused(db: Conn, cast: dict[str, Any]) -> None:
    sent = _send(db, cast)
    kavya = cast["kavya"]["id"]
    asking.save_answer(db, _qids(sent)[1], kavya, "   ")  # a blank draft is not an answer
    with pytest.raises(Refused) as refused:
        asking.send_answers(db, sent["id"], kavya, f.at(16, 16))
    got = refused.value
    assert (got.status, got.code, got.message) == (422, "nothing_answered", "Answer at least one question")
    assert db.execute("SELECT count(*) AS n FROM answers WHERE sent_at IS NOT NULL").fetchone() == {"n": 0}


def test_L_QUESTIONS_answer_3_one_of_three_then_the_rest(db: Conn, cast: dict[str, Any]) -> None:
    sent = _send(db, cast)
    kavya, uuid_ = cast["kavya"]["id"], cast["idea"]["id"]
    q1, q2, q3 = _qids(sent)
    asking.save_answer(db, q1, kavya, "All of them. R07 is about half the calls.", at=f.at(16, 16, 20))
    first = asking.send_answers(db, sent["id"], kavya, f.at(16, 16, 32))
    assert (first["state"], first["sent"], first["answered"], first["count"]) == ("partly_answered", 1, 1, 3)
    assert (first["sent_line"], first["spare"]) == ("Sent to Meera, 4:32 pm", "Answered with 3 days to spare")
    assert first["decides_by"] == "Meera decides by Friday 20 November"
    assert _idea_row(db, cast)["status"] == "needs_you"
    facts = asking.facts(db, uuid_)
    assert facts is not None and (facts.count, facts.answered, facts.answered_at) == (3, 1, f.at(16, 16, 32))
    entries = db.execute(
        "SELECT question_set_id FROM conversation_entries WHERE idea_uuid = %s AND type = 'answers'", (uuid_,)
    ).fetchall()
    assert [str(e["question_set_id"]) for e in entries] == [sent["id"]]
    assert f.audit_actions(db, f"idea:{cast['idea']['idea_id']}")[-1] == "desk.answers_sent"
    with pytest.raises(Refused) as refused:  # a sent answer is with the desk now
        asking.save_answer(db, q1, kavya, "Changed my mind.")
    assert refused.value.code == "answer_sent"

    asking.save_answer(db, q2, kavya, "That is our Hyderabad branch alone.")
    asking.save_answer(db, q3, kavya, "Two screenshots attached, folio hidden.")
    rest = asking.send_answers(db, sent["id"], kavya, f.at(17, 10))
    assert (rest["state"], rest["sent"], rest["answered"], rest["progress"]) == (
        "answered",
        2,
        3,
        "3 of 3 answered",
    )
    assert _idea_row(db, cast)["status"] == "with_review_desk"
    facts = asking.facts(db, uuid_)
    assert facts is not None and (facts.answered, facts.answered_at) == (3, f.at(17, 10))
    by_part = asking.answers_by_part(db, uuid_)
    assert list(by_part) == ["summary", "often", "evidence"]
    often = by_part["often"][0]
    assert (often["answer"], often["by"], often["asked_by"]) == (
        "That is our Hyderabad branch alone.",
        "Kavya",
        "Meera",
    )
    assert _when(often["answered_at"]) == f.at(17, 10) and _when(often["asked_at"]) == SENT


def test_L_QUESTIONS_states_a_closed_set_refuses_saves(db: Conn, cast: dict[str, Any]) -> None:
    sent = _send(db, cast)
    kavya = cast["kavya"]["id"]
    asking.save_answer(db, _qids(sent)[0], kavya, "Mostly R07.")
    decide.send(db, cast["idea"]["idea_id"], cast["meera"]["id"], {"choice": "pick", "reason": REASON})
    calls: tuple[Callable[[], object], ...] = (
        lambda: asking.save_answer(db, _qids(sent)[1], kavya, "One branch."),
        lambda: asking.send_answers(db, sent["id"], kavya),
    )
    for call in calls:
        with pytest.raises(Refused) as refused:
            call()
        assert (refused.value.status, refused.value.code) == (409, "set_closed")
    assert asking.open_set_for_sharer(db, cast["idea"]["idea_id"], kavya) is None
    facts = asking.facts(db, cast["idea"]["id"])
    assert facts is not None and facts.closed


def test_L_QUESTIONS_clock_3_give_more_time_adds_two_days(db: Conn, cast: dict[str, Any]) -> None:
    sent = _send(db, cast)
    got = asking.give_more_time(db, sent["id"], cast["meera"]["id"], f.at(17, 10))
    assert _when(got["due_at"]) == f.at(21, 18) and got["extended_times"] == 1
    assert got["due_label"] == "Kavya has until Saturday 21 November, 6 pm."
    assert got["countdown"]["label"] == "4 days to answer"
    row = db.execute(
        "SELECT due_at, extended_times FROM question_sets WHERE id = %s", (sent["id"],)
    ).fetchone()
    assert row == {"due_at": f.at(21, 18), "extended_times": 1}
    assert f.audit_actions(db, f"idea:{cast['idea']['idea_id']}")[-1] == "desk.give_more_time"
    with pytest.raises(Refused) as refused:  # not the sharer's to extend, and never on one's own idea
        asking.give_more_time(db, sent["id"], cast["kavya"]["id"])
    assert refused.value.code == "own_idea"


def test_L_QUESTIONS_clock_3_remind_records_reminded_at(db: Conn, cast: dict[str, Any]) -> None:
    sent = _send(db, cast)
    got = asking.remind(db, sent["id"], cast["meera"]["id"], f.at(18, 9, 30))
    assert _when(got["reminded_at"]) == f.at(18, 9, 30)
    row = db.execute("SELECT reminded_at FROM question_sets WHERE id = %s", (sent["id"],)).fetchone()
    assert row == {"reminded_at": f.at(18, 9, 30)}
    assert f.audit_actions(db, f"idea:{cast['idea']['idea_id']}")[-1] == "desk.remind"


def test_L_QUESTIONS_clock_2_the_timed_reminder_respects_the_sharer_and_the_set(
    db: Conn, cast: dict[str, Any]
) -> None:
    sent = _send(db, cast)
    sid, day_before = sent["id"], f.at(18, 18)
    db.execute("INSERT INTO comms_prefs (user_id, reminders) VALUES (%s, false)", (cast["kavya"]["id"],))
    assert asking.remind_due(db, sid, day_before) is False  # reminders off (S-H6)
    db.execute("UPDATE comms_prefs SET reminders = true WHERE user_id = %s", (cast["kavya"]["id"],))
    assert asking.remind_due(db, sid, f.at(17, 9)) is False  # too early: a timer from an older deadline
    assert asking.remind_due(db, sid, day_before) is True
    row = db.execute("SELECT reminded_at FROM question_sets WHERE id = %s", (sid,)).fetchone()
    assert row == {"reminded_at": day_before}
    assert f.audit_actions(db, f"idea:{cast['idea']['idea_id']}")[-1] == "desk.answer_reminder"
    assert asking.remind_due(db, sid, f.at(19, 19)) is False  # past the deadline
    for q in _qids(sent):
        asking.save_answer(db, q, cast["kavya"]["id"], "Answered.")
    asking.send_answers(db, sid, cast["kavya"]["id"], f.at(19, 12))
    assert asking.remind_due(db, sid, f.at(19, 16)) is False  # answered


def test_L_QUESTIONS_clock_1_desk_line_reads_the_stored_facts(db: Conn, cast: dict[str, Any]) -> None:
    uuid_, kavya = cast["idea"]["id"], cast["kavya"]["id"]
    assert desk_line(asking.facts(db, uuid_), SENT) == "No questions asked"
    sent = _send(db, cast)
    assert desk_line(asking.facts(db, uuid_), f.at(16, 11, 30)) == "Not seen yet"
    asking.open_set_for_sharer(db, cast["idea"]["idea_id"], kavya, f.at(16, 12, 5))
    assert desk_line(asking.facts(db, uuid_), f.at(16, 13)) == "0 of 3 answered, seen 12:05 pm"
    q1, q2, q3 = _qids(sent)
    asking.save_answer(db, q1, kavya, "All of them.")
    asking.send_answers(db, sent["id"], kavya, f.at(16, 14))
    assert desk_line(asking.facts(db, uuid_), f.at(16, 15)) == "1 of 3 answered"
    asking.save_answer(db, q2, kavya, "One branch.")
    asking.save_answer(db, q3, kavya, "Screenshot added.")
    asking.send_answers(db, sent["id"], kavya, f.at(16, 16, 32))
    assert desk_line(asking.facts(db, uuid_), f.at(16, 17, 32)) == "All 3 answered, 1 hour ago"


def _file(db: Conn, idea: dict[str, Any], sharer: dict[str, str], n: int, state: str) -> str:
    fid = f"ATT-2026-{n:06d}"
    db.execute(
        "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, name, mime, bytes, store_key, kind, file_state) "
        "VALUES (%s, %s, %s, 'sms-screenshot.png', 'image/png', 2048, %s, 'file', %s)",
        (fid, idea["id"], sharer["code"], f"clean/{fid}", state),
    )
    return fid


def test_S_R3_rules_3_DEC_107_files_on_an_answer_are_the_ideas_own_and_a_customer_detail_is_marked(
    db: Conn, cast: dict[str, Any]
) -> None:
    """DEC-107: a file in which the scan found a customer detail can be attached and sent. It is marked, and the desk
    sees it; a file still checking is the sharer's alone until it passes."""
    sent = _send(db, cast)
    kavya, q3 = cast["kavya"]["id"], _qids(sent)[2]
    clean = _file(db, cast["idea"], cast["kavya"], 901, "hidden_checked")
    found = _file(db, cast["idea"], cast["kavya"], 902, "personal_data_found")
    checking = _file(db, cast["idea"], cast["kavya"], 904, "checking")
    other = _file(
        db, f.idea(db, cast["kavya"], title="Track couriered redemption forms"), cast["kavya"], 903, "ok"
    )
    with pytest.raises(Refused) as refused:
        asking.save_answer(db, q3, kavya, "Two screenshots.", [clean, other])
    assert (refused.value.code, refused.value.field) == ("file_not_found", "file_ids")
    saved = asking.save_answer(db, q3, kavya, "", [clean])  # a file alone answers "add a screenshot"
    assert [x["id"] for x in saved["files"]] == [clean]
    saved = asking.save_answer(db, q3, kavya, "Three screenshots of the SMS.", [found, checking])
    assert [(x["id"], x["customer_detail"]) for x in saved["files"]] == [
        (clean, False), (found, True), (checking, False)
    ]  # fmt: skip
    assert asking.send_answers(db, sent["id"], kavya)["sent"] == 1
    shown = asking.answers_by_part(db, cast["idea"]["id"])["evidence"][0]["files"]
    assert [(x["id"], x["customer_detail"]) for x in shown] == [(clean, False), (found, True)]
