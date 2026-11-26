"""BLD-F097, L-HIDE, L-TEAMUP, L-MERGE.request, DEC-103, DEC-104, BLD-B247: the three team-up texts go through lane C's
hide (`hide.hide_text`: the patterns, then the gatekeeper, then names) as the sealed source `teamup`, with lane C's
lock taken first, before anyone else sees them: the team-up note, the lead's decline reason and a draft's ask.

Each text is shown to the other side, stored, and sent onward (the Inbox notice, `merges.note_encrypted` after a
merge) as the masked copy only; the person who typed it reads their own words back through lane C's `own_words`.
A customer's name only the gatekeeper finds is made up for each test and found by a stand-in for
`hide.detect.gatekeeper_finds`, the way lane C's own tests stand in for it; folio, PAN and phone are made up too and
caught by the shared patterns. Synthetic people only (non-negotiable 11): the pack's fictional cast. Everything made
is removed afterwards except `audit_log`, whose trigger refuses DELETE.
"""

from __future__ import annotations

import re
import secrets
import string
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

from core.db import Conn
from hide import detect
from hide import recheck as hide_recheck
from hide.core import own_words, scope_for
from onepc.context import open_text
from teamup import adapters, drafts, requests
from tests import f_teamup_fixtures as f
from tests import helpers

MIGRATION = (
    Path(__file__).resolve().parents[3] / "db" / "migrations" / "20261122301100_hide_teamup_source.sql"
)
NOTE = "I take these calls at our Hyderabad branch every day, about 40 a day, and most are about R07."
HIDDEN_SOURCES = frozenset(
    {
        "message",
        "answer",
        "conversation",
        "edit",
        "file",
        "desk",
        "title",
        "part",
        "fix",
        "version",
        "similar",
        "run",
    }
)
SEALED_SOURCES = frozenset({"message", "answer", "conversation", "edit"})


@pytest.fixture
def db(db: Conn) -> Iterator[Conn]:
    """The shared `db` (every switch on), fresh gateway state, and clean-up: the jobs, vault values and gateway
    calls this test's ideas made, then (through `f.clean`) its ideas and people."""
    from core import killswitch
    from gateway import limits
    from gateway.routes import FAKE_SCRIPT

    killswitch.clear_cache()
    limits.reset()
    FAKE_SCRIPT.clear()
    last_job = int(db.execute("SELECT coalesce(max(id), 0) AS n FROM jobs").fetchone()["n"])
    yield db
    scopes = [scope_for(i) for i in f._made["ideas"]]
    db.execute("DELETE FROM jobs WHERE id > %s", (last_job,))
    db.execute("DELETE FROM pseudonym_vault WHERE scope_id = ANY(%s)", (scopes,))
    db.execute("DELETE FROM vault_counters WHERE scope_id = ANY(%s)", (scopes,))
    db.execute("DELETE FROM llm_calls WHERE ref_id = ANY(%s)", (scopes,))
    f.clean(db)
    FAKE_SCRIPT.clear()
    killswitch.clear_cache()


@pytest.fixture
def inbox(monkeypatch: pytest.MonkeyPatch) -> f.Inbox:
    return f.record_inbox(monkeypatch)


@pytest.fixture
def cast(db: Conn) -> dict[str, Any]:
    """Ravi leads the idea; Kavya asks to team up on it and brings her own shared idea; Asha asks from a draft."""
    ravi = f.person(db, "Ravi Nair")
    kavya = f.person(db, "Kavya Menon")
    asha = f.person(db, "Asha Sen", city="Pune", area="Operations")
    lead = f.idea(db, ravi, title="Rejection SMS codes confuse investors", shared_at=f.at(13, 9))
    mine = f.idea(
        db, kavya, title="Investors call to ask why a redemption was rejected", shared_at=f.at(14, 10)
    )
    return {"ravi": ravi, "kavya": kavya, "asha": asha, "lead": lead, "mine": mine}


def made_up() -> tuple[str, str, str]:
    """A folio, PAN and phone made up for this test, which the shared patterns catch (their last two characters
    fixed, so the masks read the same)."""
    folio = f"{secrets.randbelow(9_000_000) + 1_000_000}/89"
    pan = f"ABCPK{secrets.randbelow(900) + 100}4F"
    phone = f"98{secrets.randbelow(900_000) + 100_000}10"
    return folio, pan, phone


def gatekeeper_finding(
    monkeypatch: pytest.MonkeyPatch, name: str, *, calls: list[tuple[str, str]] | None = None
) -> list[str]:
    """Stand in for the gatekeeper (lane C's tests do the same): it finds `name` wherever it is in a text. Returns
    the texts it was asked about; with `calls` (`_lock_calls`), each ask is put there too as ("gatekeeper", text),
    in order with the locks (BLD-F100)."""
    asked: list[str] = []

    def gatekeeper_finds(conn: Any, text: str, scope: str) -> detect.Gate:
        asked.append(text)
        if calls is not None:
            calls.append(("gatekeeper", text))
        found: list[detect.Found] = []
        at = text.find(name)
        while at != -1:
            found.append(detect.Found(at, at + len(name), "name", name, "gatekeeper"))
            at = text.find(name, at + len(name))
        return detect.Gate(found)

    monkeypatch.setattr(detect, "gatekeeper_finds", gatekeeper_finds)
    return asked


@pytest.fixture
def customer(monkeypatch: pytest.MonkeyPatch) -> str:
    """A customer's name made up for this test that the patterns and names do not catch and the gatekeeper does."""
    name = "Kiran Ra" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(4))
    gatekeeper_finding(monkeypatch, name)
    return name


def _details(db: Conn, idea_uuid: Any, source_id: str | None = None) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in db.execute(
            "SELECT id, source, source_id, kind, found_by, vault_tag FROM hidden_details WHERE idea_uuid = %s "
            "AND (%s::text IS NULL OR source_id = %s::text) ORDER BY span_start NULLS LAST, created_at",
            (idea_uuid, source_id, source_id),
        ).fetchall()
    ]


