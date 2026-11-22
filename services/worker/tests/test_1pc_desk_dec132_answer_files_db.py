"""DEC-132 (BLD-B275, L-QUESTIONS.answer/3, /5; DEC-107): an answer to the review desk whose only file is infected,
locked or failed its checks does not count as answered, so it is not sent and the desk never receives an empty answer.
A file still checking counts once its check ends. A file the desk sees (checked, or holding a customer detail, which
can still be sent and is marked) counts. The rule is `asking._counts`, used by S-R3's "N of M answered" and Send's
label (`open_set_for_sharer`) and by `send_answers`, and it is the desk's own read: the answers it receives each hold
words or a file it can open.

One set of six questions, each answered with no words and one file of the idea's own (`purpose = 'idea'`, BLD-B274)
in one state. Synthetic people and files only (non-negotiable 11); lane B's and lane F's fixtures, cleaned up after
each test."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import asking, questions, reads
from desk.store import Refused
from tests import convo_fixtures as fx
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

NOW = f.at(16, 13)  # Monday 16 November 2026, 1 pm IST
# Each question's one file and its state: the first four never reach the desk, the last two do
NOT_SEEN = ("infected", "upload_failed", "locked", "checking")
SEEN = ("personal_data_found", "checked")
QS: list[dict[str, Any]] = [
    {"part": "evidence", "text": f"Can you add the November call log for branch R0{i + 1}?"}
    for i in range(len(NOT_SEEN) + len(SEEN))
]


@pytest.fixture
def repo(company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    get_settings.cache_clear()
    yield company_repo
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def cast(db: Conn, repo: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    _ = repo
    f.install_fake_notify(monkeypatch)
    kavya = f.person(db, "Kavya Menon")
    return {
        "kavya": kavya, "meera": f.person(db, "Meera Iyer", roles=("reviewer",)), "idea": f.idea(db, kavya),
    }  # fmt: skip


def _file_only_answers(
    db: Conn, cast: dict[str, Any], states: tuple[str, ...]
) -> tuple[dict[str, Any], list[str]]:
    """The set sent at 9 am, and each question answered at 10 am with no words and one file in `states`' order."""
    idea, kavya = cast["idea"], cast["kavya"]
    sent = asking.send_set(db, idea["idea_id"], cast["meera"]["id"], {"questions": QS, "time_to_answer": "3d"},
                           f.at(16, 9))  # fmt: skip
    answer_ids = []
    for q, state in zip(sent["questions"], states, strict=True):
        att = fx.attachment(db, idea, kavya, file_state=state, name=f"call-log-{state}.xlsx", purpose="idea")
        saved = asking.save_answer(db, q["id"], kavya["id"], "", [att], f.at(16, 10))
        assert [x["id"] for x in saved["files"]] == [att], state
        answer_ids.append(str(saved["id"]))
    return sent, answer_ids


def _sent_at(db: Conn, answer_ids: list[str]) -> list[bool]:
    rows = {
        str(r["id"]): r["sent_at"] is not None
        for r in db.execute(
            "SELECT id, sent_at FROM answers WHERE id = ANY(%s::uuid[])", (answer_ids,)
        ).fetchall()
    }
    return [rows[a] for a in answer_ids]


def test_DEC_132_L_QUESTIONS_answer_3_BLD_B275_a_file_counts_only_in_a_state_the_desk_sees() -> None:
    """The rule on its own: words, or a file in the desk's states; nothing else counts."""
    for state in (*NOT_SEEN, "uploading", "too_big", None):
        assert not asking._has_content({"text": "  ", "files": [{"state": state}]}), state
    for state in (*SEEN, "hidden_checked", "ok"):
        assert asking._has_content({"text": "", "files": [{"state": "infected"}, {"state": state}]}), state
    assert asking._has_content({"text": "Branch R07 only.", "files": [{"state": "infected"}]})
    assert not asking._has_content({"text": "", "files": []})


def test_DEC_132_S_R3_L_QUESTIONS_answer_3_BLD_B275_answers_whose_only_file_is_infected_or_failed_are_not_answered(
    db: Conn, cast: dict[str, Any]
) -> None:
    """With only the four the desk never sees, S-R3 says nothing is answered, Send's label is the disabled one, and
    sending is refused with S-R3's words; no answer is sent."""
    sent, answer_ids = _file_only_answers(db, cast, NOT_SEEN)
    mine = asking.open_set_for_sharer(db, cast["idea"]["idea_id"], cast["kavya"]["id"], NOW)
    assert mine is not None
    assert mine["progress"] == f"0 of {len(NOT_SEEN)} answered"
    assert mine["send_label"] == questions.send_answers_label(0) == asking.NOTHING_ANSWERED
    # the sharer still sees each of her own files on her answer, in its state (she removes or replaces it)
    assert [[x["state"] for x in q["answer"]["files"]] for q in mine["questions"]] == [[s] for s in NOT_SEEN]
    with pytest.raises(Refused) as refused:
        asking.send_answers(db, sent["id"], cast["kavya"]["id"], NOW)
    got = refused.value
    assert (got.status, got.code, got.message) == (422, "nothing_answered", asking.NOTHING_ANSWERED)
    assert _sent_at(db, answer_ids) == [False] * len(NOT_SEEN)


def test_DEC_132_S_R2_left_3_L_QUESTIONS_answer_5_BLD_B275_only_answers_with_a_file_the_desk_sees_are_sent(
    db: Conn, cast: dict[str, Any]
) -> None:
    """With all six, the two with a file the desk sees go (the found one marked, DEC-107); the other four stay unsent
    for the sharer to fix, and the desk lists exactly the two, each with its file."""
    states = (*NOT_SEEN, *SEEN)
    sent, answer_ids = _file_only_answers(db, cast, states)
    mine = asking.open_set_for_sharer(db, cast["idea"]["idea_id"], cast["kavya"]["id"], NOW)
    assert mine is not None
    assert mine["progress"] == f"{len(SEEN)} of {len(states)} answered"
    assert mine["send_label"] == questions.send_answers_label(len(SEEN))
    out = asking.send_answers(db, sent["id"], cast["kavya"]["id"], NOW)
    assert (out["sent"], out["answered"], out["state"]) == (len(SEEN), len(SEEN), "partly_answered")
    assert _sent_at(db, answer_ids) == [False] * len(NOT_SEEN) + [True] * len(SEEN)
    page = reads.reviewer_idea(db, cast["idea"]["idea_id"], cast["meera"]["id"], NOW)
    evidence = next(p for p in page["parts"] if p["part"] == "evidence")["questions"]
    answered = [q["answer"] for q in evidence if q["answer"] is not None]
    assert [[(x["name"], x["customer_detail"]) for x in a["files"]] for a in answered] == [
        [("call-log-personal_data_found.xlsx", True)],
        [("call-log-checked.xlsx", False)],
    ]
    assert all(a["files"] for a in answered)  # the desk never receives an empty answer
