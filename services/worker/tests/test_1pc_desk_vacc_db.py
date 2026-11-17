"""V-ACC rows proved against the database, with lane A's `notify` replaced by a recorder (`FakeNotify`): who is told
what and whether it needs them (L-INBOX.kinds), and the reviewer's page through asking and answering
(V-ACC.review/7, /8, /13; V-ACC.track/5; V-ACC.committee/4; J-REVIEW, J-TRACK, J-COMMITTEE)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import asking, clocks, committee, decide, merging, reads
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

SENT = f.at(16, 11, 20)  # Monday 16 November, 11:20 am
DUE = f.at(19, 18)  # 3 days: Thursday 19 November, 6 pm
QS: list[dict[str, Any]] = [
    {"part": "summary", "text": "Is it mostly R07, or all rejection codes?"},
    {"part": "often", "text": "Is the 40 calls a day at one branch, or across Hyderabad?"},
    {"part": "evidence", "text": "Can you add a screenshot of the SMS, with the folio hidden?"},
]
ANSWERS = (
    "All of them. R07 is about half the calls. R03 and R12 make up most of the rest.",
    "That’s our Hyderabad branch alone. Vizag and Vijayawada say they get about the same.",
    "Two screenshots attached, folio hidden.",
)
REASON = "Picked. A clear problem, a real number and a simple fix for the branch."
NOTE = "The SMS templates are frozen until the platform upgrade in January, so a team picked now would wait."


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
    kavya, ravi = f.person(db, "Kavya Menon"), f.person(db, "Ravi Nair")
    return {
        "kavya": kavya, "ravi": ravi,
        "meera": f.person(db, "Meera Iyer", roles=("reviewer",)),
        "rohan": f.person(db, "Rohan Mehta", roles=("committee",)),
        "idea": f.idea(db, kavya, shared_at=f.at(14, 10)),
    }  # fmt: skip


@pytest.fixture
def told(monkeypatch: pytest.MonkeyPatch) -> f.FakeNotify:
    """Lane A's `notify`, recording each post for this test (removed when it ends)."""
    return f.install_fake_notify(monkeypatch)


def _send(db: Conn, cast: dict[str, Any]) -> dict[str, Any]:
    return asking.send_set(
        db, cast["idea"]["idea_id"], cast["meera"]["id"], {"questions": QS, "time_to_answer": "3d"}, SENT
    )


def test_V_ACC_review_7_the_sharer_is_told_and_the_idea_waits_on_them(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify
) -> None:
    sent = _send(db, cast)
    [item] = told.of("questions")
    assert (item.recipients, item.needs_you, item.due_at, item.sender) == (
        [cast["kavya"]["id"]], True, DUE, cast["meera"]["id"]
    )  # fmt: skip
    assert item.dedupe_key == f"qs:{sent['id']}"
    asking.open_set_for_sharer(db, cast["idea"]["idea_id"], cast["kavya"]["id"], f.at(16, 12, 5))
    desk = reads.desk(db, cast["meera"]["id"], tab="waiting", at=f.at(16, 13))
    row = next(r for r in desk["items"] if r["idea_id"] == cast["idea"]["idea_id"])
    assert (row["questions"], row["time_left"], row["asked"], row["answered"]) == (
        "0 of 3 answered, seen 12:05 pm", "3 days to answer", 3, 0
    )  # fmt: skip


def test_V_ACC_review_8_the_reviewer_reads_each_answer_under_its_part(db: Conn, cast: dict[str, Any]) -> None:
    sent = _send(db, cast)
    ref, meera = cast["idea"]["idea_id"], cast["meera"]["id"]
    asking.open_set_for_sharer(db, ref, cast["kavya"]["id"], f.at(16, 12, 5))
    # sent, waiting on Kavya (DeskIdea board, "Sent, waiting")
    page = reads.reviewer_idea(db, ref, meera, f.at(16, 13))
    panel = page["panel"]
    assert (panel["state"], panel["title"], panel["countdown"]) == (
        "sent",
        "Waiting on Kavya",
        "3 days to answer",
    )
    assert panel["sent_line"] == "Sent today, 11:20 am. Seen 12:05 pm."
    asked = [
        (p["part"], q["asked_line"], q["state"], q["answer"]) for p in page["parts"] for q in p["questions"]
    ]
    assert asked == [
        ("summary", "You asked, today 11:20 am", "Not answered yet", None),
        ("often", "You asked, today 11:20 am", "Not answered yet", None),
        ("evidence", "You asked, today 11:20 am", "Not answered yet", None),
    ]
    # Kavya answers all three at 4:32 pm (DeskIdea board, "Answered")
    for q, text in zip(sent["questions"], ANSWERS, strict=True):
        asking.save_answer(db, q["id"], cast["kavya"]["id"], text, at=f.at(16, 16, 30))
    asking.send_answers(db, sent["id"], cast["kavya"]["id"], f.at(16, 16, 32))
    page = reads.reviewer_idea(db, ref, meera, f.at(16, 17))
    panel = page["panel"]
    assert (panel["state"], panel["title"], panel["spare_line"]) == (
        "answered", "All 3 answered", "Answered with 3 days to spare"
    )  # fmt: skip
    assert panel["decide_by_line"] == "Decide by Friday 20 November."
    answered = [
        (p["part"], q["asked_line"], q["state"], q["answer"]["line"], q["answer"]["text"])
        for p in page["parts"]
        for q in p["questions"]
    ]
    assert answered == [
        (part, "You asked, today 11:20 am", "Answered", "Kavya answered, today 4:32 pm", text)
        for part, text in zip(("summary", "often", "evidence"), ANSWERS, strict=True)
    ]