def _sealed(db: Conn, source: str = "teamup") -> list[dict[str, str]]:
    """The sealed own words of a source: idea, key (lane C's `sealed_key`) and typer, as text."""
    return [
        {k: str(v) for k, v in r.items()}
        for r in db.execute(
            "SELECT idea_uuid, source_id, owner_user_id FROM idea_words_sealed WHERE source = %s ORDER BY id",
            (source,),
        ).fetchall()
    ]


def _masked_only(text: str, *values: str) -> None:
    """The masked copy: none of the values, each kind's mask instead."""
    for value in values:
        assert value not in text, "a hidden value is in the masked copy"


def _nowhere_in_clear(db: Conn, *values: str) -> None:
    for value in values:
        assert helpers.tables_containing(db, value) == [], "a hidden value is stored in clear"


def _stored(db: Conn, table: str, column: str, row_id: str) -> str | None:
    row = db.execute(f"SELECT {column} FROM {table} WHERE id = %s", (row_id,)).fetchone()  # noqa: S608
    assert row is not None
    return open_text(table, column, row_id, row[column])


# ---- the three texts, each masked before anyone else sees it -------------------------------------------------


def test_l_hide_l_teamup_dec_103_dec_104_bld_f097_the_note_is_masked_before_the_lead_reads_it(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, customer: str
) -> None:
    """The team-up note (L-TEAMUP.rules/2): the patterns hide the folio, PAN and phone, the gatekeeper the customer's
    name. Ravi's reader, the stored copy and, after he merges, `merges.note_encrypted` carry the masked copy only;
    the `hidden_details` rows sit under Ravi's idea as source `teamup` with the request's id, and the idea page's
    hidden details leave them out. Kavya, who typed it, reads her own words back; the Inbox notice carries IDs."""
    from ideapage.read import hidden

    folio, pan, phone = made_up()
    note = f"{customer} rang our Hyderabad branch twice about this. Folio {folio}, PAN {pan}, call {phone} after 6."
    lead, mine = cast["lead"], cast["mine"]
    sent = requests.send(db, lead["idea_id"], cast["kavya"]["id"],
                         {"note": note, "brought_idea_ids": [mine["idea_id"]]})  # fmt: skip
    rid = sent["id"]

    # Kavya reads her own words: the sheet's sent step, and her state on the idea
    assert sent["note"] == note
    assert requests.my_state(db, lead["idea_id"], cast["kavya"]["id"])["request"]["note"] == note
    assert requests.read(db, rid, cast["kavya"]["id"])["note"] == note

    # Ravi reads the masked copy only, and it is the stored one
    masked = requests.read(db, rid, cast["ravi"]["id"])["note"]
    _masked_only(masked, customer, folio, pan, phone)
    assert "Folio ••••89" in masked and "PAN ••••4F" in masked and "Phone ••••10" in masked
    assert "Name ••••" in masked and "rang our" in masked
    assert _stored(db, "teamup_requests", "note_encrypted", rid) == masked

    # lane C's rows: under the idea asked about, source `teamup`, the request's id; the name found by the gatekeeper
    rows = _details(db, lead["id"])
    assert {(r["source"], r["source_id"]) for r in rows} == {("teamup", rid)}
    assert sorted(r["kind"] for r in rows) == ["folio", "name", "pan", "phone"]
    assert {r["kind"]: r["found_by"] for r in rows}["name"] == "gatekeeper"
    assert _details(db, mine["id"]) == []
    assert _sealed(db) == [
        {"idea_uuid": str(lead["id"]), "source_id": rid, "owner_user_id": cast["kavya"]["id"]}
    ]
    assert adapters.own_words(db, str(lead["id"]), rid) == note
    assert all(h["source"] != "teamup" for h in hidden(db, str(lead["id"])))

    # the Inbox notice to Ravi: IDs only
    (item,) = inbox.of("teamup_request")
    _masked_only(str(item), customer, folio, pan, phone, "Hyderabad")
    _nowhere_in_clear(db, customer, folio, pan, phone)

    # Merge it: the merge carries the masked note on
    out = requests.answer(db, rid, cast["ravi"]["id"], {"answer": "merge"})
    assert out["request"]["note"] == masked
    m = db.execute("SELECT id FROM merges WHERE teamup_request_id = %s", (rid,)).fetchone()
    assert m is not None and _stored(db, "merges", "note_encrypted", str(m["id"])) == masked
    _nowhere_in_clear(db, customer, folio, pan, phone)


@pytest.mark.parametrize(
    ("viewer", "full", "as_typed"),
    [
        pytest.param("kavya", False, True, id="the-requester"),
        pytest.param("ravi", True, False, id="the-lead"),
        pytest.param("ravi", False, False, id="the-lead-without-full"),
        pytest.param("asha", False, False, id="a-third-viewer"),
        pytest.param("asha", True, False, id="a-third-viewer-with-full"),
        pytest.param(None, False, False, id="no-code"),
    ],
)
def test_l_teamup_dec_103_dec_104_bld_f098_the_note_reads_as_typed_only_for_its_requester(
    db: Conn,
    cast: dict[str, Any],
    inbox: f.Inbox,
    customer: str,
    viewer: str | None,
    full: bool,
    as_typed: bool,
) -> None:
    """`request_json` takes the reader's contributor code (BLD-F098), and the note's `mine` follows who reads, not
    who calls: Kavya, who sent it, reads her own note back; Ravi, the lead, reads the masked note, with the lead's
    view or without; a third person's code (Asha), or none, reads the masked note too, whatever `full` says."""
    folio, pan, phone = made_up()
    note = f"{customer} rang our Hyderabad branch twice about this. Folio {folio}, PAN {pan}, call {phone} after 6."
    sent = requests.send(
        db, cast["lead"]["idea_id"], cast["kavya"]["id"], {"note": note, "brought_idea_ids": []}
    )
    req = requests.load_request(db, sent["id"])
    code = cast[viewer]["code"] if viewer else None
    got = requests.request_json(db, req, viewer=code, full=full)["note"]
    if as_typed:
        assert got == note
    else:
        _masked_only(got, customer, folio, pan, phone)
        assert "Folio ••••89" in got and "Name ••••" in got
        assert got == _stored(db, "teamup_requests", "note_encrypted", sent["id"])


