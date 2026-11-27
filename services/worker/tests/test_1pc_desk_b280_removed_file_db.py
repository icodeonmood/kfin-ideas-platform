"""BLD-B280 (the lead's answer (b) of 26 Nov; S-R2.left/3, L-LISTEN/2; DEC-107, DEC-132): its sharer may remove a file
from an answer after sending it (DEC-107 stands), so an answer sent with only a file can be left with nothing. S-R2's
read then gives `files_removed`, "The file sent with this answer was removed.", and the listen script reads the same
words, so the desk never sees or hears an empty answer. No migration: an answer is only sent with words or a file the
desk sees (DEC-132) and is never edited after, so a sent answer with neither has had its files removed.

One set of three questions about the evidence, answered at 10 am and sent at 1 pm: a file only, words and a file, and a
file only that stays. Then Kavya removes the first two files with lane C's own Remove. Synthetic people and files only
(non-negotiable 11); the object store is a dict (lane C's pattern), nothing here needs MinIO. A database test: it runs
in CI only (BLD-A251)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from attachments import files as F
from attachments import store
from core.db import Conn
from desk import asking, listen, reads
from desk.questions import ANSWER_FILES_REMOVED
from tests import convo_fixtures as fx
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

NOW = f.at(16, 15)  # Monday 16 November 2026, 3 pm IST
WORDS = "Branch R07 only. The log for R03 is with the branch head."
QS: list[dict[str, Any]] = [
    {"part": "evidence", "text": f"Can you add the November call log for branch R0{i}?"} for i in (1, 2, 3)
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
def objects(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], bytes]:
    """The object store as a dict, as lane C's file tests keep it: Remove deletes from it."""
    kept: dict[tuple[str, str], bytes] = {}
    monkeypatch.setattr(store, "delete", lambda bucket, key: kept.pop((bucket, key), None))
    return kept


@pytest.fixture
def cast(
    db: Conn, repo: Path, objects: dict[tuple[str, str], bytes], monkeypatch: pytest.MonkeyPatch
) -> dict[str, Any]:
    _ = repo, objects
    f.install_fake_notify(monkeypatch)
    kavya = f.person(db, "Kavya Menon")
    return {
        "kavya": kavya, "meera": f.person(db, "Meera Iyer", roles=("reviewer",)), "idea": f.idea(db, kavya),
    }  # fmt: skip


def _sent(db: Conn, cast: dict[str, Any]) -> list[str]:
    """The three answers sent, each with one checked file of the idea's own; returns the files' IDs in order."""
    idea, kavya = cast["idea"], cast["kavya"]
    sent = asking.send_set(db, idea["idea_id"], cast["meera"]["id"], {"questions": QS, "time_to_answer": "3d"},
                           f.at(16, 9))  # fmt: skip
    atts = []
    for q, words in zip(sent["questions"], ("", WORDS, ""), strict=True):
        att = fx.attachment(
            db, idea, kavya, file_state="checked", name=f"call-log-{q['seq']}.xlsx", purpose="idea"
        )
        asking.save_answer(db, q["id"], kavya["id"], words, [att], f.at(16, 10))
        atts.append(att)
    out = asking.send_answers(db, sent["id"], kavya["id"], f.at(16, 13))
    assert (out["sent"], out["state"]) == (3, "answered")
    return atts


def _answers(db: Conn, cast: dict[str, Any]) -> list[dict[str, Any]]:
    page = reads.reviewer_idea(db, cast["idea"]["idea_id"], cast["meera"]["id"], NOW)
    evidence = next(p for p in page["parts"] if p["part"] == "evidence")["questions"]
    return [q["answer"] for q in evidence]


def test_BLD_B280_S_R2_left_3_DEC_107_a_sent_answer_left_with_nothing_says_its_file_was_removed(
    db: Conn, cast: dict[str, Any]
) -> None:
    """Before Remove every answer lists its file and none has the line; after Kavya removes the first two files, the
    file-only answer reads the line, the answer with words keeps its words and no line, and the third is as it was."""
    atts = _sent(db, cast)
    before = _answers(db, cast)
    assert [[x["name"] for x in a["files"]] for a in before] == [["call-log-1.xlsx"], ["call-log-2.xlsx"],
                                                                 ["call-log-3.xlsx"]]  # fmt: skip
    assert [a["files_removed"] for a in before] == [None, None, None]

    for att in atts[:2]:
        F.remove(db, att, cast["kavya"]["id"])  # DEC-107: it works after the answer is sent

    after = _answers(db, cast)
    assert [[x["name"] for x in a["files"]] for a in after] == [[], [], ["call-log-3.xlsx"]]
    assert [a["files_removed"] for a in after] == [ANSWER_FILES_REMOVED, None, None]
    assert [(a["text"] or "").strip() for a in after] == ["", WORDS, ""]
    # the desk never sees an empty answer: each has words, a file or the line
    assert all((a["text"] or "").strip() or a["files"] or a["files_removed"] for a in after)
    assert ANSWER_FILES_REMOVED == "The file sent with this answer was removed."


def test_BLD_B280_L_LISTEN_2_the_listen_script_reads_the_same_line(db: Conn, cast: dict[str, Any]) -> None:
    """The listen script hears what S-R2 shows: "Kavya answered: The file sent with this answer was removed." for the
    emptied answer, the words for the other; never "Kavya answered:" with nothing after it."""
    atts = _sent(db, cast)
    for att in atts[:2]:
        F.remove(db, att, cast["kavya"]["id"])
    spoken = reads._spoken_answers(db, cast["idea"]["id"], NOW)["evidence"]
    assert spoken[:2] == [listen.Answer("Kavya", ANSWER_FILES_REMOVED), listen.Answer("Kavya", WORDS)]
    script = listen.build({}, answers={"evidence": spoken[:2]})
    said = next(p for p in script.parts if p.part == "evidence").text
    assert "Kavya answered: The file sent with this answer was removed." in said
