"""DEC-127, L-REVIEW, S-R2, BLD-B247 (lane B's desk reads, carried by lane C's BLD-C222 with lane B's OK): the review
desk's hidden and shown details (`desk.reads._hidden`, `_shown`) never include a file not yet sent. That's an unsent
conversation file (DEC-127 (2): it is its uploader's alone) or an unsent answer's file (BLD-B247: an answer is the
sharer's until sent), and each file's name details (`<id>:name`) as well as its own. Once the file is on a
conversation entry, or its answer is sent, its details are listed as before. Synthetic people and values only."""

from __future__ import annotations

import uuid
from typing import Any

from psycopg.types.json import Jsonb

from attachments import files as F
from core.db import Conn
from desk import reads
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes the people and ideas)


def _file(
    db: Conn, idea: dict[str, Any], by: dict[str, str], *, purpose: str, answer: str | None = None
) -> str:
    """An attachments row as the routes leave a checked file, written directly."""
    att = F._next_id(db)
    db.execute(
        "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, uploaded_by_user, name, mime, bytes, store_key, "
        "state, kind, file_state, checks, purpose, answer_id) "
        "VALUES (%s, %s, %s, %s, 'notes.pdf', 'application/pdf', 1200, %s, 'clean', 'file', 'checked', %s, %s, %s)",
        (att, idea["id"], by["code"], by["id"], f"files/{att}-{uuid.uuid4().hex}", Jsonb({"type": "pdf"}), purpose,
         answer),
    )  # fmt: skip
    return att


def _detail(
    db: Conn, idea: dict[str, Any], source_id: str, kind: str, masked: str, by: dict[str, str]
) -> None:
    """One hidden and one shown detail on `source_id` (the file's id, or `<id>:name`), as hide leaves them."""
    db.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked) VALUES (%s, 'file', %s, %s, %s)",
        (idea["id"], source_id, kind, f"{masked} hidden"),
    )
    db.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked, state, reason, shown_by, shown_at) "
        "VALUES (%s, 'file', %s, %s, %s, 'shown', 'internal_reference', %s, now())",
        (idea["id"], source_id, kind, f"{masked} shown", by["id"]),
    )


def _answer(db: Conn, idea: dict[str, Any], desk: dict[str, str], sharer: dict[str, str]) -> str:
    """A question the desk sent on the idea and the sharer's answer to it, not sent yet."""
    s = db.execute(
        "INSERT INTO question_sets (idea_uuid, by_user_id, state, time_to_answer, sent_at, due_at) "
        "VALUES (%s, %s, 'sent', '3d', now(), now() + interval '3 days') RETURNING id",
        (idea["id"], desk["id"]),
    ).fetchone()
    assert s is not None
    q = db.execute(
        "INSERT INTO questions (set_id, seq, part, text_encrypted) VALUES (%s, 1, 'evidence', %s) RETURNING id",
        (s["id"], b"synthetic"),
    ).fetchone()
    assert q is not None
    a = db.execute(
        "INSERT INTO answers (question_id, by_code) VALUES (%s, %s) RETURNING id", (q["id"], sharer["code"])
    ).fetchone()
    assert a is not None
    return str(a["id"])


def _lists(db: Conn, idea: dict[str, Any]) -> tuple[set[str], set[str]]:
    """The masked lines `_hidden` gives, and the kinds `_shown` gives (`_shown` carries no masked text)."""
    hidden = {str(m) for _, m in reads._hidden(db, idea["id"])}
    shown = {str(s["kind"]) for s in reads._shown(db, idea["id"])}
    return hidden, shown


def test_DEC_127_L_REVIEW_S_R2_BLD_B247_the_desk_lists_no_detail_of_a_file_not_yet_sent_and_lists_it_once_sent(
    db: Conn,
) -> None:
    kavya = f.person(db, "Kavya Menon")
    meera = f.person(db, "Meera Iyer", roles=("reviewer",))
    idea = f.idea(db, kavya)
    # (a) an idea file: listed.
    own = _file(db, idea, kavya, purpose="idea")
    _detail(db, idea, own, "folio", "Folio ••••01", kavya)
    # (b) an unsent conversation file, its own detail and its name's: in neither list.
    unsent = _file(db, idea, meera, purpose="conversation")
    _detail(db, idea, unsent, "pan", "PAN ••••02", kavya)
    _detail(db, idea, f"{unsent}:name", "name", "Name ••••03", kavya)
    # (d) an unsent answer's file, its own detail and its name's: in neither list.
    answer = _answer(db, idea, meera, kavya)
    ans = _file(db, idea, kavya, purpose="idea", answer=answer)
    _detail(db, idea, ans, "phone", "Phone ••••04", kavya)
    _detail(db, idea, f"{ans}:name", "email", "Email ••••05", kavya)

    hidden, shown = _lists(db, idea)
    assert hidden == {"Folio ••••01 hidden"}
    assert shown == {"folio"}

    # (c) the same conversation file once it is on an entry: listed, its name's details too.
    entry = db.execute(
        "INSERT INTO conversation_entries (idea_uuid, type, author_code) VALUES (%s, 'message', %s) RETURNING id",
        (idea["id"], meera["code"]),
    ).fetchone()
    assert entry is not None
    db.execute("UPDATE attachments SET conversation_entry_id = %s WHERE id = %s", (entry["id"], unsent))
    hidden, shown = _lists(db, idea)
    assert hidden == {"Folio ••••01 hidden", "PAN ••••02 hidden", "Name ••••03 hidden"}
    assert shown == {"folio", "pan", "name"}

    # (d) once the answer is sent, its file's details are listed, its name's too.
    db.execute("UPDATE answers SET sent_at = now() WHERE id = %s", (answer,))
    hidden, shown = _lists(db, idea)
    assert hidden == {
        "Folio ••••01 hidden", "PAN ••••02 hidden", "Name ••••03 hidden", "Phone ••••04 hidden", "Email ••••05 hidden",
    }  # fmt: skip
    assert shown == {"folio", "pan", "name", "phone", "email"}