def test_l_teamup_l_merge_request_dec_103_dec_104_bld_f098_the_ask_reads_as_typed_only_for_its_owner(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, customer: str
) -> None:
    """`drafts.merge_request_json` reads whether its reader typed the ask from `user_id` against the request's
    `from_code` (BLD-F098), never assumed: Asha, who asked from her draft, reads her own words back; the lead's
    user id (Ravi) and a third person's (Kavya) read the masked ask, the stored copy."""
    folio, pan, phone = made_up()
    draft = f.draft(db, cast["asha"])
    ask = f"{customer} wrote to our Pune desk about the same SMS. Folio {folio}, PAN {pan}, call {phone} after 6."
    got = drafts.ask(
        db, str(draft["id"]), cast["asha"]["id"], {"other_idea_id": cast["lead"]["idea_id"], "note": ask}
    )
    req = requests.load_request(db, got["id"])
    assert drafts.merge_request_json(db, req, cast["asha"]["id"])["note"] == ask
    stored = _stored(db, "merge_requests", "note_encrypted", got["id"])
    for who in ("ravi", "kavya"):
        masked = drafts.merge_request_json(db, req, cast[who]["id"])["note"]
        _masked_only(masked, customer, folio, pan, phone)
        assert masked == stored


def test_l_hide_l_teamup_dec_103_bld_f097_the_decline_reason_is_masked_before_the_requester_reads_it(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, customer: str
) -> None:
    """The lead's decline reason (L-TEAMUP.rules/5): Kavya's sheet, her request page and the stored copy carry the
    masked reason only; the rows sit under Ravi's idea with "<request id>:decline"; Ravi, who typed it, reads his
    own words back on the request's page, and his result line shows what Kavya sees."""
    folio, _, phone = made_up()
    lead = cast["lead"]
    sent = requests.send(db, lead["idea_id"], cast["kavya"]["id"], {"note": NOTE, "brought_idea_ids": []})
    rid = sent["id"]
    reason = f"{customer} already raised this with us. Ask about folio {folio} on {phone} after 6."
    out = requests.answer(db, rid, cast["ravi"]["id"], {"answer": "decline", "reason": reason})
    assert out["result"]["state"] == "declined"
    _masked_only(out["result"]["text"], customer, folio, phone)

    # Kavya reads the masked reason only, and it is the stored one
    mine = requests.my_state(db, lead["idea_id"], cast["kavya"]["id"])
    masked = mine["request"]["lead_reason"]
    _masked_only(masked, customer, folio, phone)
    assert "Folio ••••89" in masked and "Phone ••••10" in masked and "Name ••••" in masked
    assert mine["after"]["line"].startswith("Ravi declined: ")
    _masked_only(mine["after"]["line"], customer, folio, phone)
    assert requests.read(db, rid, cast["kavya"]["id"])["lead_reason"] == masked
    assert _stored(db, "teamup_requests", "lead_reason_encrypted", rid) == masked

    # lane C's rows: under Ravi's idea, "<request id>:decline", sealed for Ravi alone
    key = adapters.decline_id(rid)
    assert key == f"{rid}:decline"
    rows = _details(db, lead["id"], key)
    assert sorted(r["kind"] for r in rows) == ["folio", "name", "phone"] and {r["source"] for r in rows} == {
        "teamup"
    }
    assert {r["kind"]: r["found_by"] for r in rows}["name"] == "gatekeeper"
    sealed = {r["source_id"]: r["owner_user_id"] for r in _sealed(db)}
    assert sealed[f"{lead['id']}:{key}"] == cast["ravi"]["id"]  # lane C's `sealed_key`: under the idea's uuid
    assert own_words(db, "teamup", key, idea_uuid=str(lead["id"])) == reason

    # Ravi typed it: his request page gives his own words back; his result line reads as Kavya's sheet does
    page = requests.read(db, rid, cast["ravi"]["id"])
    assert page["lead_reason"] == reason
    _masked_only(page["result"]["text"], customer, folio, phone)

    # the Inbox notice to Kavya: IDs only, never the reason
    (told,) = inbox.of("teamup_answer")
    assert told["refs"] == {"request_id": rid, "request": "teamup", "answer": "decline", "has_reason": True}
    _masked_only(str(told), customer, folio, phone, "already raised")
    _nowhere_in_clear(db, customer, folio, phone)


def test_l_hide_l_merge_request_dec_103_bld_f097_a_drafts_ask_is_masked_before_the_lead_reads_it(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, customer: str
) -> None:
    """A draft's ask (L-MERGE.request/2): Ravi's reader, the stored copy and, after he merges the draft in,
    `merges.note_encrypted` carry the masked ask only; the rows sit under Asha's draft with "<merge request id>:ask";
    Asha, who typed it, reads her own words back on Check it."""
    folio, pan, phone = made_up()
    draft = f.draft(db, cast["asha"])
    ask = f"{customer} wrote to our Pune desk about the same SMS. Folio {folio}, PAN {pan}, call {phone} after 6."
    got = drafts.ask(db, str(draft["id"]), cast["asha"]["id"],
                     {"other_idea_id": cast["lead"]["idea_id"], "note": ask})  # fmt: skip
    rid = got["id"]
    assert got["state"] == "waiting"

    # Asha reads her own words on Check it
    assert got["note"] == ask
    assert drafts.state(db, str(draft["id"]), cast["asha"]["id"])["note"] == ask

    # Ravi reads the masked copy only, and it is the stored one
    masked = requests.read(db, rid, cast["ravi"]["id"])["note"]
    _masked_only(masked, customer, folio, pan, phone)
    assert (
        "Folio ••••89" in masked
        and "PAN ••••4F" in masked
        and "Phone ••••10" in masked
        and "Name ••••" in masked
    )
    assert _stored(db, "merge_requests", "note_encrypted", rid) == masked

    # lane C's rows: under the draft (Asha typed it), "<merge request id>:ask"; none under Ravi's idea
    key = adapters.ask_id(rid)
    assert key == f"{rid}:ask"
    rows = _details(db, draft["id"])
    assert {(r["source"], r["source_id"]) for r in rows} == {("teamup", key)}
    assert sorted(r["kind"] for r in rows) == ["folio", "name", "pan", "phone"]
    assert {r["kind"]: r["found_by"] for r in rows}["name"] == "gatekeeper"
    assert _details(db, cast["lead"]["id"]) == []
    sealed = {r["source_id"]: r["owner_user_id"] for r in _sealed(db)}
    assert sealed == {f"{draft['id']}:{key}": cast["asha"]["id"]}
    assert own_words(db, "teamup", key, idea_uuid=str(draft["id"])) == ask

    (item,) = inbox.of("teamup_request")
    _masked_only(str(item), customer, folio, pan, phone, "Pune desk")
    _nowhere_in_clear(db, customer, folio, pan, phone)

    # Merge it: the merge carries the masked ask on
    requests.answer(db, rid, cast["ravi"]["id"], {"answer": "merge"})
    m = db.execute("SELECT id FROM merges WHERE merge_request_id = %s", (rid,)).fetchone()
    assert m is not None and _stored(db, "merges", "note_encrypted", str(m["id"])) == masked
    _nowhere_in_clear(db, customer, folio, pan, phone)


