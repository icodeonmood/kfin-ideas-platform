"""L-REVIEW.open and L-DECIDE against the database (V-ACC.review/4, /9, /14; L-DECIDE.rules/3, /5–10).

Needs Postgres with the handoff cut-over applied (`make up`, then the tests migrate their own database).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import decide, review
from desk.store import Refused, unseal
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

REASON = "A clear problem, a real number and a simple fix. Folio 1234567890 shows it well."


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


def test_L_REVIEW_open_1_first_open_closes_the_edit_window_and_assigns(
    db: Conn, cast: dict[str, Any]
) -> None:
    ref, t = cast["idea"]["idea_id"], f.at(16, 9, 50)
    got = review.open_idea(db, ref, cast["meera"]["id"], t)
    assert got["first"] is True
    row = db.execute("SELECT * FROM ideas WHERE idea_id = %s", (ref,)).fetchone()
    assert row is not None
    assert (row["opened_at"], str(row["opened_by"]), str(row["reviewer_id"])) == (
        t,
        cast["meera"]["id"],
        cast["meera"]["id"],
    )
    assert row["edit_closes_at"] == t
    assert f.events(db, row["id"]) == ["desk.opened"]
    # idempotent: a second open changes nothing
    assert review.open_idea(db, ref, cast["meera"]["id"], f.at(16, 11))["first"] is False
    assert f.events(db, row["id"]) == ["desk.opened"]


def test_V_ACC_review_14_a_reviewer_opening_their_own_idea_only_looks(db: Conn, cast: dict[str, Any]) -> None:
    mine = f.idea(db, cast["meera"])
    assert review.open_idea(db, mine["idea_id"], cast["meera"]["id"])["own"] is True
    row = db.execute("SELECT opened_at FROM ideas WHERE id = %s", (mine["id"],)).fetchone()
    assert row is not None and row["opened_at"] is None
    with pytest.raises(Refused) as refused:
        decide.send(db, mine["idea_id"], cast["meera"]["id"], {"choice": "pick", "reason": REASON})
    assert (refused.value.status, refused.value.code) == (403, "own_idea")
    assert "desk.own_idea_refused" in f.audit_actions(db, f"idea:{mine['idea_id']}")


def test_V_ACC_review_4_pick_with_a_reason_opens_a_30_day_window(db: Conn, cast: dict[str, Any]) -> None:
    ref, t = cast["idea"]["idea_id"], f.at(16, 16, 58)
    d = decide.send(db, ref, cast["meera"]["id"], {"choice": "pick", "reason": REASON}, t)
    assert d["label"] == "Picked" and d["team_by"] == f.at(27, 18).isoformat()
    assert (
        "1234567890" not in d["reason"] and "Folio ••••90" in d["reason"]
    )  # L-HIDE on what the sharer reads
    row = db.execute("SELECT status, opened_at FROM ideas WHERE idea_id = %s", (ref,)).fetchone()
    assert row is not None and row["status"] == "picked" and row["opened_at"] == t
    stored = db.execute("SELECT * FROM idea_decisions WHERE id = %s", (d["id"],)).fetchone()
    assert stored is not None
    assert unseal(stored["reason_encrypted"], "idea_decisions", "reason_encrypted", d["id"]) == d["reason"]
    w = db.execute("SELECT * FROM decision_windows WHERE decision_id = %s", (d["id"],)).fetchone()
    assert w is not None and (w["state"], w["closes_at"], w["max_closes_at"]) == (
        "open", t + dt.timedelta(days=30), f.at(16, 16, 58, m=2, y=2027)
    )  # fmt: skip
    assert f.audit_actions(db, f"idea:{ref}")[-1] == "desk.decide"


def test_V_ACC_review_9_nothing_is_sent_without_a_choice_and_a_reason(db: Conn, cast: dict[str, Any]) -> None:
    ref = cast["idea"]["idea_id"]
    for body, code, message in (
        ({"reason": REASON}, "choice_required", "Choose Pick, Not now or Not picked first."),
        ({"choice": "pick", "reason": "Too short"}, "reason_too_short",
         "Give Kavya a reason of at least a line, 30 characters or more."),
    ):  # fmt: skip
        with pytest.raises(Refused) as refused:
            decide.send(db, ref, cast["meera"]["id"], body)
        assert (refused.value.code, refused.value.message) == (code, message)
    assert db.execute("SELECT count(*) AS n FROM idea_decisions").fetchone() == {"n": 0}


def test_L_DECIDE_rules_4_BLD_B236_the_wording_check_warns_with_the_words_then_lets_it_through(
    db: Conn, cast: dict[str, Any]
) -> None:
    ref, reason = cast["idea"]["idea_id"], "This is a duplicate of the SMS idea, so it is not going ahead."
    with pytest.raises(Refused) as refused:
        decide.send(db, ref, cast["meera"]["id"], {"choice": "not_picked", "reason": reason})
    assert refused.value.code == "wording_check" and "“duplicate”" in (refused.value.message or "")
    err = refused.value.body()["error"]
    assert (refused.value.status, err["field"], err["words"]) == (422, "reason", ["duplicate"])
    assert err["suggestions"] == [
        {"word": "duplicate", "suggestion": "say it is the same problem as another idea, and name it"}
    ]
    assert db.execute("SELECT count(*) AS n FROM idea_decisions").fetchone() == {"n": 0}
    for not_yes in ("true", 1):  # only a real `true` sends it as written
        with pytest.raises(Refused):
            decide.send(
                db,
                ref,
                cast["meera"]["id"],
                {"choice": "not_picked", "reason": reason, "wording_ok": not_yes},
            )
    d = decide.send(
        db, ref, cast["meera"]["id"], {"choice": "not_picked", "reason": reason, "wording_ok": True}
    )
    assert d["choice"] == "not_picked"


def test_L_DECIDE_rules_7_not_now_comes_back_on_its_date(db: Conn, cast: dict[str, Any]) -> None:
    ref, t = cast["idea"]["idea_id"], f.at(16, 16, 58)
    d = decide.send(db, ref, cast["meera"]["id"],
                    {"choice": "not_now", "reason": "Right problem; the new SMS vendor arrives in February.",
                     "return_in": "3m"}, t)  # fmt: skip
    assert d["return_at"] == f.at(16, 16, 58, m=2, y=2027).isoformat()
    uuid_ = cast["idea"]["id"]
    assert decide.return_from_not_now(db, str(uuid_), f.at(1, 9, m=2, y=2027)) is False  # not yet
    assert decide.return_from_not_now(db, str(uuid_), f.at(17, 9, m=2, y=2027)) is True
    row = db.execute("SELECT status, decide_by FROM ideas WHERE id = %s", (uuid_,)).fetchone()
    assert (
        row is not None
        and row["status"] == "with_review_desk"
        and row["decide_by"] == f.at(23, 18, m=2, y=2027)
    )


def test_L_DECIDE_rules_10_open_sets_close_and_queued_ones_are_dropped(
    db: Conn, cast: dict[str, Any]
) -> None:
    uuid_, meera = cast["idea"]["id"], cast["meera"]["id"]
    db.execute("INSERT INTO question_sets (idea_uuid, by_user_id) VALUES (%s, %s)", (uuid_, meera))
    db.execute(
        "INSERT INTO question_sets (idea_uuid, by_user_id, state, sent_at, due_at, time_to_answer) "
        "VALUES (%s, %s, 'seen', now(), now() + interval '3 days', '3d')",
        (uuid_, meera),
    )
    decide.send(db, cast["idea"]["idea_id"], meera, {"choice": "pick", "reason": REASON})
    states = [
        r["state"] for r in db.execute("SELECT state FROM question_sets WHERE idea_uuid = %s", (uuid_,))
    ]
    assert states == ["closed"]


def test_a_decided_idea_cannot_be_decided_again(db: Conn, cast: dict[str, Any]) -> None:
    ref, meera = cast["idea"]["idea_id"], cast["meera"]["id"]
    decide.send(db, ref, meera, {"choice": "pick", "reason": REASON})
    with pytest.raises(Refused) as refused:
        decide.send(db, ref, meera, {"choice": "not_picked", "reason": REASON})
    assert refused.value.code == "already_decided"
