"""The second independent review of lane B's back end (17 Nov 2026), each finding pinned by a test against the
database: bodies of the wrong type, co-sharers' drafts, the crew told of decisions, the panel and the asked lines,
answer files by check state (DEC-107), more time on an overdue set and a sweep that carries on past a bad item."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import asking, revise
from desk.store import Refused
from tests import desk_fixtures as f

SENT = f.at(16, 11, 20)  # Monday 16 November 2026, 11:20 am IST
QS: list[dict[str, Any]] = [
    {"part": "often", "text": "Is the 40 calls a day at one branch, or across Hyderabad?"},
    {"part": "evidence", "text": "Can you add a screenshot of the SMS, with the folio hidden?"},
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
