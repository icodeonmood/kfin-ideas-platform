"""BLD-B284 (DEC-144 (1) and (3); S-R2.left/2, S-R2.left/3, L-MERGE.effects/3): the review desk shows a green "Checked
for personal details" badge on every file it lists once both checks have passed. S-R2's read marks each listed file
`checked` through lane C's `attachments.files.gatekeeper_ran` (DEC-127): a 1% Club file is listed only checked or
found, so always; a file from the old pipeline (no `file_state`) only when its personal-data check ran
(`checks.gatekeeper` true), never on the patterns alone. Which files the desk lists does not change: never one still
being checked. Synthetic people and files only (non-negotiable 11). A database test: it runs in CI only (BLD-A251)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from psycopg.types.json import Jsonb

from core.db import Conn
from desk import asking, reads
from tests import convo_fixtures as fx
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

NOW = f.at(16, 15)  # Monday 16 November 2026, 3 pm IST


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


def _file(
    db: Conn, cast: dict[str, Any], name: str, file_state: str | None, gatekeeper: bool | None = None
) -> str:
    """One of the idea's own files. `file_state` None is a row from the old pipeline, clean, with its
    `checks.gatekeeper` as given."""
    att = fx.attachment(
        db, cast["idea"], cast["kavya"], file_state=file_state or "checked", name=name, purpose="idea"
    )
    if file_state is None:
        db.execute(
            "UPDATE attachments SET file_state = NULL, checks = %s WHERE id = %s",
            (Jsonb({"type": "xlsx", "gatekeeper": gatekeeper}), att),
        )
    return att


def test_BLD_B284_DEC_144_1_every_file_the_desk_lists_is_marked_checked_once_both_checks_passed(
    db: Conn, cast: dict[str, Any]
) -> None:
    """S-R2.left/2: checked, hidden and found files carry the badge; an old clean file only when its gatekeeper ran;
    a file still being checked is not listed at all, as before."""
    _file(db, cast, "new-checked.xlsx", "checked")
    _file(db, cast, "new-hidden.xlsx", "hidden_checked")
    _file(db, cast, "new-found.xlsx", "personal_data_found")
    _file(db, cast, "new-checking.xlsx", "checking")
    _file(db, cast, "old-gatekeeper.xlsx", None, gatekeeper=True)
    _file(db, cast, "old-patterns-only.xlsx", None, gatekeeper=False)
    page = reads.reviewer_idea(db, cast["idea"]["idea_id"], cast["meera"]["id"], NOW)
    rows = [
        (a["title"], a["checked"], a["customer_detail"]) for a in page["artefacts"] if a["kind"] == "file"
    ]
    assert rows == [
        ("new-checked.xlsx", True, False),
        ("new-hidden.xlsx", True, False),
        ("new-found.xlsx", True, True),  # DEC-107: checked, and holds a customer detail
        ("old-gatekeeper.xlsx", True, False),
        ("old-patterns-only.xlsx", False, False),  # DEC-127: never claimed on the patterns alone
    ]


def test_BLD_B284_S_R2_left_3_a_file_sent_with_an_answer_is_marked_the_same_way(
    db: Conn, cast: dict[str, Any]
) -> None:
    idea, kavya = cast["idea"], cast["kavya"]
    sent = asking.send_set(
        db, idea["idea_id"], cast["meera"]["id"],
        {"questions": [{"part": "evidence", "text": "Can you add the November returns count for branch R07?"}],
         "time_to_answer": "3d"},
        f.at(16, 9),
    )  # fmt: skip
    new = _file(db, cast, "returns-R07.xlsx", "checked")
    old = _file(db, cast, "returns-R08.xlsx", None, gatekeeper=False)
    asking.save_answer(
        db, sent["questions"][0]["id"], kavya["id"], "Here they are.", [new, old], f.at(16, 10)
    )
    assert asking.send_answers(db, sent["id"], kavya["id"], f.at(16, 13))["sent"] == 1
    page = reads.reviewer_idea(db, idea["idea_id"], cast["meera"]["id"], NOW)
    answer = next(p for p in page["parts"] if p["part"] == "evidence")["questions"][0]["answer"]
    assert [(x["name"], x["checked"]) for x in answer["files"]] == [
        ("returns-R07.xlsx", True),
        ("returns-R08.xlsx", False),
    ]
