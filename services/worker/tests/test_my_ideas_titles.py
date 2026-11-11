"""My ideas names an idea before its canvas is confirmed (BLD-A166).

Lane D's screenshots showed "Your idea IDEA-2026-001473" for an idea the scan had finished but the person had not
yet confirmed: the canvas, which holds the one line, is written only at the confirm step. The title now comes from
what the person typed: their one line, or the first words of a quick capture. Their own words, for them only.
"""

from __future__ import annotations

import uuid
from typing import Any

from core.crypto import encrypt_json
from tests.test_b6_review import _user, desk  # noqa: F401  (the fixture is reused)
from views import mine

LINE = "Courier slips are signed twice at the branch counter"
QUICK = "Every morning the branch team retypes the same courier slip into two registers before lunch"


def _unconfirmed(db: Any, code: str, raw: dict[str, Any], *, stage: str = "scanning") -> str:
    idea_uuid = str(uuid.uuid4())
    n = db.execute("SELECT next_number('IDEA', '2026') AS n").fetchone()["n"]
    db.execute(
        "INSERT INTO ideas (id, idea_id, submission_id, stage, capture_mode, contributor_code, raw_encrypted, "
        "submitted_at) VALUES (%s, %s, %s, %s, 'quick', %s, %s, now())",
        (
            idea_uuid,
            f"IDEA-2026-{int(n):06d}",
            f"SUB-2026-{int(n):06d}",
            stage,
            code,
            encrypt_json(raw, idea_uuid),
        ),
    )
    return idea_uuid


def _draft(db: Any, code: str, raw: dict[str, Any]) -> str:
    idea_uuid = str(uuid.uuid4())
    db.execute(
        "INSERT INTO ideas (id, contributor_code, stage, capture_mode, draft_encrypted, draft_expires_at) "
        "VALUES (%s, %s, 'draft', 'quick', %s, now() + interval '20 days')",
        (idea_uuid, code, encrypt_json(raw, idea_uuid)),
    )
    return idea_uuid


def _titles(db: Any, user_id: str) -> dict[str, str | None]:
    return {i["id"]: i["one_line"] for i in mine.my_ideas(db, user_id)["ideas"]}


def test_an_unconfirmed_idea_and_a_draft_show_the_persons_own_words(desk: Any) -> None:  # noqa: F811
    db = desk["db"]
    with_line = _unconfirmed(db, desk["code"], {"one_line": LINE, "details": QUICK})
    quick = _unconfirmed(db, desk["code"], {"one_line": "", "details": QUICK})
    draft = _draft(db, desk["code"], {"one_line": None, "details": "Short note"})
    empty = _draft(db, desk["code"], {"details": ""})

    titles = _titles(db, desk["owner"])
    assert titles[with_line] == LINE
    assert titles[quick] == " ".join(QUICK.split()[: mine.TITLE_WORDS]) + "…"
    assert titles[draft] == "Short note"
    assert titles[empty] is None  # the page falls back to "Your idea"


def test_a_confirmed_canvas_still_wins(desk: Any) -> None:  # noqa: F811
    db = desk["db"]
    shared = next(i for i in mine.my_ideas(db, desk["owner"])["ideas"] if i["idea_id"] == desk["idea_id"])
    assert shared["one_line"]  # restored from the confirmed canvas, as before


def test_nobody_else_sees_the_title(desk: Any) -> None:  # noqa: F811
    db = desk["db"]
    _unconfirmed(db, desk["code"], {"one_line": LINE, "details": QUICK})
    assert LINE not in str(mine.my_ideas(db, _user(db, None)))


def test_a_blob_that_does_not_open_gives_no_title() -> None:
    assert mine.own_title(b"not a sealed blob", str(uuid.uuid4())) is None
