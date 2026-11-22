"""L-HIDE.rules/7, BLD-C235, BLD-F097: the review desk's "Hide this" masks the value in the team-up texts others read
about the idea too: a team-up note on it, its lead's decline reason and a draft's ask to it (lane F's three texts,
lane C's sealed source `teamup`).

A customer's name the checks missed is in Ravi's message on his idea, twice in Kavya's team-up note (which Ravi
declines), in capitals in Ravi's reason, and in Asha's ask from her draft (which Ravi merges in, so a merge carries
the ask on). Nothing hides it when it is written: the gatekeeper is stood in for and finds nothing, and the name
alone matches no pattern. Meera at the review desk hides it on Ravi's message (lane C's `desk_hide`). Each team-up
text goes through lane F's public entry points (`requests.send`, `requests.answer`, `drafts.ask`), and its stored
copy is read the way lane F reads it. Synthetic people only (non-negotiable 11): the pack's fictional cast, and a
name made up at run time as lane F's tests make theirs. Everything made is removed afterwards except `audit_log`,
whose trigger refuses DELETE.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import string
import uuid
from collections.abc import Iterator
from typing import Any

import pytest

from core.db import Conn
from hide import desk_hide, detect
from hide.core import own_words, scope_for
from onepc.context import open_text, seal_text
from teamup import adapters, drafts, requests
from tests import f_teamup_fixtures as f
from tests import helpers

Calls = list[tuple[str, str]]
ROW_LOCK = re.compile(r"\bFOR\s+UPDATE\b|^\s*(UPDATE|DELETE)\b|\bDO\s+UPDATE\b", re.IGNORECASE)


@pytest.fixture
def db(db: Conn, monkeypatch: pytest.MonkeyPatch) -> Iterator[Conn]:
    """The shared `db` (every switch on) with the gatekeeper stood in for, finding nothing, and clean-up: the jobs,
    vault values and gateway calls this test's ideas made, then (through `f.clean`) its ideas and people."""
    from core import killswitch

    monkeypatch.setattr(detect, "gatekeeper_finds", lambda conn, text, scope: detect.Gate([]))
    killswitch.clear_cache()
    last_job = int(db.execute("SELECT coalesce(max(id), 0) AS n FROM jobs").fetchone()["n"])
    yield db
    scopes = [scope_for(i) for i in f._made["ideas"]]
    db.execute("DELETE FROM jobs WHERE id > %s", (last_job,))
    db.execute("DELETE FROM pseudonym_vault WHERE scope_id = ANY(%s)", (scopes,))
    db.execute("DELETE FROM vault_counters WHERE scope_id = ANY(%s)", (scopes,))
    db.execute("DELETE FROM llm_calls WHERE ref_id = ANY(%s)", (scopes,))
    f.clean(db)
    killswitch.clear_cache()


@pytest.fixture
def inbox(monkeypatch: pytest.MonkeyPatch) -> f.Inbox:
    return f.record_inbox(monkeypatch)


@pytest.fixture
def cast(db: Conn) -> dict[str, Any]:
    """Ravi leads the idea; Kavya asks to team up on it; Asha asks from a draft; Meera reviews."""
    ravi = f.person(db, "Ravi Nair")
    kavya = f.person(db, "Kavya Menon")
    asha = f.person(db, "Asha Sen", city="Pune", area="Operations")
    meera = f.person(db, "Meera Iyer", roles=("reviewer",))
    lead = f.idea(db, ravi, title="Rejection SMS codes confuse investors", shared_at=f.at(13, 9))
    return {"ravi": ravi, "kavya": kavya, "asha": asha, "meera": meera, "lead": lead}


@pytest.fixture
def name() -> str:
    """A customer's name made up for this test, which no pattern catches (lane F's and lane C's tests make theirs
    the same way)."""
    return "Kiran Ra" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(4))


def _stored(db: Conn, table: str, column: str, row_id: str) -> str | None:
    """The copy lane F stores for others, opened as lane F's reads open it."""
    row = db.execute(f"SELECT {column} FROM {table} WHERE id = %s", (row_id,)).fetchone()  # noqa: S608
    assert row is not None
    return open_text(table, column, row_id, row[column])


