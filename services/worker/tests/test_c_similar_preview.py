"""A-API.idea-preview, C-PREVIEW, L-SIMILAR.rules/10 (BLD-C090) on the 1% Club seed: what a colleague, the sharer and
the review desk see of a shared idea. Masked text only, never the sharer's raw words (DEC-104, non-negotiable 7);
names unless hidden from the Wall; `compare` for the desk and the Ones Committee alone."""

from __future__ import annotations

import json
from typing import Any

import pytest

from bootstrap import club_seed
from similar.preview import HIDDEN_NAME, SUMMARY_PENDING, Viewer, idea_preview


def _user(conn: Any, first: str) -> str:
    row = conn.execute("SELECT id FROM users WHERE name LIKE %s", (first + " %",)).fetchone()
    return str(row["id"])


@pytest.fixture
def seeded(db: Any) -> dict[str, Any]:
    return club_seed.load(db)


def test_bld_c090_a_colleague_sees_the_public_preview(db: Any, seeded: dict[str, Any]) -> None:
    t7 = seeded["T7"]  # Tanvi's picked fix; Gopal leads its build, the crew has joined
    me = Viewer.of(db, _user(db, "Pallavi"))
    out = idea_preview(db, t7.ref, viewer=me)
    assert out is not None
    assert out["id"] == t7.ref and out["status"] == "picked"
    assert out["title"] == "Plain words for transaction rejection codes"
    assert out["area"] == "Investor service" and out["city"] == "Hyderabad"
    assert out["shared_at"].endswith("Z")
    assert out["in_their_words"] in (
        "Rejection letters show codes like R07 that investors cannot read.",
        SUMMARY_PENDING,
    )
    assert out["lead"]["name"] and out["lead"]["initials"]
    assert out["crew_count"] >= 1 and 1 <= len(out["crew_faces"]) <= 3
    assert out["crew_faces"][0] == out["lead"]
    assert out["hue"] in (1, 2)
    assert "compare" not in out and "compare_with" not in out  # reviewers only
    # The same idea by its row ID.
    assert idea_preview(db, t7.uuid, viewer=me) == out


def test_bld_c090_never_raw_words_or_hidden_values(db: Any, seeded: dict[str, Any]) -> None:
    me = Viewer.of(db, _user(db, "Pallavi"))
    for key in ("T5", "T6", "T7", "R1"):
        made = seeded[key]
        text = json.dumps(idea_preview(db, made.ref, viewer=me), ensure_ascii=False)
        for words in made.spec.words:  # the sharer's own words never reach anyone else
            assert words.split("{")[0][:60] not in text
        for _kind, value in made.spec.hidden.values():
            assert value not in text
    # A detail typed into the summary is masked before anyone sees it.
    t5 = seeded["T5"]
    db.execute(
        "UPDATE ideas SET summary = 'An investor with folio 7700012389 waits at the branch. More here.' WHERE id = %s",
        (t5.uuid,),
    )
    out = idea_preview(db, t5.ref, viewer=me)
    assert "7700012389" not in json.dumps(out)
    assert out["in_their_words"] in ("An investor with folio ••••89 waits at the branch.", SUMMARY_PENDING)


def test_bld_c090_names_show_unless_hidden_from_the_wall(db: Any, seeded: dict[str, Any]) -> None:
    c1 = seeded["C1"]  # Charulata hides her name on the Wall
    colleague = idea_preview(db, c1.ref, viewer=Viewer.of(db, _user(db, "Pallavi")))
    assert colleague["lead"]["name"] == HIDDEN_NAME and colleague["lead"]["initials"] == ""
    assert "Charulata" not in json.dumps(colleague)
    desk = idea_preview(db, c1.ref, viewer=Viewer.of(db, _user(db, "Harish")))
    assert desk["lead"]["name"] == "Charulata Sen" and desk["lead"]["initials"] == "CS"


def test_bld_c090_compare_for_the_desk_and_committee_only(db: Any, seeded: dict[str, Any]) -> None:
    t7, r1 = seeded["T7"], seeded["R1"]
    for first in ("Harish", "Manoj"):  # review desk, Ones Committee
        out = idea_preview(db, t7.ref, viewer=Viewer.of(db, _user(db, first)), compare_with=r1.ref)
        assert out["compare"]["often"] == "About 40 calls a day across branches"
        assert out["compare"]["who"] == "Investors"
        # the reviewer's revision is the latest figure (L-WORTH/3)
        assert out["compare"]["worth"] == "Saves 150 to 220 hours a month and ₹40,000 to ₹60,000 a month"
        assert out["compare_with"]["id"] == r1.ref
        assert out["compare_with"]["owner"]["first_name"] == "Rekha"
        assert set(out["compare_with"]) >= {"id", "title", "owner", "worth"}
    for first in ("Pallavi", "Kunal", "Tanvi"):  # a colleague, an admin, the sharer herself
        plain = idea_preview(db, t7.ref, viewer=Viewer.of(db, _user(db, first)), compare_with=r1.ref)
        assert plain is not None and "compare" not in plain and "compare_with" not in plain


def test_bld_c090_drafts_and_withdrawn_ideas(db: Any, seeded: dict[str, Any]) -> None:
    colleague = Viewer.of(db, _user(db, "Pallavi"))
    assert idea_preview(db, seeded["T2"].uuid, viewer=colleague) is None  # a draft is nobody else's to see
    assert idea_preview(db, "IDEA-2099-000001", viewer=colleague) is None
    assert idea_preview(db, "not-an-id", viewer=colleague) is None
    t10 = seeded["T10"]  # withdrawn
    assert idea_preview(db, t10.ref, viewer=colleague) is None
    assert idea_preview(db, t10.ref, viewer=Viewer.of(db, _user(db, "Tanvi"))) is not None
    assert idea_preview(db, t10.ref, viewer=Viewer.of(db, _user(db, "Harish"))) is not None
    assert idea_preview(db, seeded["T7"].ref, viewer=Viewer.of(db, None)) is not None  # public fields only
