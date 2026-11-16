"""What the independent review of lane B's back end found, each pinned by a test (16 Nov 2026):
timers that never ran, a draft answer's files seen early, a restored merge stuck in Needs you, a member reversing a
merge of their own lead idea, a stale reversal overwriting a newer decision, credit lost along a chain of merges,
admins reading reasons, and a list in a body answering 500."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import asking, clocks, committee, decide, merging, reads, revise
from desk.store import Refused, own_codes
from tests import desk_fixtures as f

REASON = "Right problem, wrong time: the new SMS vendor arrives in February."
NOTE = "Picked after all: the branch counts make the case on their own."
MERGE_NOTE = "You both found the same R07 calls in Hyderabad."


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
        "idea": f.idea(db, kavya),
        "other": f.idea(db, ravi, title="Rejection SMS codes confuse investors", shared_at=f.at(2, 15)),
    }  # fmt: skip


def _status(db: Conn, idea: dict[str, Any]) -> str:
    row = db.execute("SELECT status FROM ideas WHERE id = %s", (idea["id"],)).fetchone()
    assert row is not None
    return str(row["status"])


def test_finding_1_not_now_comes_back_without_any_timer(db: Conn, cast: dict[str, Any]) -> None:
    decide.send(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                {"choice": "not_now", "reason": REASON, "return_in": "1m"}, f.at(16, 10))  # fmt: skip

    def to_review(at: dt.datetime) -> list[str]:
        return [r["idea_id"] for r in reads.desk(db, cast["meera"]["id"], tab="to_review", at=at)["items"]]

    assert cast["idea"]["idea_id"] not in to_review(f.at(10, 9, m=12))
    assert cast["idea"]["idea_id"] in to_review(f.at(17, 9, m=12))
    assert _status(db, cast["idea"]) == "with_review_desk"


def test_finding_1_the_sweep_closes_windows_and_reminds_once_per_threshold(
    db: Conn, cast: dict[str, Any]
) -> None:
    sent = asking.send_set(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                           {"questions": [{"part": "often", "text": "Is it one branch or all of them?"}],
                            "time_to_answer": "3d"}, f.at(16, 11, 20))  # fmt: skip
    assert sent["due_at"]
    day_before, two_hours = f.at(18, 18, 30), f.at(19, 16, 30)
    assert clocks.run_due(db, f.at(17, 9))["reminded"] == 0
    assert clocks.run_due(db, day_before)["reminded"] == 1
    assert clocks.run_due(db, day_before + dt.timedelta(minutes=5))["reminded"] == 0
    assert clocks.run_due(db, two_hours)["reminded"] == 1
    assert clocks.run_due(db, two_hours + dt.timedelta(minutes=5))["reminded"] == 0
    other = f.idea(db, cast["ravi"], title="Branch queue times are not tracked anywhere")
    decide.send(db, other["idea_id"], cast["meera"]["id"], {"choice": "pick", "reason": NOTE}, f.at(16, 10))
    assert clocks.run_due(db, f.at(17, 10, m=12))["windows_closed"] == 1
    assert clocks.run_due(db, f.at(17, 10, m=12))["windows_closed"] == 0


def test_finding_2_a_draft_answers_files_stay_the_sharers(db: Conn, cast: dict[str, Any]) -> None:
    sent = asking.send_set(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                           {"questions": [{"part": "evidence", "text": "Can you add a screenshot of the SMS?"}]},
                           f.at(16, 11, 20))  # fmt: skip
    db.execute(
        "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, name, bytes, store_key, kind, file_state) "
        "VALUES ('ATT-2026-000777', %s, %s, 'rejection-sms-1.png', 2048, 'k', 'file', 'checked')",
        (cast["idea"]["id"], cast["kavya"]["code"]),
    )
    qid = sent["questions"][0]["id"]
    asking.save_answer(db, qid, cast["kavya"]["id"], "Here it is.", ("ATT-2026-000777",), f.at(16, 12))
    files = lambda: [a for a in reads.reviewer_idea(db, cast["idea"]["idea_id"], cast["meera"]["id"])["artefacts"]  # noqa: E731
                     if a["kind"] == "file"]  # fmt: skip
    assert files() == []
    asking.send_answers(db, sent["id"], cast["kavya"]["id"], f.at(16, 12, 5))
    assert [a["title"] for a in files()] == ["rejection-sms-1.png"]


def test_finding_3_a_merge_reversed_from_needs_you_comes_back_to_the_desk(
    db: Conn, cast: dict[str, Any]
) -> None:
    asking.send_set(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                    {"questions": [{"part": "often", "text": "Is it one branch or all of them?"}]}, f.at(16, 9))  # fmt: skip
    assert _status(db, cast["idea"]) == "needs_you"
    merging.desk_merge(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                       {"other_idea_id": cast["other"]["idea_id"], "lead": "other", "team_up": True, "note": MERGE_NOTE},
                       f.at(16, 10))  # fmt: skip
    window = db.execute("SELECT id FROM decision_windows WHERE merge_id IS NOT NULL").fetchone()
    assert window is not None
    committee.reverse_window(db, str(window["id"]), cast["rohan"]["id"], {"note": NOTE}, f.at(17, 10))
    assert _status(db, cast["idea"]) == "with_review_desk"


def test_finding_4_a_member_never_reverses_a_merge_into_their_own_idea(
    db: Conn, cast: dict[str, Any]
) -> None:
    rohans = f.idea(db, cast["rohan"], title="Mandate rejections need plain words", shared_at=f.at(1, 9))
    merging.desk_merge(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                       {"other_idea_id": rohans["idea_id"], "lead": "other", "team_up": True, "note": MERGE_NOTE},
                       f.at(16, 10))  # fmt: skip
    window = db.execute("SELECT id FROM decision_windows WHERE merge_id IS NOT NULL").fetchone()
    assert window is not None
    row = committee.listing(db, cast["rohan"]["id"], at=f.at(16, 11))["items"][0]
    assert row["can_reverse"] is False
    with pytest.raises(Refused) as refused:
        committee.reverse_window(db, str(window["id"]), cast["rohan"]["id"], {"note": NOTE}, f.at(16, 11))
    assert refused.value.code == "own_idea"


def test_finding_5_a_reversal_never_overwrites_a_newer_decision(db: Conn, cast: dict[str, Any]) -> None:
    ref, meera = cast["idea"]["idea_id"], cast["meera"]["id"]
    decide.send(db, ref, meera, {"choice": "not_now", "reason": REASON, "return_in": "1m"}, f.at(16, 10))
    old = db.execute("SELECT id FROM decision_windows").fetchone()
    assert old is not None
    committee.extend_window(db, str(old["id"]), cast["rohan"]["id"], f.at(20, 10))  # open to mid-January
    reads.desk(db, meera, at=f.at(17, 9, m=12))  # Not now comes back
    decide.send(db, ref, meera, {"choice": "pick", "reason": NOTE}, f.at(17, 10, m=12))
    with pytest.raises(Refused) as refused:
        committee.reverse_window(db, str(old["id"]), cast["rohan"]["id"], {"to": "not_picked", "note": NOTE},
                                 f.at(18, 10, m=12))  # fmt: skip
    assert refused.value.code == "window_closed"
    assert _status(db, cast["idea"]) == "picked"


def test_finding_6_credit_follows_a_chain_of_merges(db: Conn, cast: dict[str, Any]) -> None:
    third = f.idea(db, f.person(db, "Arjun Rao"), title="SMS codes, one more time", shared_at=f.at(1, 9))
    body = {"lead": "other", "team_up": True, "note": MERGE_NOTE}
    merging.desk_merge(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                       {**body, "other_idea_id": cast["other"]["idea_id"]}, f.at(16, 10))  # fmt: skip
    merging.desk_merge(db, cast["other"]["idea_id"], cast["meera"]["id"],
                       {**body, "other_idea_id": third["idea_id"]}, f.at(16, 11))  # fmt: skip
    assert cast["kavya"]["code"] in own_codes(db, third)


def test_finding_7_admins_read_the_stage_not_the_reason(db: Conn, cast: dict[str, Any]) -> None:
    admin = f.person(db, "Priya Iyer", roles=("admin",))
    decide.send(db, cast["idea"]["idea_id"], cast["meera"]["id"], {"choice": "pick", "reason": NOTE})
    got = committee.decision_for_viewer(db, cast["idea"]["idea_id"], admin["id"])
    assert got == {"stage_only": True, "decision": {"choice": "pick", "label": "Picked"}}


def test_finding_8_a_list_where_a_word_belongs_answers_in_the_packs_shape(
    db: Conn, cast: dict[str, Any]
) -> None:
    with pytest.raises(Refused) as refused:
        revise.revise_worth(db, cast["idea"]["idea_id"], cast["meera"]["id"], {"kind": ["problem"]})
    assert (refused.value.status, refused.value.code) == (422, "kind_invalid")