def test_V_ACC_track_5_reminders_a_day_and_two_hours_before_the_deadline(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify
) -> None:
    sent = _send(db, cast)
    for t, expect in (
        (f.at(18, 17, 55), 0), (f.at(18, 18, 5), 1), (f.at(18, 18, 10), 0),  # 24 hours before, once
        (f.at(19, 15, 55), 0), (f.at(19, 16, 5), 1), (f.at(19, 16, 10), 0),  # 2 hours before, once
    ):  # fmt: skip
        assert clocks.run_due(db, t)["reminded"] == expect, t
    reminders = told.of("answer_reminder")
    assert [(r.recipients, r.needs_you, r.due_at, r.sender) for r in reminders] == [
        ([cast["kavya"]["id"]], True, DUE, "system")
    ] * 2
    assert all((r.dedupe_key or "").startswith(f"qs:{sent['id']}:") for r in reminders)
    # answering every question takes the item and its reminders out of Needs you (L-INBOX.rules/3)
    for q, text in zip(sent["questions"], ANSWERS, strict=True):
        asking.save_answer(db, q["id"], cast["kavya"]["id"], text, at=f.at(19, 16, 20))
    asking.send_answers(db, sent["id"], cast["kavya"]["id"], f.at(19, 16, 30))
    assert told.resolved == [f"qs:{sent['id']}"]
    assert clocks.run_due(db, f.at(19, 17))["reminded"] == 0


def test_V_ACC_review_13_both_sharers_are_told_of_a_desk_merge(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify
) -> None:
    theirs = f.idea(db, cast["ravi"], title="Rejection SMS codes confuse investors", shared_at=f.at(2, 15))
    m = merging.desk_merge(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                           {"other_idea_id": theirs["idea_id"], "note": "You both found the same R07 calls."},
                           f.at(16, 12))  # fmt: skip
    assert m["lead_idea_id"] == theirs["idea_id"]  # the earlier idea leads by default
    [item] = told.of("desk_merge")
    assert sorted(item.recipients) == sorted([cast["kavya"]["id"], cast["ravi"]["id"]])
    assert (item.needs_you, item.sender) == (False, cast["meera"]["id"])


def test_V_ACC_committee_4_the_sharer_the_crew_and_the_reviewer_are_told_of_a_reversal(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify
) -> None:
    farhan = f.person(db, "Farhan Shaikh")
    f.crew(db, cast["idea"], farhan)
    d = decide.send(db, cast["idea"]["idea_id"], cast["meera"]["id"], {"choice": "pick", "reason": REASON},
                    f.at(16, 16, 58))  # fmt: skip
    [decided] = told.of("decision")
    assert (decided.recipients, decided.needs_you) == ([cast["kavya"]["id"], farhan["id"]], False)
    window = db.execute("SELECT id FROM decision_windows WHERE decision_id = %s", (d["id"],)).fetchone()
    assert window is not None
    committee.reverse_window(db, str(window["id"]), cast["rohan"]["id"],
                             {"to": "not_now", "note": NOTE, "return_in": "3m"}, f.at(24, 17, 40))  # fmt: skip
    [item] = told.of("decision_reversed")
    assert item.recipients == [cast["kavya"]["id"], farhan["id"], cast["meera"]["id"]]
    assert (item.needs_you, item.sender) == (False, cast["rohan"]["id"])
    # and the sharer's page shows the committee's card (the lines are pinned in test_1pc_desk_viewer_lines_db)
    got = committee.decision_for_viewer(db, cast["idea"]["idea_id"], cast["kavya"]["id"], f.at(24, 18))
    assert got is not None and got["lines"]["reversal"]["final_line"].startswith("This is final.")
    assert dt.datetime.fromisoformat(got["reversal"]["at"]) == f.at(24, 17, 40)
