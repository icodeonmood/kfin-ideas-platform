"""S-R2 read from the database: the heading, artefacts, parts with questions and answers, worth, similar ideas,
the panel's working state, and the listen script (V-ACC.review/1, /8, /14; L-REVIEW.open/2–3; L-LISTEN/2)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import decide, reads
from desk.store import seal
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

NOW = f.at(16, 13, 20)


@pytest.fixture
def repo(company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    get_settings.cache_clear()
    yield company_repo
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def page(db: Conn, repo: Path) -> dict[str, Any]:
    kavya, ravi = f.person(db, "Kavya Menon"), f.person(db, "Ravi Nair")
    meera = f.person(db, "Meera Iyer", roles=("reviewer",))
    idea = f.idea(db, kavya, brings=["saves_time", "saves_cost"], affects=["Investors", "KFin teams"],
                  sorting_confirmed_at=f.at(14, 10, 5), kept_separate=True)  # fmt: skip
    other = f.idea(db, ravi, title="Rejection SMS codes confuse investors", shared_at=f.at(2, 15))
    msg = db.execute(
        "INSERT INTO idea_messages (idea_uuid, seq, via, text_encrypted, created_at) VALUES (%s, 1, 'typed', %s, %s) "
        "RETURNING id",
        (idea["id"], b"x", f.at(14, 9, 50)),  # Saturday, before the draft
    ).fetchone()
    assert msg is not None
    db.execute("UPDATE idea_messages SET text_encrypted = %s WHERE id = %s",
               (seal("Investors keep calling about folio Folio ••••89 and the R07 code.", "idea_messages",
                     "text_encrypted", str(msg["id"])), msg["id"]))  # fmt: skip
    db.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked) VALUES (%s, 'message', %s, 'folio', "
        "'Folio ••••89')",
        (idea["id"], str(msg["id"])),
    )
    db.execute(
        "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, name, bytes, store_key, kind, file_state, pages, "
        "hidden_note) VALUES ('ATT-2026-000001', %s, %s, 'branch-call-log-nov.pdf', 143360, 'k', 'file', "
        "'hidden_checked', 3, 'A phone number on page 2 is hidden.')",
        (idea["id"], kavya["code"]),
    )
    db.execute(
        "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason) VALUES (%s, %s, 'close', "
        "'Same R07 SMS in Hyderabad')",
        (idea["id"], other["id"]),
    )
    return {"kavya": kavya, "meera": meera, "idea": idea, "other": other}


def test_V_ACC_review_1_the_page_opens_on_reviewing(db: Conn, page: dict[str, Any]) -> None:
    got = reads.reviewer_idea(db, page["idea"]["idea_id"], page["meera"]["id"], NOW)
    assert got["panel"]["state"] == "reviewing" and got["can_act"] is True and got["own"] is False
    assert got["idea"]["heading"] == (
        "Shared Saturday 14 November by Kavya Menon, Investor service, Hyderabad. Sorting confirmed by Kavya: "
        "a problem to fix, Investor service, saves time and cost."
    )
    import datetime as dt

    assert dt.datetime.fromisoformat(got["decide_by"]["at"]) == f.at(20, 18)
    assert (got["decide_by"]["label"], got["decide_by"]["left"]) == ("Friday 20 November", "4 days to decide")


def test_S_R2_left_2_artefacts(db: Conn, page: dict[str, Any]) -> None:
    arts = {
        a["kind"]: a
        for a in reads.reviewer_idea(db, page["idea"]["idea_id"], page["meera"]["id"], NOW)["artefacts"]
    }
    assert arts["file"]["line"] == "Attached by Kavya. 140 KB, 3 pages. A phone number on page 2 is hidden."
    assert arts["own_words"]["title"] == "Kavya’s own words"
    assert arts["own_words"]["line"] == "As Kavya wrote them on Saturday, before the draft. Folio hidden."
    assert arts["similar_found"]["line"] == "1 found while Kavya wrote. Kavya kept it separate."
    assert "versions" not in arts  # never changed since it was shared: no Draft history


def test_S_R2_left_3_E_ENTITIES_draft_history_counts_the_shared_version_as_one(
    db: Conn, page: dict[str, Any]
) -> None:
    idea = page["idea"]
    db.execute(  # lane C's row for the version as shared, with nothing changed, then two edits
        "INSERT INTO idea_versions (idea_uuid, n, changed_fields) VALUES (%s, 1, '{}'), (%s, 2, '{title}'), "
        "(%s, 3, '{sorting}')",
        (idea["id"], idea["id"], idea["id"]),
    )
    arts = {
        a["kind"]: a for a in reads.reviewer_idea(db, idea["idea_id"], page["meera"]["id"], NOW)["artefacts"]
    }
    assert arts["versions"]["line"] == "3 versions. Title changed once, sorting confirmed."
    db.execute("DELETE FROM idea_versions WHERE idea_uuid = %s AND n = 1", (idea["id"],))  # no row for it
    again = reads.reviewer_idea(db, idea["idea_id"], page["meera"]["id"], NOW)["artefacts"]
    assert next(a for a in again if a["kind"] == "versions")["line"] == (
        "3 versions. Title changed once, sorting confirmed."
    )


def test_L_REVIEW_open_3_reviewers_read_the_masked_words(db: Conn, page: dict[str, Any]) -> None:
    got = reads.reviewer_idea(db, page["idea"]["idea_id"], page["meera"]["id"], NOW)
    assert got["own_words"][0]["text"].count("••••89") == 1


def test_S_R2_left_3_and_5_parts_and_similar_ideas(db: Conn, page: dict[str, Any]) -> None:
    got = reads.reviewer_idea(db, page["idea"]["idea_id"], page["meera"]["id"], NOW)
    assert [p["name"] for p in got["parts"]] == [
        "The problem", "How often", "Who it affects", "What it’s worth", "Attached", "Fix"
    ]  # fmt: skip
    assert got["parts"][2]["text"] == "Investors, KFin teams."  # with its full stop, as on the DeskIdea board
    sim = got["similar"][0]
    assert sim["meta"] == f"{page['other']['idea_id']}, Ravi Nair, Investor service, Hyderabad. 1 on its crew"
    assert sim["merged"] is False


def test_V_ACC_review_14_own_idea_is_read_only(db: Conn, page: dict[str, Any]) -> None:
    got = reads.reviewer_idea(db, page["idea"]["idea_id"], page["kavya"]["id"], NOW)
    assert got["own"] is True and got["can_act"] is False


def test_S_R2_panel_6_decided(db: Conn, page: dict[str, Any]) -> None:
    decide.send(db, page["idea"]["idea_id"], page["meera"]["id"],
                {"choice": "pick", "reason": "A clear problem, a real number and a simple fix."}, f.at(16, 16, 58))  # fmt: skip
    got = reads.reviewer_idea(db, page["idea"]["idea_id"], page["meera"]["id"], f.at(16, 17))
    assert got["panel"]["state"] == "decided" and got["panel"]["decision"]["window"]["left"] == "30 days left"
    assert got["can_act"] is False


def test_L_LISTEN_2_the_script_reads_the_masked_idea(db: Conn, page: dict[str, Any]) -> None:
    s = reads.listen_script(db, page["idea"]["idea_id"], page["meera"]["id"])
    parts = {p["part"]: p["text"] for p in s["parts"]}
    assert parts["who"] == "Investors, KFin teams."
    assert parts["evidence"].startswith("One file:") and "hidden" in parts["evidence"]
    assert parts["fix"] == "No fix suggested. It was optional."