def _teamup_rows(db: Conn, idea_uuid: str) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in db.execute(
            "SELECT id, source_id, kind, found_by, state, span_start, span_end, vault_tag FROM hidden_details "
            "WHERE idea_uuid = %s AND source = 'teamup' ORDER BY source_id, span_start",
            (idea_uuid,),
        ).fetchall()
    ]


def _world(db: Conn, c: dict[str, Any], name: str) -> dict[str, str]:
    """Ravi's message on his idea, Kavya's note (the name twice) that Ravi declines with a reason (the name in
    capitals), and Asha's ask from her draft (the name once) that Ravi merges in. Nothing is hidden yet."""
    from hide import hide_message

    lead_uuid = str(c["lead"]["id"])
    text = f"Investors such as {name} call our branch because the SMS gives a code and not a reason."
    mid = str(uuid.uuid4())
    with db.transaction():
        out = hide_message(db, lead_uuid, text, by=c["ravi"]["id"], source_id=mid, gatekeeper=False)
        db.execute(
            "INSERT INTO idea_messages (id, idea_uuid, seq, via, text_encrypted, char_count) "
            "VALUES (%s, %s, 1, 'typed', %s, %s)",
            (mid, lead_uuid, seal_text("idea_messages", "text_encrypted", mid, out.masked), len(text)),
        )
    note = f"{name} rang our branch twice about the same SMS. Last week {name} asked us for a plain reason."
    rid = requests.send(db, c["lead"]["idea_id"], c["kavya"]["id"], {"note": note})["id"]
    reason = f"We are already talking to {name.upper()} about this one."
    requests.answer(db, rid, c["ravi"]["id"], {"answer": "decline", "reason": reason})
    draft = f.draft(db, c["asha"])
    ask = f"{name} wrote to our Pune desk about the same SMS and the code it gives."
    mrid = drafts.ask(db, str(draft["id"]), c["asha"]["id"], {"other_idea_id": c["lead"]["idea_id"], "note": ask})[
        "id"
    ]
    requests.answer(db, mrid, c["ravi"]["id"], {"answer": "merge"})
    merge = db.execute("SELECT id FROM merges WHERE merge_request_id = %s", (mrid,)).fetchone()
    assert merge is not None
    w = {
        "lead": lead_uuid, "draft": str(draft["id"]), "mid": mid, "text": text, "rid": rid, "note": note,
        "reason": reason, "mrid": mrid, "ask": ask, "merge": str(merge["id"]),
    }  # fmt: skip

    # nothing hidden yet: the other party reads the name in each text, and no team-up detail is kept
    assert name in requests.read(db, rid, c["ravi"]["id"])["note"]
    assert name.upper() in str(_stored(db, "teamup_requests", "lead_reason_encrypted", rid))
    assert name in str(_stored(db, "merge_requests", "note_encrypted", mrid))
    assert name in str(_stored(db, "merges", "note_encrypted", w["merge"]))
    assert _teamup_rows(db, lead_uuid) == [] and _teamup_rows(db, w["draft"]) == []
    return w


def _hide_this(db: Conn, c: dict[str, Any], w: dict[str, str], name: str) -> dict[str, Any]:
    """Meera's "Hide this" on the name in Ravi's message."""
    start = w["text"].index(name)
    return desk_hide(db, w["lead"], source_kind="message", source_id=w["mid"], start=start, end=start + len(name),
                     by=c["meera"]["id"])  # fmt: skip


def _copies(db: Conn, c: dict[str, Any], w: dict[str, str]) -> dict[str, str | None]:
    """Every copy of the three texts the other party reads, and the stored ones behind them."""
    return {
        "note_read": requests.read(db, w["rid"], c["ravi"]["id"])["note"],
        "note": _stored(db, "teamup_requests", "note_encrypted", w["rid"]),
        "reason_read": requests.read(db, w["rid"], c["kavya"]["id"])["lead_reason"],
        "reason": _stored(db, "teamup_requests", "lead_reason_encrypted", w["rid"]),
        "ask": _stored(db, "merge_requests", "note_encrypted", w["mrid"]),
        "merge": _stored(db, "merges", "note_encrypted", w["merge"]),
    }


# ---- every other-party copy masked; the typer's words kept -----------------------------------------------------


