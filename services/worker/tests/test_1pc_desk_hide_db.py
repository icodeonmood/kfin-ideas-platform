"""L-HIDE on the review side (BLD-B246): the desk reads why a detail was shown (L-HIDE.rules/6, S-R2), the desk's own
words are masked through lane C's `hide.hide_text` with who wrote them, and a sharer's answer keeps its details'
ids across autosaves. Synthetic people and values only (non-negotiable 11); every row made is removed at the end
(`clean_up_desk_rows`; hidden_details and the sealed words go with the idea)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import adapters, asking, reads
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

NOW = f.at(16, 13, 20)


def cast_conn(value: object) -> Conn:
    """A stand-in connection for a call that never reaches the database."""
    return value  # type: ignore[return-value]


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
    asha = f.person(db, "Asha Kulkarni", roles=("committee",))
    arjun = f.person(db, "Arjun Rao")  # no desk or committee role
    return {"kavya": kavya, "meera": meera, "asha": asha, "arjun": arjun, "idea": f.idea(db, kavya)}


def _detail(db: Conn, idea_uuid: str, *, kind: str, masked: str, tag: str, state: str = "hidden",
            reason: str | None = None, by: str | None = None, at: Any = None, source_id: str = "m-1") -> None:  # fmt: skip
    db.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked, vault_tag, state, reason, shown_by, "
        "shown_at, created_at) VALUES (%s, 'message', %s, %s, %s, %s, %s, %s, %s, %s, coalesce(%s, now()))",
        (idea_uuid, source_id, kind, masked, tag, state, reason, by, at, at),
    )


def test_L_HIDE_rules_6_S_R2_the_desk_reads_what_was_shown_and_why_one_line_per_value(
    db: Conn, cast: dict[str, Any]
) -> None:
    idea, kavya = cast["idea"], cast["kavya"]
    # the folio shown in two copies (one value, one vault tag), a PAN shown once, a phone number still hidden
    _detail(db, idea["id"], kind="folio", masked="Folio ••••89", tag="[[FOLIO_NUMBER_1]]", state="shown",
            reason="internal_reference", by=kavya["id"], at=f.at(14, 10, 0))  # fmt: skip
    _detail(db, idea["id"], kind="folio", masked="Folio ••••89", tag="[[FOLIO_NUMBER_1]]", state="shown",
            reason="internal_reference", by=kavya["id"], at=f.at(14, 10, 5), source_id="m-2")  # fmt: skip
    _detail(db, idea["id"], kind="pan", masked="PAN ••••4F", tag="[[PAN_1]]", state="shown",
            reason="made_up_example", by=kavya["id"], at=f.at(14, 11, 0))  # fmt: skip
    _detail(db, idea["id"], kind="phone", masked="Phone ••••10", tag="[[PHONE_1]]")
    _detail(db, idea["id"], kind="phone", masked="Phone ••••10", tag="[[PHONE_1]]", source_id="m-2")

    for reader in ("meera", "asha"):  # the review desk and the Ones Committee
        got = reads.reviewer_idea(db, idea["idea_id"], cast[reader]["id"], NOW)
        assert [s["line"] for s in got["shown"]] == [
            "Folio shown, because it’s an internal reference.",
            "PAN shown, because it’s made up for the example.",
        ]
        first = got["shown"][0]
        assert (first["kind"], first["reason"], first["because"], first["by"]) == (
            "folio", "internal_reference", "it’s an internal reference", "Kavya",
        )  # fmt: skip
        assert first["at"].startswith("2026-11-14T04:35")  # the later of the two showings, 10:05 am IST
        # the hidden line stays hidden-only, one per value: "Phone ••••10 is hidden from everyone."
        evidence = next(p for p in got["parts"] if p["part"] == "evidence")
        assert evidence["text"] == "Phone ••••10 is hidden from everyone."
        assert "Folio" not in evidence["text"] and "PAN" not in evidence["text"]

    # anyone else reads no reasons (the route refuses them first; the read itself gives nothing either)
    assert reads.reviewer_idea(db, idea["idea_id"], cast["arjun"]["id"], NOW)["shown"] == []


def test_L_HIDE_rules_6_S_R2_nothing_shown_reads_an_empty_list(db: Conn, cast: dict[str, Any]) -> None:
    got = reads.reviewer_idea(db, cast["idea"]["idea_id"], cast["meera"]["id"], NOW)
    assert got["shown"] == []


def test_L_HIDE_rules_7_S_R2_messages_and_answers_carry_their_ids_for_hide_this(
    db: Conn, cast: dict[str, Any]
) -> None:
    from desk.store import seal

    msg = db.execute(
        "INSERT INTO idea_messages (idea_uuid, seq, via, text_encrypted, created_at) VALUES (%s, 1, 'typed', %s, %s) "
        "RETURNING id",
        (cast["idea"]["id"], b"x", f.at(14, 9, 50)),
    ).fetchone()
    assert msg is not None
    db.execute(
        "UPDATE idea_messages SET text_encrypted = %s WHERE id = %s",
        (seal("Investors keep calling.", "idea_messages", "text_encrypted", str(msg["id"])), msg["id"]),
    )
    got = reads.reviewer_idea(db, cast["idea"]["idea_id"], cast["meera"]["id"], NOW)
    assert got["own_words"][0]["id"] == str(msg["id"])


def test_L_HIDE_adapters_hide_calls_lane_C_hide_text_with_who_wrote_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Any, ...]] = []

    def spy(conn: Any, idea_uuid: str, text: str, **kw: Any) -> tuple[str, int]:
        calls.append((conn, idea_uuid, text, kw))
        return "masked", 1

    monkeypatch.setattr(adapters, "hide_text", spy)
    conn = cast_conn("conn")
    assert adapters.hide(conn, "idea-1", "words", by="user-1") == ("masked", 1)
    assert adapters.hide(conn, "idea-1", "words", by="user-2", source="answer", source_id="a-1") == (
        "masked",
        1,
    )
    assert calls == [
        ("conn", "idea-1", "words", {"by": "user-1", "source": "desk", "source_id": None}),
        ("conn", "idea-1", "words", {"by": "user-2", "source": "answer", "source_id": "a-1"}),
    ]


def test_L_HIDE_adapters_hide_the_desks_words_are_masked_and_stored_under_the_idea(
    db: Conn, cast: dict[str, Any]
) -> None:
    idea, meera = cast["idea"], cast["meera"]
    with db.transaction():
        masked, n = adapters.hide(
            db, str(idea["id"]), "Did the investor on 9876543210 call twice?", by=meera["id"]
        )
    assert n == 1 and "9876543210" not in masked and "••••10" in masked
    rows = db.execute(
        "SELECT source, kind, state FROM hidden_details WHERE idea_uuid = %s", (idea["id"],)
    ).fetchall()
    assert [(r["source"], r["kind"], r["state"]) for r in rows] == [("desk", "phone", "hidden")]


def test_L_HIDE_rules_4_L_QUESTIONS_answer_6_an_answer_keeps_its_details_across_autosaves(
    db: Conn, cast: dict[str, Any]
) -> None:
    sent = asking.send_set(
        db, cast["idea"]["idea_id"], cast["meera"]["id"],
        {"questions": [{"part": "summary", "text": "Is it mostly R07?"}], "time_to_answer": "3d"}, f.at(16, 11, 20),
    )  # fmt: skip
    qid, kavya = sent["questions"][0]["id"], cast["kavya"]["id"]
    text = "Mostly R07. Folio 1234567890 got it twice last week."
    first = asking.save_answer(db, qid, kavya, text, at=f.at(16, 12, 10))
    again = asking.save_answer(db, qid, kavya, text + " And once more today.", at=f.at(16, 12, 12))
    assert first["id"] == again["id"] and "1234567890" not in again["text"]
    rows = db.execute(
        "SELECT id, source, source_id FROM hidden_details WHERE idea_uuid = %s", (cast["idea"]["id"],)
    ).fetchall()
    assert len(rows) == 1  # the same detail, not one per autosave
    assert (rows[0]["source"], rows[0]["source_id"]) == ("answer", first["id"])
    # the sharer's own words are kept sealed for them alone, under the answer's id
    from hide import core

    assert core.own_words(db, "answer", first["id"], idea_uuid=str(cast["idea"]["id"])) == text + (
        " And once more today."
    )
    # an emptied box hides nothing any more
    asking.save_answer(db, qid, kavya, "", at=f.at(16, 12, 14))
    left = db.execute(
        "SELECT count(*) AS n FROM hidden_details WHERE idea_uuid = %s", (cast["idea"]["id"],)
    ).fetchone()
    assert left is not None and left["n"] == 0