def test_l_hide_bld_f097_a_note_a_reason_and_an_ask_on_related_requests_all_seal_with_no_conflict(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, customer: str
) -> None:
    """`idea_words_sealed` is UNIQUE on (source, source_id) across every idea, and lane C refuses (409) a row of
    another idea or person: Kavya's note on Ravi's idea, Ravi's reason declining it, Kavya's ask from her draft to
    the same idea and Ravi's reason declining that all seal, each under its own id, idea and typer."""
    lead, kavya, ravi = cast["lead"], cast["kavya"], cast["ravi"]
    folio = made_up()[0]
    sent = requests.send(db, lead["idea_id"], kavya["id"],
                         {"note": f"{customer} asked at the counter again. Folio {folio} is the one."})  # fmt: skip
    requests.answer(
        db, sent["id"], ravi["id"], {"answer": "decline", "reason": f"Not now. {customer} is ours."}
    )
    draft = f.draft(db, kavya)
    got = drafts.ask(db, str(draft["id"]), kavya["id"],
                     {"other_idea_id": lead["idea_id"], "note": f"Same as my note: {customer}, folio {folio}."})  # fmt: skip
    requests.answer(
        db, got["id"], ravi["id"], {"answer": "decline", "reason": f"Still {customer}, folio {folio}."}
    )
    lead_id, draft_id = lead["id"], draft["id"]
    assert sorted((r["idea_uuid"], r["source_id"], r["owner_user_id"]) for r in _sealed(db)) == sorted([
        (str(lead_id), sent["id"], kavya["id"]),
        (str(lead_id), f"{lead_id}:{sent['id']}:decline", ravi["id"]),
        (str(draft_id), f"{draft_id}:{got['id']}:ask", kavya["id"]),
        (str(lead_id), f"{lead_id}:{got['id']}:decline", ravi["id"]),
    ])  # fmt: skip
    assert {r["source_id"] for r in _details(db, lead_id)} == {
        sent["id"],
        f"{sent['id']}:decline",
        f"{got['id']}:decline",
    }
    assert {r["source_id"] for r in _details(db, draft_id)} == {f"{got['id']}:ask"}
    # each reader: Kavya her note and her ask, Ravi his two reasons; the other side the masked copies
    assert drafts.state(db, str(draft_id), kavya["id"])["note"].startswith(f"Same as my note: {customer}")
    assert customer not in drafts.state(db, str(draft_id), kavya["id"])["lead_reason"]
    assert requests.read(db, got["id"], ravi["id"])["lead_reason"] == f"Still {customer}, folio {folio}."
    assert customer not in requests.read(db, got["id"], ravi["id"])["note"]
    _nowhere_in_clear(db, customer, folio)


# ---- when the gatekeeper cannot run --------------------------------------------------------------------------


def test_l_hide_detect_bld_f097_with_the_assistant_off_the_note_still_hides_what_the_patterns_find(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    """`ai.all` off (lane C's `gatekeeper_finds` asks no model): the patterns still hide the folio and phone before
    Ravi reads the note, and no model is called. A switch turned off on purpose is not a failure, so lane C audits no
    skip and queues no re-check for it (BLD-C067); the name only the gatekeeper would find stays."""
    from core import killswitch

    folio, _, phone = made_up()
    name = "Kiran Ra" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(4))
    note = f"{name} rang twice about this. Folio {folio}, call {phone} after 6, about the R07 SMS."
    calls = db.execute("SELECT count(*) AS n FROM llm_calls").fetchone()["n"]
    db.execute("UPDATE kill_switches SET state = 'off' WHERE name = 'ai.all'")
    killswitch.clear_cache()
    try:
        sent = requests.send(db, cast["lead"]["idea_id"], cast["kavya"]["id"], {"note": note})
    finally:
        db.execute("UPDATE kill_switches SET state = 'on' WHERE name = 'ai.all'")
        killswitch.clear_cache()
    masked = requests.read(db, sent["id"], cast["ravi"]["id"])["note"]
    _masked_only(masked, folio, phone)
    assert "Folio ••••89" in masked and "Phone ••••10" in masked and name in masked
    assert sent["note"] == note
    assert db.execute("SELECT count(*) AS n FROM llm_calls").fetchone()["n"] == calls
    entity = f"idea:{cast['lead']['id']}"
    assert (
        db.execute(
            "SELECT count(*) AS n FROM audit_log WHERE action = 'hide.gatekeeper_skipped' AND entity = %s",
            (entity,),
        ).fetchone()["n"]
        == 0
    )
    assert (
        db.execute(
            "SELECT count(*) AS n FROM jobs WHERE type = 'hide.recheck' AND payload->>'source_id' = %s",
            (sent["id"],),
        ).fetchone()["n"]
        == 0
    )