def test_l_hide_rules_7_bld_c235_bld_f097_the_desks_hide_masks_the_note_the_reason_and_the_ask(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, name: str
) -> None:
    """L-HIDE.rules/7: the name Meera hid on Ravi's message is masked in Kavya's note (both places) as Ravi reads it,
    in Ravi's reason as Kavya reads it, and in Asha's ask and the merge's copy of it; each stored copy is the one
    read. One `hidden_details` row per place, source `teamup`, under the idea the words are kept under (the note
    and the reason under Ravi's idea, the ask under Asha's draft), found by the reviewer. Each typer's sealed words
    are unchanged, and the idea page's hidden details and Ravi's S-06B still leave the team-up rows out."""
    from ideapage.read import hidden
    from submit import edit as submit_edit

    w = _world(db, cast, name)
    _hide_this(db, cast, w, name)

    copies = _copies(db, cast, w)
    for key, text in copies.items():
        assert text is not None and name.lower() not in text.lower(), key
    mask, caps = detect.mask("name", name), detect.mask("name", name.upper())
    assert str(copies["note_read"]).count(mask) == 2 and copies["note"] == copies["note_read"]
    assert caps in str(copies["reason_read"]) and copies["reason"] == copies["reason_read"]
    assert mask in str(copies["ask"]) and copies["merge"] == copies["ask"]
    assert str(copies["note"]).startswith(f"{mask} rang our branch twice")

    # one row per place, source `teamup`, under the idea the words are kept under
    rid, decline, ask_key = w["rid"], adapters.decline_id(w["rid"]), adapters.ask_id(w["mrid"])
    on_lead = _teamup_rows(db, w["lead"])
    assert [(r["source_id"], r["kind"], r["found_by"], r["state"]) for r in on_lead] == [
        (rid, "name", "reviewer", "hidden"),
        (rid, "name", "reviewer", "hidden"),
        (decline, "name", "reviewer", "hidden"),
    ]
    on_draft = _teamup_rows(db, w["draft"])
    assert [(r["source_id"], r["kind"], r["found_by"]) for r in on_draft] == [(ask_key, "name", "reviewer")]
    assert all(r["vault_tag"] for r in on_lead + on_draft)
    note_spans = [(r["span_start"], r["span_end"]) for r in on_lead if r["source_id"] == rid]
    assert [w["note"][s:e] for s, e in note_spans] == [name, name]

    # each typer's own words, unchanged; each still reads them back
    assert own_words(db, "teamup", rid, idea_uuid=w["lead"]) == w["note"]
    assert own_words(db, "teamup", decline, idea_uuid=w["lead"]) == w["reason"]
    assert own_words(db, "teamup", ask_key, idea_uuid=w["draft"]) == w["ask"]
    assert requests.read(db, rid, cast["kavya"]["id"])["note"] == w["note"]
    assert requests.read(db, rid, cast["ravi"]["id"])["lead_reason"] == w["reason"]

    # the idea's own lists still leave out the team-up rows (BLD-F097 (6))
    ids = {str(r["id"]) for r in on_lead}
    assert all(h["source"] != "teamup" for h in hidden(db, w["lead"]))
    assert not ids & {str(h["id"]) for h in hidden(db, w["lead"])}
    page = submit_edit.page(db, cast["lead"]["idea_id"], cast["ravi"]["id"], now=f.at(14, 12))
    assert not ids & {str(h["id"]) for h in page["hidden"]}

    # the desk's audit counts the three texts among the other copies
    after = db.execute(
        "SELECT after FROM audit_log WHERE action = 'hide.desk_hidden' AND entity = %s ORDER BY id DESC LIMIT 1",
        (f"idea:{w['lead']}",),
    ).fetchone()["after"]
    assert after["other_copies"] >= 3


