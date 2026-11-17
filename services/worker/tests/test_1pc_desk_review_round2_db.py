"""The second independent review of lane B's back end (17 Nov 2026), each finding pinned by a test against the
database: bodies of the wrong type, co-sharers' drafts, the crew told of decisions, the panel and the asked lines,
answer files by check state (DEC-107), more time on an overdue set and a sweep that carries on past a bad item."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import asking, merging, revise
from desk.store import Refused
from tests import desk_fixtures as f

SENT = f.at(16, 11, 20)  # Monday 16 November 2026, 11:20 am IST
QS: list[dict[str, Any]] = [
    {"part": "often", "text": "Is the 40 calls a day at one branch, or across Hyderabad?"},
    {"part": "evidence", "text": "Can you add a screenshot of the SMS, with the folio hidden?"},
]
REASON = "A clear problem, a real number and a simple fix that the branch can try."
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
        "anil": f.person(db, "Anil Kapoor", roles=("reviewer",)),
        "rohan": f.person(db, "Rohan Mehta", roles=("committee",)),
        "idea": f.idea(db, kavya),
    }  # fmt: skip


def _send(db: Conn, cast: dict[str, Any], by: str = "meera", **body: Any) -> dict[str, Any]:
    return asking.send_set(
        db, cast["idea"]["idea_id"], cast[by]["id"], {"questions": QS, "time_to_answer": "3d", **body}, SENT
    )


def _refused(fn: Any, *args: Any) -> Refused:
    with pytest.raises(Refused) as refused:
        fn(*args)
    return refused.value


# ---- finding 3: a list, object or number in a body is refused in the pack's shape, never a 500 ----------------
def test_L_WORTH_a_list_object_or_number_where_a_figure_belongs_is_refused(
    db: Conn, cast: dict[str, Any]
) -> None:
    ref, meera = cast["idea"]["idea_id"], cast["meera"]["id"]
    for body, code, field in (
        ({"outside_tools": []}, "outside_tools_invalid", "outside_tools"),
        ({"outside_tools": {}}, "outside_tools_invalid", "outside_tools"),
        ({"hours_month": 70}, "worth_invalid", "hours_month"),
        ({"hours_month": ["70"]}, "worth_invalid", "hours_month"),
        ({"worth": {"cost_month": {"low": 1}}}, "worth_invalid", "cost_month"),
        ({"hours_month": "99,99,99,99,999"}, "worth_invalid", "hours_month"),  # past numeric(12,2)
        ({"revenue_month": "1 to 5,00,000 crore"}, "worth_invalid", "revenue_month"),  # past numeric(14,2)
    ):
        e = _refused(revise.revise_worth, db, ref, meera, body)
        assert (e.status, e.code, e.field) == (422, code, field), body
    e = _refused(revise.revise_worth, db, ref, meera, {"cost_month": "1,20,00,00,00,00,000"})
    assert e.message == "That figure is too large. Check it and write it again."
    assert db.execute("SELECT count(*) AS n FROM idea_worth").fetchone() == {"n": 0}
    ok = revise.revise_worth(db, ref, meera, {"cost_month": "₹1,200 crore"})
    assert ok["reviewer"]["cost_month"]["low"] == 1.2e10


def test_L_QUESTIONS_answer_a_number_where_the_files_or_the_text_belong_is_refused(
    db: Conn, cast: dict[str, Any]
) -> None:
    sent = _send(db, cast)
    q1, kavya = sent["questions"][0]["id"], cast["kavya"]["id"]
    for text, file_ids, code, field in (
        ("Across Hyderabad.", 5, "file_not_found", "file_ids"),
        ("Across Hyderabad.", "ATT-2026-000001", "file_not_found", "file_ids"),
        ("Across Hyderabad.", [{"id": "ATT-2026-000001"}], "file_not_found", "file_ids"),
        ({"text": "Across Hyderabad."}, None, "answer_invalid", "text"),
        (["Across Hyderabad."], None, "answer_invalid", "text"),
    ):
        e = _refused(asking.save_answer, db, q1, kavya, text, file_ids)
        assert (e.status, e.code, e.field) == (422, code, field)
    assert asking.save_answer(db, q1, kavya, None, None)["text"] == ""


# ---- finding 6: WorthResponse is what the worker returns (figures, the person under reviewer.by) ----------------
def test_L_WORTH_the_revision_response_matches_the_shared_sample(db: Conn, cast: dict[str, Any]) -> None:
    """desk/worth_response_sample.json is what apps/web/tests/unit/desk-worth.test.ts checks `WorthResponse` against."""
    import json

    sample = json.loads(
        (Path(__file__).parents[1] / "desk" / "worth_response_sample.json").read_text("utf-8")
    )
    sample.pop("_about")
    db.execute(
        "INSERT INTO idea_worth (idea_uuid, by_side, by_code, hours_low, hours_high, cost_low, outside_tools, at) "
        "VALUES (%s, 'sharer', %s, 70, 150, 25000, 'none', %s)",
        (cast["idea"]["id"], cast["kavya"]["code"], f.at(14, 10)),
    )
    got = revise.revise_worth(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                              {"hours_month": "120 to 200", "outside_tools": "partly",
                               "note": "Every branch in the region takes these calls, not one."}, SENT)  # fmt: skip
    got = json.loads(json.dumps(got))
    for key in ("idea_id", "worth_id"):
        got[key] = sample[key]
    got["reviewer"]["by"]["id"] = sample["reviewer"]["by"]["id"]
    assert dt.datetime.fromisoformat(got["reviewer"]["at"]) == SENT
    got["reviewer"]["at"] = sample["reviewer"]["at"]
    assert got == sample


def _merge_ravi_in(db: Conn, cast: dict[str, Any]) -> dict[str, Any]:
    """Ravi's idea joins Kavya's at the desk: Ravi is credited (own_codes) and joins the crew."""
    theirs = f.idea(db, cast["ravi"], title="Rejection SMS codes confuse investors", shared_at=f.at(2, 15))
    merging.desk_merge(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                       {"other_idea_id": theirs["idea_id"], "lead": "this", "team_up": True, "note": MERGE_NOTE},
                       f.at(16, 10))  # fmt: skip
    return theirs


# ---- finding 4: a credited co-sharer never sees, sends or overwrites another sharer's draft ---------------------
def test_L_QUESTIONS_answer_4_a_draft_answer_stays_with_the_sharer_who_wrote_it(
    db: Conn, cast: dict[str, Any]
) -> None:
    _merge_ravi_in(db, cast)
    sent = _send(db, cast)
    ref, kavya, ravi = cast["idea"]["idea_id"], cast["kavya"]["id"], cast["ravi"]["id"]
    q1, q2 = (q["id"] for q in sent["questions"])
    asking.save_answer(db, q1, kavya, "One branch, about 40 a day.", at=SENT)
    seen_by_ravi = asking.open_set_for_sharer(db, ref, ravi, SENT)
    assert seen_by_ravi is not None and [q["answer"] for q in seen_by_ravi["questions"]] == [None, None]
    e = _refused(asking.save_answer, db, q1, ravi, "All of Hyderabad.")
    assert (e.status, e.code) == (409, "answer_in_progress")
    assert _refused(asking.send_answers, db, sent["id"], ravi).code == "nothing_answered"
    asking.save_answer(db, q2, ravi, "The SMS says R07 and nothing else.", at=SENT)
    assert asking.send_answers(db, sent["id"], ravi, SENT)["sent"] == 1
    mine = asking.open_set_for_sharer(db, ref, kavya, SENT)
    assert mine is not None
    first, second = (q["answer"] for q in mine["questions"])
    assert (first["text"], first["sent"]) == ("One branch, about 40 a day.", False)  # still Kavya's to send
    assert second["sent"] is True and second["by"]["first_name"] == "Ravi"
    assert asking.send_answers(db, sent["id"], kavya, SENT)["state"] == "answered"