def test_l_hide_detect_bld_f097_a_gatekeeper_failure_is_audited_and_the_recheck_rewrites_the_note(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gateway fails while Kavya's note is hidden: the patterns still hide the folio and phone, lane C audits
    `hide.gatekeeper_skipped` with IDs and the code only and queues a `hide.recheck` job for source `teamup`. Ravi
    merges Kavya's idea in, so the note is carried into `merges.note_encrypted`. Once the gateway is back, the
    re-check finds the customer's name and lane F's writer (`adapters.write_masked`, through lane C's new `teamup`
    branch in `hide/recheck.py`) rewrites both stored copies; Kavya still reads her own words."""
    folio, _, phone = made_up()
    name = "Kiran Ra" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(4))
    note = f"{name} rang twice about this. Folio {folio}, call {phone} after 6, about the R07 SMS."
    lead, mine = cast["lead"], cast["mine"]

    def gateway_down(conn: Any, text: str, scope: str) -> detect.Gate:
        return detect.Gate([], "connection")

    monkeypatch.setattr(detect, "gatekeeper_finds", gateway_down)
    sent = requests.send(db, lead["idea_id"], cast["kavya"]["id"],
                         {"note": note, "brought_idea_ids": [mine["idea_id"]]})  # fmt: skip
    rid = sent["id"]
    before = requests.read(db, rid, cast["ravi"]["id"])["note"]
    _masked_only(before, folio, phone)
    assert name in before  # only the gatekeeper finds it
    skipped = db.execute(
        "SELECT after FROM audit_log WHERE action = 'hide.gatekeeper_skipped' AND entity = %s",
        (f"idea:{lead['id']}",),
    ).fetchone()["after"]
    assert skipped["source"] == "teamup" and skipped["source_id"] == rid and skipped["code"] == "connection"
    _masked_only(str(skipped), name, folio, phone)
    job = db.execute(
        "SELECT id, payload FROM jobs WHERE type = 'hide.recheck' AND payload->>'source_id' = %s", (rid,)
    ).fetchone()
    assert job is not None and skipped["recheck_job"] == job["id"]
    assert job["payload"] == {
        "idea_uuid": str(lead["id"]), "source": "teamup", "source_id": rid, "by": cast["kavya"]["id"]
    }  # fmt: skip

    requests.answer(db, rid, cast["ravi"]["id"], {"answer": "merge"})
    m = db.execute("SELECT id FROM merges WHERE teamup_request_id = %s", (rid,)).fetchone()
    assert m is not None and _stored(db, "merges", "note_encrypted", str(m["id"])) == before

    gatekeeper_finding(monkeypatch, name)  # the gateway is back
    hide_recheck.run(db, job["payload"])
    after = requests.read(db, rid, cast["ravi"]["id"])["note"]
    _masked_only(after, name, folio, phone)
    assert "Name ••••" in after and "Folio ••••89" in after and "Phone ••••10" in after
    assert _stored(db, "teamup_requests", "note_encrypted", rid) == after
    assert _stored(db, "merges", "note_encrypted", str(m["id"])) == after
    found = {r["kind"]: r["found_by"] for r in _details(db, lead["id"], rid)}
    assert found == {"name": "gatekeeper", "folio": "patterns", "phone": "patterns"}
    assert requests.my_state(db, lead["idea_id"], cast["kavya"]["id"])["request"]["note"] == note
    _nowhere_in_clear(db, name, folio, phone)


def test_bld_f097_write_masked_maps_each_source_id_to_its_stored_copy(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    """Lane F's writer for lane C's re-check: "<request id>" the team-up note, "<request id>:decline" the lead's
    reason on whichever table holds the request, "<merge request id>:ask" a draft's ask; anything else writes
    nothing."""
    lead, kavya, ravi = cast["lead"], cast["kavya"], cast["ravi"]
    sent = requests.send(db, lead["idea_id"], kavya["id"], {"note": NOTE})
    requests.answer(db, sent["id"], ravi["id"], {"answer": "decline", "reason": "The crew is full for now."})
    draft = f.draft(db, cast["asha"])
    got = drafts.ask(
        db, str(draft["id"]), cast["asha"]["id"], {"other_idea_id": lead["idea_id"], "note": NOTE}
    )
    requests.answer(db, got["id"], ravi["id"], {"answer": "decline", "reason": "Better as two, for now."})

    assert adapters.write_masked(db, sent["id"], "Note, masked again.") == 1
    assert adapters.write_masked(db, adapters.decline_id(sent["id"]), "Reason, masked again.") == 1
    assert adapters.write_masked(db, adapters.ask_id(got["id"]), "Ask, masked again.") == 1
    assert adapters.write_masked(db, adapters.decline_id(got["id"]), "Its reason, masked again.") == 1
    assert _stored(db, "teamup_requests", "note_encrypted", sent["id"]) == "Note, masked again."
    assert _stored(db, "teamup_requests", "lead_reason_encrypted", sent["id"]) == "Reason, masked again."
    assert _stored(db, "merge_requests", "note_encrypted", got["id"]) == "Ask, masked again."
    assert _stored(db, "merge_requests", "lead_reason_encrypted", got["id"]) == "Its reason, masked again."
    assert adapters.write_masked(db, f"{sent['id']}:other", "x") == 0
    assert adapters.write_masked(db, "not-a-request:decline", "x") == 0
    assert adapters.write_masked(db, adapters.ask_id(sent["id"]), "x") == 0  # a team-up request has no ask
    assert _stored(db, "teamup_requests", "note_encrypted", sent["id"]) == "Note, masked again."


# ---- BLD-B247: lane C's lock first, in uuid order, then the rows ----------------------------------------------


def _lock_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Every lock asked for, in order: ("hide", uuid) for each call of lane C's `hide.core.lock` (lane F reaches it
    through `teamup.adapters.lock_hide`, lane C's hide through its own call), and ("row", uuid) for each idea row
    lane F's `lock_ideas` locks, in the order it locks them (by uuid)."""
    import hide.core
    from teamup import store

    calls: list[tuple[str, str]] = []
    real_lock, real_ideas = hide.core.lock, store.lock_ideas

    def hide_lock(conn: Conn, idea_uuid: str) -> None:
        calls.append(("hide", str(idea_uuid)))
        real_lock(conn, idea_uuid)

    def lock_ideas(conn: Conn, *uuids: Any) -> dict[str, dict[str, Any]]:
        calls.extend(("row", u) for u in sorted({str(u) for u in uuids}))
        return real_ideas(conn, *uuids)

    monkeypatch.setattr(hide.core, "lock", hide_lock)
    monkeypatch.setattr(requests, "lock_ideas", lock_ideas)
    monkeypatch.setattr(drafts, "lock_ideas", lock_ideas)
    return calls


def test_l_hide_bld_b247_bld_f097_send_and_a_drafts_ask_take_lane_cs_lock_first_in_one_order(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, customer: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L-HIDE (BLD-C067's lock order), BLD-B247, BLD-F097: `requests.send` (with an idea brought) and `drafts.ask`
    each take lane C's lock on every idea they lock, in uuid order, before any row lock, and then the rows in the
    same order. Lane C's hide of the note or the ask asks again for a lock the transaction already holds."""
    lead, mine = cast["lead"], cast["mine"]
    draft = f.draft(db, cast["asha"])
    calls = _lock_calls(monkeypatch)

    def in_order(*uuids: Any) -> list[tuple[str, str]]:
        ids = sorted(str(u) for u in uuids)
        return [("hide", u) for u in ids] + [("row", u) for u in ids]

    folio = made_up()[0]
    requests.send(db, lead["idea_id"], cast["kavya"]["id"],
                  {"note": f"{customer} asked again. Folio {folio} is the one at our branch.",
                   "brought_idea_ids": [mine["idea_id"]]})  # fmt: skip
    sent_calls = list(calls)
    assert list(dict.fromkeys(sent_calls)) == in_order(lead["id"], mine["id"])
    assert ("hide", str(lead["id"])) in sent_calls[4:]  # lane C's hide of the note: held already

    calls.clear()
    drafts.ask(db, str(draft["id"]), cast["asha"]["id"],
               {"other_idea_id": lead["idea_id"], "note": f"{customer} wrote to us too, folio {folio}."})  # fmt: skip
    ask_calls = list(calls)
    assert list(dict.fromkeys(ask_calls)) == in_order(draft["id"], lead["id"])
    assert ("hide", str(draft["id"])) in ask_calls[4:]  # lane C's hide of the ask: held already


# ---- BLD-F100: the gatekeeper is asked before lane C's lock (lane C's `hide.gate`, BLD-C234) -------------------


def _asked_first(calls: list[tuple[str, str]], text: str) -> None:
    """One call's asks and locks: the gatekeeper asked once, for `text` exactly, before lane C's first lock and the
    first row lock, and then both kinds of lock taken, so lane C's hide used that answer under the lock."""
    asks = [c for c in calls if c[0] == "gatekeeper"]
    assert asks == [("gatekeeper", text)], calls
    assert calls[0] == ("gatekeeper", text), calls
    assert any(c[0] == "hide" for c in calls) and any(c[0] == "row" for c in calls), calls


def test_l_hide_detect_bld_f100_bld_c234_the_note_a_reason_and_an_ask_go_to_the_gatekeeper_before_any_lock(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, customer: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L-HIDE.detect, BLD-F100: the team-up note (`requests.send`), the lead's decline reason (`requests.answer`) and
    a draft's ask (`drafts.ask`) each go to the gatekeeper once, trimmed exactly as they are hidden, before lane C's
    lock and any row lock (`adapters.gate`). Lane C's hide uses that answer under the lock and asks nothing more,
    so no lock waits on the model. What the gatekeeper finds is still hidden from the other side."""
    lead, mine = cast["lead"], cast["mine"]
    draft = f.draft(db, cast["asha"])
    calls = _lock_calls(monkeypatch)
    gatekeeper_finding(monkeypatch, customer, calls=calls)
    folio = made_up()[0]

    note = f"{customer} asked again at the counter. Folio {folio} is the one at our branch."
    sent = requests.send(db, lead["idea_id"], cast["kavya"]["id"],
                         {"note": f"  {note}  ", "brought_idea_ids": [mine["idea_id"]]})  # fmt: skip
    _asked_first(list(calls), note)
    _masked_only(requests.read(db, sent["id"], cast["ravi"]["id"])["note"], customer, folio)

    calls.clear()
    reason = f"{customer} is with another crew on this one, folio {folio}."
    requests.answer(db, sent["id"], cast["ravi"]["id"], {"answer": "decline", "reason": f" {reason} "})
    _asked_first(list(calls), reason)
    stored = _stored(db, "teamup_requests", "lead_reason_encrypted", sent["id"])
    assert stored is not None
    _masked_only(stored, customer, folio)

    calls.clear()
    ask = f"{customer} wrote to us about this too, folio {folio}, so mine fits yours."
    got = drafts.ask(
        db, str(draft["id"]), cast["asha"]["id"], {"other_idea_id": lead["idea_id"], "note": ask}
    )
    _asked_first(list(calls), ask)
    stored = _stored(db, "merge_requests", "note_encrypted", got["id"])
    assert stored is not None
    _masked_only(stored, customer, folio)
    _nowhere_in_clear(db, customer, folio)

    # an answer with no reason asks nothing
    meghna = f.person(db, "Meghna Rao")
    rid = requests.send(db, lead["idea_id"], meghna["id"], {"note": NOTE})["id"]
    calls.clear()
    requests.answer(db, rid, cast["ravi"]["id"], {"answer": "team_only"})
    assert not [c for c in calls if c[0] == "gatekeeper"], calls


def test_l_hide_bld_f100_nothing_goes_to_the_gatekeeper_before_the_person_may_write_it(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, customer: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLD-F100, DEC-103: lane C's gate checks no ownership, so lane F asks it only once the person may write the
    text. The lead asking to team up on their own idea, a note too short, a second request while one waits, an
    answer from someone who is not the lead and an ask from someone else's draft are each refused as before, and
    none of those words reaches the gatekeeper."""
    from teamup.store import Refused

    lead = cast["lead"]
    asked = gatekeeper_finding(monkeypatch, customer)
    words = f"{customer} rang our branch about this twice last week."

    def refused(call: Any, *args: Any) -> Refused:
        with pytest.raises(Refused) as exc:
            call(db, *args)
        return exc.value

    own = refused(requests.send, lead["idea_id"], cast["ravi"]["id"], {"note": words})
    assert own.code == "already_on_crew"
    short = refused(requests.send, lead["idea_id"], cast["kavya"]["id"], {"note": customer})
    assert short.code == "note_too_short"
    assert asked == []

    rid = requests.send(db, lead["idea_id"], cast["kavya"]["id"], {"note": NOTE})["id"]
    assert asked == [NOTE]  # hers, once she may send it
    asked.clear()
    again = refused(requests.send, lead["idea_id"], cast["kavya"]["id"], {"note": words})
    assert again.code == "already_requested"
    not_lead = refused(requests.answer, rid, cast["asha"]["id"], {"answer": "decline", "reason": words})
    assert not_lead.code == "not_lead"
    other_draft = f.draft(db, cast["asha"])
    not_hers = refused(drafts.ask, str(other_draft["id"]), cast["kavya"]["id"],
                       {"other_idea_id": lead["idea_id"], "note": words})  # fmt: skip
    assert not_hers.status == 404
    assert asked == []


# ---- the idea's sharer never owns, sees or reveals a requester's details (DEC-103, DEC-104) --------------------


def _noted(db: Conn, c: dict[str, Any], customer: str) -> tuple[str, set[str]]:
    """Kavya's note on Ravi's idea with a folio and a customer's name: the request id and its detail ids."""
    folio = made_up()[0]
    sent = requests.send(db, c["lead"]["idea_id"], c["kavya"]["id"],
                         {"note": f"{customer} asked at the counter again. Folio {folio} is the one."})  # fmt: skip
    ids = {str(r["id"]) for r in _details(db, c["lead"]["id"], sent["id"])}
    assert len(ids) == 2
    return sent["id"], ids


def test_l_hide_dec_103_bld_f097_show_it_on_a_team_up_detail_is_refused_to_the_lead_and_the_requester(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, customer: str
) -> None:
    """L-HIDE.rules/6: a team-up detail sits under the idea asked about, but its sharer (Ravi, the lead) never owns
    it: lane C's `_owner_of` has no owner for source `teamup`, so Show it and Hide it again answer 404 to Ravi and
    to Kavya alike, and the detail stays hidden. Kavya reads her words through `own_words` instead."""
    from hide import HideError, hide_again, show

    rid, ids = _noted(db, cast, customer)
    lead_uuid = str(cast["lead"]["id"])
    for hid in ids:
        for who in (cast["ravi"], cast["kavya"]):
            with pytest.raises(HideError) as shown:
                show(db, lead_uuid, hid, reason="made_up_example", by=who["id"])
            assert (shown.value.status, shown.value.code) == (404, "not_found")
            with pytest.raises(HideError) as again:
                hide_again(db, lead_uuid, hid, by=who["id"])
            assert (again.value.status, again.value.code) == (404, "not_found")
    states = db.execute(
        "SELECT state, count(*) AS n FROM hidden_details WHERE source = 'teamup' AND source_id = %s GROUP BY state",
        (rid,),
    ).fetchall()
    assert [(r["state"], r["n"]) for r in states] == [("hidden", 2)]


def test_l_hide_dec_103_dec_104_bld_f097_the_leads_edit_page_and_track_leave_out_a_requesters_details(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, customer: str
) -> None:
    """S-06B (`submit.edit.page`) lists the hidden details of Ravi's own words only, and his track's "Checked and
    matched" line (`submit.send.handover`) counts only those: a team-up note's details under his idea are Kavya's."""
    from submit import edit as submit_edit
    from submit.send import handover

    _, ids = _noted(db, cast, customer)
    lead = cast["lead"]
    page = submit_edit.page(db, lead["idea_id"], cast["ravi"]["id"], now=f.at(14, 12))
    assert not ids & {str(h["id"]) for h in page["hidden"]}
    idea = db.execute("SELECT * FROM ideas WHERE id = %s", (lead["id"],)).fetchone()
    assert idea is not None
    track = handover(db, dict(idea), f.at(14, 12))
    assert "No personal details found" in str(track["stages"])


def test_l_hide_dec_103_bld_f097_the_desks_hidden_and_shown_lists_leave_out_team_up_details(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, customer: str
) -> None:
    """Lane B's reviewer page reads an idea's hidden and shown details through `desk.reads._hidden` and `_shown`:
    the page's hidden list, the Attached part's "… is hidden from everyone." line, the own words' "Folio hidden."
    line and the Listen script (`listen_script`) all go through `_hidden`; the committee reads the same page. A
    team-up note's details under Ravi's idea are in neither list, hidden or (were one ever shown) shown."""
    from desk.reads import _hidden, _shown

    rid, _ = _noted(db, cast, customer)
    lead_uuid = cast["lead"]["id"]
    assert _hidden(db, lead_uuid) == []
    db.execute(
        "UPDATE hidden_details SET state = 'shown', reason = 'made_up_example', shown_at = now() "
        "WHERE source = 'teamup' AND source_id = %s AND kind = 'folio'",
        (rid,),
    )
    assert _shown(db, lead_uuid) == [] and _hidden(db, lead_uuid) == []


# ---- the migration: lane C's `teamup` source -------------------------------------------------------------------


class _Undo(Exception):
    """Raised at the end of the migration's round trip, so its transaction rolls back."""


def _listed(db: Conn, table: str, name: str) -> frozenset[str]:
    row = db.execute(
        "SELECT pg_get_constraintdef(c.oid) AS def FROM pg_constraint c WHERE c.conname = %s "
        "AND c.conrelid = %s::regclass AND c.contype = 'c'",
        (name, f"public.{table}"),
    ).fetchone()
    assert row is not None, name
    return frozenset(re.findall(r"'([^']*)'", row["def"]))


def _section(which: str) -> str:
    sql = MIGRATION.read_text(encoding="utf-8")
    up, down = sql.split("-- migrate:up", 1)[1].split("-- migrate:down", 1)
    return up if which == "up" else down


def test_bld_f097_l_hide_the_teamup_source_migration_checks_and_its_down_with_a_teamup_row(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, customer: str
) -> None:
    """20261122301100: both CHECKs take `teamup` (`hidden_details_source_check`, `idea_words_sealed_source_check`,
    read from pg_constraint). Its down, with a team-up note's rows present, removes those rows and the vault values
    only they held, then restores both CHECKs, after which a `teamup` row is refused; its up widens them again.
    The round trip runs in a transaction that is rolled back."""

    def hidden_check() -> frozenset[str]:
        return _listed(db, "hidden_details", "hidden_details_source_check")

    def sealed_check() -> frozenset[str]:
        return _listed(db, "idea_words_sealed", "idea_words_sealed_source_check")

    assert hidden_check() == HIDDEN_SOURCES | {"teamup"}
    assert sealed_check() == SEALED_SOURCES | {"teamup"}

    folio = made_up()[0]
    lead = cast["lead"]
    sent = requests.send(db, lead["idea_id"], cast["kavya"]["id"],
                         {"note": f"{customer} asked at the counter again. Folio {folio} is the one."})  # fmt: skip
    tags = sorted({str(r["vault_tag"]) for r in _details(db, lead["id"], sent["id"]) if r["vault_tag"]})
    assert len(tags) == 2 and len(_sealed(db)) == 1

    def vault_values() -> int:
        return int(
            db.execute(
                "SELECT count(*) AS n FROM pseudonym_vault WHERE scope_id = %s AND tag = ANY(%s::text[])",
                (scope_for(str(lead["id"])), tags),
            ).fetchone()["n"]
        )

    assert vault_values() == 2
    with pytest.raises(_Undo), db.transaction():
        db.execute(_section("down"))
        assert _details(db, lead["id"]) == [] and _sealed(db) == [] and vault_values() == 0
        assert hidden_check() == HIDDEN_SOURCES and sealed_check() == SEALED_SOURCES
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            db.execute(
                "INSERT INTO idea_words_sealed (idea_uuid, source, source_id, owner_user_id, text_encrypted) "
                "VALUES (%s, 'teamup', %s, %s, %s)",
                (lead["id"], sent["id"], cast["kavya"]["id"], b"sealed"),
            )
        db.execute(_section("up"))
        assert hidden_check() == HIDDEN_SOURCES | {"teamup"}
        assert sealed_check() == SEALED_SOURCES | {"teamup"}
        raise _Undo
    assert len(_details(db, lead["id"], sent["id"])) == 2 and len(_sealed(db)) == 1 and vault_values() == 2


# ---- the requester's own request on a match card (similar/views.py `my_request`, BLD-F101) -------------------


def test_l_teamup_l_similar_dec_103_dec_104_bld_f101_the_requester_reads_their_own_note_on_the_match_card(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, customer: str
) -> None:
    """L-SIMILAR, L-TEAMUP: the match card's `my_request` is the viewer's own request (its row is theirs by
    `from_code`), so its note is the words they typed, from lane C's sealed copy (BLD-F097), as everywhere else
    they read it back. The stored copy, which the lead and everyone else read, stays masked (DEC-103, DEC-104)."""
    from similar.preview import Viewer
    from similar.views import my_request

    folio, pan, phone = made_up()
    note = f"{customer} rang our Hyderabad branch twice about this. Folio {folio}, PAN {pan}, call {phone} after 6."
    lead = cast["lead"]
    rid = requests.send(db, lead["idea_id"], cast["kavya"]["id"], {"note": note, "brought_idea_ids": []})[
        "id"
    ]
    card = my_request(db, str(lead["id"]), Viewer.of(db, cast["kavya"]["id"]))
    assert card is not None and card["id"] == rid
    assert card["note"] == note
    stored = _stored(db, "teamup_requests", "note_encrypted", rid)
    assert stored is not None and stored != note
    _masked_only(stored, customer, folio, pan, phone)
    assert (
        my_request(db, str(lead["id"]), Viewer.of(db, cast["ravi"]["id"])) is None
    )  # only the requester's own


def test_l_teamup_l_similar_dec_103_bld_f101_a_note_with_no_sealed_words_reads_as_its_masked_copy(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, customer: str
) -> None:
    """A request sent before BLD-F097, or seeded, has no sealed words: the match card reads the masked copy stored
    on the request, never nothing and never the other's words."""
    from similar.preview import Viewer
    from similar.views import my_request

    folio, _, phone = made_up()
    lead = cast["lead"]
    rid = requests.send(db, lead["idea_id"], cast["kavya"]["id"],
                        {"note": f"{customer} asked again. Folio {folio}, call {phone}.", "brought_idea_ids": []},
                        )["id"]  # fmt: skip
    db.execute("DELETE FROM idea_words_sealed WHERE source = 'teamup' AND idea_uuid = %s", (lead["id"],))
    card = my_request(db, str(lead["id"]), Viewer.of(db, cast["kavya"]["id"]))
    assert card is not None
    assert card["note"] == _stored(db, "teamup_requests", "note_encrypted", rid)
    _masked_only(card["note"], customer, folio, phone)


def test_l_teamup_l_similar_dec_103_bld_f101_the_leads_reason_on_the_card_stays_masked(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, customer: str
) -> None:
    """The lead's decline reason on the requester's card is the lead's words, so the requester reads the masked
    copy even though the lead's own words are sealed (lane C's condition, BLD-F101)."""
    from similar.preview import Viewer
    from similar.views import my_request

    folio, _, phone = made_up()
    lead = cast["lead"]
    rid = requests.send(db, lead["idea_id"], cast["kavya"]["id"], {"note": NOTE, "brought_idea_ids": []})[
        "id"
    ]
    reason = f"{customer} already raised this with us. Ask about folio {folio} on {phone} after 6."
    requests.answer(db, rid, cast["ravi"]["id"], {"answer": "decline", "reason": reason})
    assert own_words(db, "teamup", adapters.decline_id(rid), idea_uuid=str(lead["id"])) == reason  # sealed
    card = my_request(db, str(lead["id"]), Viewer.of(db, cast["kavya"]["id"]))
    assert card is not None and card["state"] == "declined"
    assert card["lead_reason"] == _stored(db, "teamup_requests", "lead_reason_encrypted", rid)
    _masked_only(card["lead_reason"], customer, folio, phone)
    assert card["note"] == NOTE  # her own note, as typed
