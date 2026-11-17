"""The review of ae4a140 (17 Nov 2026), each finding pinned by a test against the database: no reminder the moment a
1-day set arrives, an empty draft never locks a co-sharer out, the test helpers leave no timer rows behind, the
committee's chair reads the desk, and a worth note that is not text is refused."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from psycopg.types.json import Jsonb

from core.db import Conn
from desk import asking, clocks, committee, merging, reads, revise
from desk.store import READERS, REVIEWERS, Refused, require_role
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

QS: list[dict[str, Any]] = [
    {"part": "often", "text": "Is the 40 calls a day at one branch, or across Hyderabad?"},
    {"part": "evidence", "text": "Can you add a screenshot of the SMS, with the folio hidden?"},
]
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
        "idea": f.idea(db, kavya),
    }  # fmt: skip


def _refused(fn: Any, *args: Any) -> Refused:
    with pytest.raises(Refused) as refused:
        fn(*args)
    return refused.value


# ---- 1: a 1-day set sent after the deadline hour is not reminded as it arrives (L-QUESTIONS.clock/2) -------------
def test_L_QUESTIONS_clock_2_a_one_day_set_is_reminded_two_hours_before_and_never_as_it_arrives(
    db: Conn, cast: dict[str, Any]
) -> None:
    sent_at = f.at(16, 19)  # Monday 7 pm, after the 6 pm deadline hour; "1 day" is 24 hours: due Tuesday 7 pm
    sent = asking.send_set(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                           {"questions": QS, "time_to_answer": "1d"}, sent_at)  # fmt: skip
    assert dt.datetime.fromisoformat(sent["due_at"]) == f.at(17, 19)
    assert clocks.run_due(db, f.at(16, 19, 5))["reminded"] == 0  # its "1 day before" is the sending itself
    assert asking.remind_due(db, sent["id"], f.at(16, 19, 5)) is False
    assert clocks.run_due(db, f.at(17, 17, 5))["reminded"] == 1  # 2 hours before the deadline
    assert clocks.run_due(db, f.at(17, 17, 10))["reminded"] == 0  # once


# ---- 2: an empty draft is nobody's yet; a draft with text or a file stays its writer's (L-QUESTIONS.answer/4) ----
def _merge_ravi_in(db: Conn, cast: dict[str, Any]) -> None:
    theirs = f.idea(db, cast["ravi"], title="Rejection SMS codes confuse investors", shared_at=f.at(2, 15))
    merging.desk_merge(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                       {"other_idea_id": theirs["idea_id"], "lead": "this", "team_up": True, "note": MERGE_NOTE},
                       f.at(16, 10))  # fmt: skip


def test_L_QUESTIONS_answer_4_an_empty_autosave_never_locks_a_co_sharer_out(
    db: Conn, cast: dict[str, Any]
) -> None:
    _merge_ravi_in(db, cast)
    sent = asking.send_set(db, cast["idea"]["idea_id"], cast["meera"]["id"], {"questions": QS}, f.at(16, 11))
    q1, q2 = (q["id"] for q in sent["questions"])
    kavya, ravi = cast["kavya"]["id"], cast["ravi"]["id"]
    asking.save_answer(db, q1, kavya, "", at=f.at(16, 12))  # Kavya opened the box and wrote nothing
    took = asking.save_answer(
        db, q1, ravi, "All of Hyderabad, about 40 a day at each branch.", at=f.at(16, 12, 5)
    )
    assert took["text"].startswith("All of Hyderabad")
    owner = db.execute("SELECT by_code FROM answers WHERE question_id = %s", (q1,)).fetchone()
    assert owner == {"by_code": cast["ravi"]["code"]}
    assert _refused(asking.save_answer, db, q1, kavya, "Mine.").code == "answer_in_progress"  # now Ravi's
    # a file alone is an answer in progress: it stays Kavya's
    fid = "ATT-2026-000931"
    db.execute(
        "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, name, mime, bytes, store_key, kind, file_state) "
        "VALUES (%s, %s, %s, 'sms-1.png', 'image/png', 2048, 'clean/x', 'file', 'checked')",
        (fid, cast["idea"]["id"], cast["kavya"]["code"]),
    )
    asking.save_answer(db, q2, kavya, "", [fid], f.at(16, 12, 10))
    e = _refused(asking.save_answer, db, q2, ravi, "The SMS says R07.")
    assert (e.status, e.code) == (409, "answer_in_progress")


# ---- 3: the helpers remove the timer rows keyed to what they made (crunch rule 14) -----------------------------
def test_crunch_rule_14_remove_made_takes_the_jobs_keyed_to_the_ideas_sets_and_windows(
    db: Conn, cast: dict[str, Any]
) -> None:
    sent = asking.send_set(db, cast["idea"]["idea_id"], cast["meera"]["id"], {"questions": QS}, f.at(16, 11))

    def job(payload: dict[str, Any], key: str | None) -> int:
        row = db.execute(
            "INSERT INTO jobs (type, payload, dedupe_key, run_at) VALUES ('desk.answer_reminder', %s, %s, now()) "
            "RETURNING id",
            (Jsonb(payload), key),
        ).fetchone()
        assert row is not None
        return int(row["id"])

    keyed = [job({"set_id": sent["id"]}, None), job({}, f"idea:{cast['idea']['id']}")]
    other = job({"set_id": "00000000-0000-4000-8000-00000000abcd"}, None)
    try:
        f.remove_made(db, [cast["kavya"]["id"]], [str(cast["idea"]["id"])])
        left = {
            int(r["id"]) for r in db.execute("SELECT id FROM jobs WHERE id = ANY(%s)", ([*keyed, other],))
        }
        assert left == {other}
        assert db.execute("SELECT 1 FROM ideas WHERE id = %s", (cast["idea"]["id"],)).fetchone() is None
    finally:
        db.execute("DELETE FROM jobs WHERE id = ANY(%s)", ([*keyed, other],))


# ---- 4: the committee's chair reads the desk and the decision, and never acts on it (P-PRODUCT.privacy) -------
def test_P_PRODUCT_privacy_the_chair_reads_the_desk_and_the_decision_but_never_writes(
    db: Conn, cast: dict[str, Any]
) -> None:
    chair = f.person(db, "Vivek Shenoy", roles=("core_chair",))
    require_role(db, chair["id"], READERS)
    ref = cast["idea"]["idea_id"]
    assert reads.reviewer_idea(db, ref, chair["id"], f.at(16, 11))["idea"]["id"] == ref
    assert reads.listen_script(db, ref, chair["id"])["parts"]
    assert committee.may_read_decision(db, chair["id"], cast["idea"]) is True
    e = _refused(require_role, db, chair["id"], REVIEWERS)
    assert (e.status, e.code) == (403, "forbidden")


# ---- 5: a worth note that is not text is refused in the pack's shape, never stored as its repr (BLD-B233) ------
def test_L_WORTH_a_note_that_is_not_text_is_refused(db: Conn, cast: dict[str, Any]) -> None:
    for note in (["Every branch"], {"text": "Every branch"}, 5):
        e = _refused(revise.revise_worth, db, cast["idea"]["idea_id"], cast["meera"]["id"],
                     {"hours_month": "120 to 200", "note": note})  # fmt: skip
        assert (e.status, e.code, e.field, e.message) == (
            422,
            "note_invalid",
            "note",
            "Write the note as text.",
        )
    assert db.execute(
        "SELECT count(*) AS n FROM idea_worth WHERE idea_uuid = %s", (cast["idea"]["id"],)
    ).fetchone() == {"n": 0}
