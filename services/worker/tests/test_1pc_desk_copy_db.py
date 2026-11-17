"""The reviewer's page, word for word against the DeskIdea board (reference/copy/DeskIdea.md; S-R2.left/2–3): the
asked and answered lines, the Attached line and what it says is hidden, a file sent with the answers, and the day
the sharer wrote their own words."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import asking, reads
from desk.store import seal
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

SENT = f.at(16, 11, 20)  # Monday 16 November, 11:20 am
QS: list[dict[str, Any]] = [
    {"part": "often", "text": "Is the 40 calls a day at one branch, or across Hyderabad?"},
    {"part": "evidence", "text": "Can you add a screenshot of the SMS, with the folio hidden?"},
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
def cast(db: Conn, repo: Path) -> dict[str, Any]:
    kavya = f.person(db, "Kavya Menon")
    return {
        "kavya": kavya,
        "meera": f.person(db, "Meera Iyer", roles=("reviewer",)),
        "anil": f.person(db, "Anil Kapoor", roles=("reviewer",)),
        "idea": f.idea(db, kavya, shared_at=f.at(16, 9)),
    }


def _page(db: Conn, cast: dict[str, Any], viewer: str = "meera", at: Any = None) -> dict[str, Any]:
    return reads.reviewer_idea(db, cast["idea"]["idea_id"], cast[viewer]["id"], at or f.at(18, 10))


def _file(db: Conn, cast: dict[str, Any], fid: str, name: str, note: str | None = None) -> str:
    db.execute(
        "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, name, mime, bytes, store_key, kind, file_state, "
        "hidden_note) VALUES (%s, %s, %s, %s, 'image/png', 143360, 'clean/x', 'file', 'checked', %s)",
        (fid, cast["idea"]["id"], cast["kavya"]["code"], name, note),
    )
    return fid


def _hide(db: Conn, cast: dict[str, Any], kind: str, masked: str) -> None:
    db.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked) VALUES (%s, 'message', 'm1', %s, %s)",
        (cast["idea"]["id"], kind, masked),
    )


def test_S_R2_left_3_asked_and_answered_lines_put_a_comma_between_the_day_and_the_time(
    db: Conn, cast: dict[str, Any]
) -> None:
    sent = asking.send_set(db, cast["idea"]["idea_id"], cast["meera"]["id"], {"questions": QS}, SENT)
    asking.save_answer(db, sent["questions"][0]["id"], cast["kavya"]["id"], "One branch, about 40 a day.",
                       at=f.at(16, 16, 32))  # fmt: skip
    asking.send_answers(db, sent["id"], cast["kavya"]["id"], f.at(16, 16, 32))

    def lines(viewer: str, at: Any) -> list[tuple[str, str | None]]:
        page = _page(db, cast, viewer, at)
        return [
            (q["asked_line"], q["answer"]["line"] if q["answer"] else None)
            for p in page["parts"]
            for q in p["questions"]
        ]

    assert lines("meera", f.at(18, 10)) == [
        ("You asked, Monday 16 November, 11:20 am", "Kavya answered, Monday 16 November, 4:32 pm"),
        ("You asked, Monday 16 November, 11:20 am", None),
    ]
    assert lines("anil", f.at(17, 10))[0] == (
        "Meera asked, yesterday, 11:20 am",
        "Kavya answered, yesterday, 4:32 pm",
    )
    assert lines("meera", f.at(16, 17))[0] == ("You asked, today 11:20 am", "Kavya answered, today 4:32 pm")


def test_S_R2_left_3_the_attached_line_says_what_is_hidden_from_everyone(
    db: Conn, cast: dict[str, Any]
) -> None:
    _file(db, cast, "ATT-2026-000971", "branch-call-log-nov.pdf")

    def attached() -> str:
        return next(str(p["text"]) for p in _page(db, cast)["parts"] if p["part"] == "evidence")

    assert attached() == "One file: branch-call-log-nov.pdf."
    _hide(db, cast, "folio", "Folio ••••89")
    assert attached() == "One file: branch-call-log-nov.pdf. Folio ••••89 is hidden from everyone."
    db.execute("UPDATE hidden_details SET masked = 'Folio' WHERE idea_uuid = %s", (cast["idea"]["id"],))
    assert attached() == "One file: branch-call-log-nov.pdf. Folio is hidden from everyone."
    _hide(db, cast, "phone", "Phone ••••21")
    assert attached() == "One file: branch-call-log-nov.pdf. Folio and phone number are hidden from everyone."


def test_S_R2_left_2_a_file_sent_with_the_answers_and_the_day_the_words_were_written(
    db: Conn, cast: dict[str, Any]
) -> None:
    mid = str(uuid.uuid4())
    db.execute(
        "INSERT INTO idea_messages (id, idea_uuid, seq, via, text_encrypted, created_at) "
        "VALUES (%s, %s, 1, 'typed', %s, %s)",
        (mid, cast["idea"]["id"], seal("Investors call about R07.", "idea_messages", "text_encrypted", mid),
         f.at(14, 9, 50)),  # written on Saturday, shared on Monday
    )  # fmt: skip
    _hide(db, cast, "folio", "Folio ••••89")
    sent = asking.send_set(db, cast["idea"]["idea_id"], cast["meera"]["id"], {"questions": QS}, SENT)
    fid = _file(db, cast, "ATT-2026-000972", "rejection-sms-1.png", "Folio hidden.")
    asking.save_answer(db, sent["questions"][1]["id"], cast["kavya"]["id"], "Two screenshots attached.", [fid],
                       f.at(16, 16, 30))  # fmt: skip
    asking.send_answers(db, sent["id"], cast["kavya"]["id"], f.at(16, 16, 32))
    arts = _page(db, cast, at=f.at(16, 17))["artefacts"]
    by_kind = {a["kind"]: a for a in arts}
    assert by_kind["file"]["line"] == "Added with Kavya’s answers today. Folio hidden."
    assert by_kind["own_words"]["line"] == "As Kavya wrote them on Saturday, before the draft. Folio hidden."
    later = {a["kind"]: a for a in _page(db, cast, at=f.at(19, 10))["artefacts"]}
    assert later["file"]["line"] == "Added with Kavya’s answers on Monday 16 November. Folio hidden."