def test_l_hide_rules_7_bld_c235_the_value_is_in_no_log_line_and_no_audit_row(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, name: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Non-negotiable 3: from the first team-up text to the desk's hide, no log line (its event or its fields) and no
    `audit_log` row carries the name, in any case; nor is it stored in clear anywhere."""
    caplog.set_level(logging.DEBUG)
    w = _world(db, cast, name)
    _hide_this(db, cast, w, name)

    assert caplog.records, "nothing was logged"
    for rec in caplog.records:
        line = rec.getMessage() + json.dumps(getattr(rec, "fields", {}), ensure_ascii=False, default=str)
        assert name.lower() not in line.lower(), rec.name
    hits = db.execute(
        "SELECT count(*) AS n FROM audit_log a WHERE strpos(lower(a::text), lower(%s)) > 0", (name,)
    ).fetchone()["n"]
    assert hits == 0
    assert helpers.tables_containing(db, name) == [] and helpers.tables_containing(db, name.upper()) == []
    assert db.execute(
        "SELECT count(*) AS n FROM audit_log WHERE action = 'hide.desk_hidden' AND entity = %s", (f"idea:{w['lead']}",)
    ).fetchone()["n"] == 1  # fmt: skip


def test_l_hide_rules_7_bld_c235_sweeping_twice_adds_no_row_and_keeps_the_masked_texts(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, name: str
) -> None:
    """The sweep run again for the same name (as a second hide of it, or the gatekeeper's re-check, would run it)
    finds every place covered: no new `hidden_details` row, no text written, the same masked copies."""
    from hide import core as hide_core
    from hide import desk as hide_desk

    w = _world(db, cast, name)
    _hide_this(db, cast, w, name)
    rows = (_teamup_rows(db, w["lead"]), _teamup_rows(db, w["draft"]))
    copies = _copies(db, cast, w)

    with db.transaction():
        hide_core.lock(db, w["lead"])
        again = hide_desk._sweep(db, w["lead"], name, "name")
    assert again.copies == 0 and again.rehidden == 0
    assert (_teamup_rows(db, w["lead"]), _teamup_rows(db, w["draft"])) == rows
    assert _copies(db, cast, w) == copies


# ---- BLD-C067's lock order: hide's lock first, then the rows ----------------------------------------------------


def _spy(db: Conn, monkeypatch: pytest.MonkeyPatch) -> Calls:
    """Every lock asked for on `db`, in order: ("hide", uuid) for each call of lane C's lock (`hide.core.lock`, and
    `hide.desk`'s own name for it, which `desk_hide` calls), ("row", sql) for each statement that locks rows
    (FOR UPDATE, UPDATE, DELETE, an upsert), and ("write", source_id) for each call of lane F's `write_masked`."""
    import hide.core
    from hide import desk as hide_desk

    calls: Calls = []
    real_lock, real_execute, real_write = hide.core.lock, db.execute, adapters.write_masked

    def hide_lock(conn: Conn, idea_uuid: str) -> None:
        calls.append(("hide", str(idea_uuid)))
        real_lock(conn, idea_uuid)

    def execute(query: Any, params: Any = None, **kw: Any) -> Any:
        text = query if isinstance(query, str) else str(query)
        if ROW_LOCK.search(text):
            calls.append(("row", " ".join(text.split())[:80]))
        return real_execute(query, params, **kw)

    def write_masked(conn: Conn, source_id: str, masked: str) -> int:
        calls.append(("write", str(source_id)))
        return real_write(conn, source_id, masked)

    monkeypatch.setattr(hide.core, "lock", hide_lock)
    monkeypatch.setattr(hide_desk, "lock", hide_lock)
    monkeypatch.setattr(db, "execute", execute)
    monkeypatch.setattr(adapters, "write_masked", write_masked)
    return calls


def test_l_hide_bld_c067_bld_c235_hides_lock_comes_before_the_first_row_lock(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLD-C067, BLD-B247: `desk_hide` takes hide's lock on Ravi's idea first, before its first row lock, and lane
    F's writer updates the team-up rows under it, later. It asks for no other idea's lock (not the draft's, whose
    ask it masks): taking one after a row lock would break the one order every caller keeps."""
    w = _world(db, cast, name)
    calls = _spy(db, monkeypatch)
    _hide_this(db, cast, w, name)

    assert calls[0] == ("hide", w["lead"]), calls[:3]
    assert {c for c in calls if c[0] == "hide"} == {("hide", w["lead"])}
    rows = [i for i, c in enumerate(calls) if c[0] == "row"]
    writes = [i for i, c in enumerate(calls) if c[0] == "write"]
    assert rows and writes and rows[0] > 0 and writes[0] > rows[0]
    assert {calls[i][1] for i in writes} == {
        w["rid"],
        adapters.decline_id(w["rid"]),
        adapters.ask_id(w["mrid"]),
    }
