"""L-HIDE.rules/1 to /8, L-HIDE.detect and L-HIDE.audit against a migrated test database (lane C, BLD-C060 to
BLD-C069): what is stored where, the masked copy, "Show it" and "Hide it", the desk's "Hide this" in every copy, the
gatekeeper and its re-check. Values are synthetic and made up for each test (non-negotiable 11), so a search of the
whole database finds only this test's rows, even on a database other runs have used. Each hide and the write of its
masked copy run in one transaction, as callers must (`hide/__init__.py`)."""

from __future__ import annotations

import secrets
import string
import uuid
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest

from core.crypto import decrypt_json, encrypt_json
from hide import HideError, desk_hide, forget, hide_again, hide_message, hide_text, show
from hide import recheck as hide_recheck
from hide.core import own_words, scope_for, sealed_key
from hide.detect import mask, to_utf16
from onepc.context import open_text, seal_text, sealed_context
from pii import vault
from tests import helpers

pytestmark = pytest.mark.stack


@pytest.fixture
def hdb(db: Any, company_repo: Any) -> Iterator[Any]:
    """The migrated test database with every switch on (the gatekeeper runs in fake mode) and fresh caches. Each
    test removes what it made afterwards (`remove_made`)."""
    from core import killswitch
    from gateway import limits
    from gateway.routes import FAKE_SCRIPT

    killswitch.clear_cache()
    limits.reset()
    FAKE_SCRIPT.clear()
    started = db.execute("SELECT clock_timestamp() AS t").fetchone()["t"]
    try:
        yield db
    finally:
        FAKE_SCRIPT.clear()
        killswitch.clear_cache()
        remove_made(db, started)


def remove_made(conn: Any, since: Any) -> None:
    """Everything this module's synthetic people made: their ideas (hidden details, messages, sealed words, parts and
    status history go with them), the vault values, counters and gateway calls under each idea's hide scope, the
    gatekeeper's cache entries from this test, and the people. `audit_log` is append-only (its trigger refuses
    DELETE), so its rows stay; every audit read here is scoped to the test's own `idea:<uuid>`."""
    from tests.web import remove_people

    users = [
        str(r["id"])
        for r in conn.execute(
            "SELECT id FROM users WHERE emp_id_hash LIKE %s AND email LIKE %s",
            ("test:%", "tester.%@kfintech.example"),
        ).fetchall()
    ]
    if not users:
        return
    ideas = [
        str(r["id"])
        for r in conn.execute(
            "SELECT i.id FROM ideas i JOIN contributor_map cm ON cm.contributor_code = i.contributor_code "
            "WHERE cm.user_id = ANY(%s::uuid[])",
            (users,),
        ).fetchall()
    ]
    scopes = [scope_for(i) for i in ideas]
    conn.execute("DELETE FROM pseudonym_vault WHERE scope_id = ANY(%s::text[])", (scopes,))
    conn.execute("DELETE FROM vault_counters WHERE scope_id = ANY(%s::text[])", (scopes,))
    conn.execute("DELETE FROM llm_calls WHERE ref_id = ANY(%s::text[])", (scopes,))
    conn.execute("DELETE FROM llm_cache WHERE agent = 'gatekeeper' AND created_at >= %s", (since,))
    conn.execute(
        "DELETE FROM jobs WHERE type = 'hide.recheck' AND payload->>'idea_uuid' = ANY(%s::text[])", (ideas,)
    )
    conn.execute("DELETE FROM ideas WHERE id = ANY(%s::uuid[])", (ideas,))
    remove_people(conn, users)


def made_up() -> tuple[str, str, str, str]:
    """A folio, PAN and phone made up for this test (their last two characters fixed, so the masks read the same),
    and the words that hold them."""
    folio = f"{secrets.randbelow(9_000_000) + 1_000_000}/89"
    pan = f"ABCPK{secrets.randbelow(900) + 100}4F"
    phone = f"98{secrets.randbelow(900_000) + 100_000}10"
    return folio, pan, phone, f"SIP failed for the investor. Folio {folio}, PAN {pan}, call {phone} after 6."


def made_up_name() -> str:
    """A customer's name made up for this test: "Kiran" and a surname no other row holds."""
    return "Kiran Ra" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(4))


def person(conn: Any) -> tuple[str, str]:
    suffix = secrets.token_hex(3)
    uid = str(
        conn.execute(
            "INSERT INTO users (emp_id_hash, name, email, source) VALUES (%s, %s, %s, 'sign_in') RETURNING id",
            (f"test:{suffix}", f"Synthetic Tester {suffix}", f"tester.{suffix}@kfintech.example"),
        ).fetchone()["id"]
    )
    code = f"CTR-{suffix}"
    conn.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, uid))
    return uid, code


def idea(conn: Any, code: str, *, shared: bool = False, title: str = "SIP mandates fail at capture") -> str:
    row = conn.execute(
        "INSERT INTO ideas (contributor_code, status, kind, title, summary, idea_id) "
        "VALUES (%s, %s, 'problem', %s, 'Mandates bounce for missing bank fields', "
        "CASE WHEN %s THEN next_idea_ref() END) RETURNING id",
        (code, "with_review_desk" if shared else "draft", title, shared),
    ).fetchone()
    return str(row["id"])


def message(
    conn: Any, idea_uuid: str, uid: str, text: str, seq: int = 1, *, gatekeeper: bool = False
) -> tuple[str, Any]:
    mid = str(uuid.uuid4())
    with conn.transaction():  # the hide and the write of its masked copy, together
        out = hide_message(conn, idea_uuid, text, by=uid, source_id=mid, gatekeeper=gatekeeper)
        conn.execute(
            "INSERT INTO idea_messages (id, idea_uuid, seq, via, text_encrypted, char_count) "
            "VALUES (%s, %s, %s, 'typed', %s, %s)",
            (mid, idea_uuid, seq, seal_text("idea_messages", "text_encrypted", mid, out.masked), len(text)),
        )
    return mid, out


def conversation(conn: Any, idea_uuid: str, author: str, text: str) -> tuple[str, Any]:
    """Lane F's conversation message: hidden with the entry's id and the author's users.id, then stored masked."""
    eid = str(uuid.uuid4())
    with conn.transaction():
        out = hide_message(
            conn, idea_uuid, text, by=author, source="conversation", source_id=eid, gatekeeper=False
        )
        conn.execute(
            "INSERT INTO conversation_entries (id, idea_uuid, type, author_user_id, text_encrypted) "
            "VALUES (%s, %s, 'message', %s, %s)",
            (eid, idea_uuid, author, seal_text("conversation_entries", "text_encrypted", eid, out.masked)),
        )
    return eid, out


def answer(conn: Any, idea_uuid: str, reviewer: str, uid: str, code: str, text: str) -> tuple[str, str, Any]:
    """A desk question (masked by `hide_text`) and the sharer's answer (hidden as an answer). Returns ids and result."""
    qid, aid = str(uuid.uuid4()), str(uuid.uuid4())
    with conn.transaction():
        set_id = conn.execute(
            "INSERT INTO question_sets (idea_uuid, by_user_id) VALUES (%s, %s) RETURNING id",
            (idea_uuid, reviewer),
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO questions (id, set_id, seq, part, text_encrypted) VALUES (%s, %s, 1, 'who', %s)",
            (qid, set_id, seal_text("questions", "text_encrypted", qid, "Who else is affected?")),
        )
        out = hide_message(conn, idea_uuid, text, by=uid, source="answer", source_id=aid, gatekeeper=False)
        conn.execute(
            "INSERT INTO answers (id, question_id, by_code, text_encrypted) VALUES (%s, %s, %s, %s)",
            (aid, qid, code, seal_text("answers", "text_encrypted", aid, out.masked)),
        )
    return qid, aid, out


def masked_message(conn: Any, mid: str) -> str:
    return masked_in(conn, "idea_messages", mid)


def masked_in(conn: Any, table: str, row_id: str) -> str:
    row = conn.execute(f"SELECT text_encrypted FROM {table} WHERE id = %s", (row_id,)).fetchone()  # noqa: S608
    text = open_text(table, "text_encrypted", row_id, row["text_encrypted"])
    assert text is not None
    return text


def test_l_hide_rules_3_4_the_masked_copy_is_all_others_get_and_no_value_is_stored_in_clear(hdb: Any) -> None:
    db = hdb
    FOLIO, PAN, PHONE, WORDS = made_up()
    uid, code = person(db)
    iid = idea(db, code)
    mid, out = message(db, iid, uid, WORDS)
    assert (
        out.masked
        == "SIP failed for the investor. Folio Folio ••••89, PAN PAN ••••4F, call Phone ••••10 after 6."
    )
    assert (
        out.receipt == "Hid 3 personal details from everyone but you: Folio ••••89, PAN ••••4F, Phone ••••10."
    )
    assert out.kinds_line == "Folio number, PAN and phone number"
    assert [(s["kind"], WORDS[s["start"] : s["end"]]) for s in out.spans] == [
        ("folio", FOLIO), ("pan", PAN), ("phone", PHONE),
    ]  # fmt: skip
    for value in (FOLIO, PAN, PHONE):
        assert helpers.tables_containing(db, value) == [], value  # encrypted or masked everywhere
    assert own_words(db, "message", mid, idea_uuid=iid) == WORDS  # the person's own copy, worker only
    tags = {
        r["vault_tag"]
        for r in db.execute("SELECT vault_tag FROM hidden_details WHERE idea_uuid = %s", (iid,))
    }
    values = {t: v for t, (_, v) in vault.mapping(db, scope_for(iid)).items() if t in tags}
    assert sorted(values.values()) == sorted([FOLIO, PAN, PHONE])
    audit = db.execute(
        "SELECT after FROM audit_log WHERE action = 'hide.detected' AND entity = %s", (f"idea:{iid}",)
    ).fetchone()
    assert audit["after"]["kinds"] == {"folio": 1, "pan": 1, "phone": 1}
    assert masked_message(db, mid) == out.masked


def test_l_hide_rules_6_show_needs_a_reason_and_an_edit_keeps_the_choice(hdb: Any) -> None:
    db = hdb
    _, PAN, _, WORDS = made_up()
    uid, code = person(db)
    other, _ = person(db)
    iid = idea(db, code)
    mid, out = message(db, iid, uid, WORDS)
    pan_id = next(d["id"] for d in out.details if d["kind"] == "pan")
    with pytest.raises(HideError) as missing:
        show(db, iid, pan_id, reason="because", by=uid)
    assert missing.value.code == "reason_required"
    with pytest.raises(HideError) as not_theirs:
        show(db, iid, pan_id, reason="made_up_example", by=other)
    assert not_theirs.value.code == "not_found"
    shown = show(db, iid, pan_id, reason="made_up_example", by=uid)
    assert shown["state"] == "shown" and shown["reason"] == "made_up_example" and "shown_at" in shown
    assert PAN in masked_message(db, mid) and "Folio ••••89" in masked_message(db, mid)
    audit = db.execute(
        "SELECT reason, after FROM audit_log WHERE action = 'hide.shown' AND entity = %s", (f"idea:{iid}",)
    ).fetchone()
    assert audit["reason"] == "made_up_example" and PAN not in str(audit["after"])

    with db.transaction():
        again = hide_message(db, iid, WORDS + " Thanks.", by=uid, source_id=mid, gatekeeper=False)
    kept = next(d for d in again.details if d["kind"] == "pan")
    assert kept["id"] == pan_id and kept["state"] == "shown"
    assert PAN in again.masked and again.hidden_count == 2

    hidden = hide_again(db, iid, pan_id, by=uid)
    assert hidden["state"] == "hidden" and "reason" not in hidden
    assert PAN not in masked_message(db, mid)


def test_l_hide_rules_1_hide_text_for_desk_written_text(hdb: Any) -> None:
    db = hdb
    FOLIO = made_up()[0]
    reviewer, _ = person(db)
    _, code = person(db)
    iid = idea(db, code, shared=True)
    masked, count = hide_text(
        db, iid, f"Please add a screenshot of folio {FOLIO} with it hidden", by=reviewer
    )
    assert masked == "Please add a screenshot of folio Folio ••••89 with it hidden" and count == 1
    row = db.execute("SELECT source, found_by FROM hidden_details WHERE idea_uuid = %s", (iid,)).fetchone()
    assert (row["source"], row["found_by"]) == ("desk", "patterns")


def test_l_hide_rules_7_the_desk_hides_a_missed_name_in_every_copy(hdb: Any) -> None:
    db = hdb
    FOLIO = made_up()[0]
    NAME = made_up_name()
    MASK = mask("name", NAME)
    reviewer, _ = person(db)
    uid, code = person(db)
    iid = idea(db, code, shared=True, title=f"{NAME} waits for SIP refunds")
    text = f"The agent {NAME} keeps asking. It is about folio {FOLIO} every week"
    mid, _ = message(db, iid, uid, text)
    m2, _ = message(db, iid, uid, f"{NAME} said the same on Monday", seq=2)
    seen = masked_message(db, mid)
    start = seen.index(NAME)
    detail = desk_hide(
        db, iid, source_kind="message", source_id=mid, start=start, end=start + len(NAME), by=reviewer
    )
    assert detail["kind"] == "name" and detail["masked"] == MASK and detail["state"] == "hidden"
    assert NAME not in masked_message(db, mid) and NAME not in masked_message(db, m2)
    assert db.execute("SELECT title FROM ideas WHERE id = %s", (iid,)).fetchone()["title"].startswith(MASK)
    assert own_words(db, "message", mid, idea_uuid=iid) == text  # the sharer's own words are unchanged
    rows = db.execute(
        "SELECT source, source_id, found_by FROM hidden_details WHERE idea_uuid = %s AND kind = 'name'",
        (iid,),
    ).fetchall()
    assert {(r["source"], str(r["source_id"]), r["found_by"]) for r in rows} == {
        ("message", mid, "reviewer"), ("message", m2, "reviewer"), ("title", "title", "reviewer"),
    }  # fmt: skip
    audit = db.execute(
        "SELECT actor, after FROM audit_log WHERE action = 'hide.desk_hidden' AND entity = %s",
        (f"idea:{iid}",),
    ).fetchone()
    assert audit["actor"] == f"user:{reviewer}" and "Kiran" not in str(audit["after"])
    assert "sharer_notified" in audit["after"]  # posted once lane A's notify knows the kind (BLD-C063)
    assert helpers.tables_containing(db, NAME) == []

    with pytest.raises(HideError) as twice:
        desk_hide(db, iid, source_kind="message", source_id=mid, start=start, end=start + 4, by=reviewer)
    assert twice.value.code == "already_hidden"
    with pytest.raises(HideError) as outside:
        desk_hide(db, iid, source_kind="message", source_id=mid, start=0, end=10_000, by=reviewer)
    assert outside.value.code == "range_invalid"

    # A new message on the same idea hides the value too, in any case.
    _, later = message(db, iid, uid, f"{NAME.lower()} again", seq=3)
    assert later.masked == f"{mask('name', NAME.lower())} again"


def test_l_hide_rules_7_the_sweep_reaches_every_copy_as_whole_words_in_any_case(hdb: Any) -> None:
    """Review fix 1 and 3 (BLD-C066): a value the desk hides in a message is masked in the answers, the
    conversation, the title, summary, how-often and helper lines, the fix, the parts, the desk's questions, the
    saved versions, the similar-idea reasons and the draft's receipts, each with a hidden_details row; "kiran …"
    goes with "Kiran …", and a longer word that starts the same stays."""
    db = hdb
    NAME = made_up_name()
    LOWER = NAME.lower()
    reviewer, _ = person(db)
    crew, _ = person(db)
    uid, code = person(db)
    iid = idea(db, code, shared=True, title=f"Refunds for {NAME} are late")
    other = idea(db, code, shared=True, title="Mandate bounces at capture")
    db.execute(
        "UPDATE ideas SET summary = %s, often = %s, helper_text = %s WHERE id = %s",
        (f"{LOWER} waits a week", f"Every time {NAME} calls", f"Ask {NAME} what she sent", iid),
    )
    db.execute(
        "INSERT INTO idea_fix (idea_uuid, how, needs, solved_note, risks) VALUES (%s, %s, %s, %s, %s)",
        (iid, f"Call {NAME} back", f"{NAME}'s branch", f"Not for {LOWER}", f"{NAME} complains"),
    )
    db.execute(
        "INSERT INTO idea_parts (idea_uuid, key, state, value, why, source_quote) VALUES "
        "(%s, 'who', 'filled', %s::jsonb, %s, %s)",
        (iid, f'["Investors like {NAME}"]', f"{NAME} is named", f"the agent {NAME} keeps asking"),
    )
    context = sealed_context("idea_versions", "snapshot_encrypted", f"{iid}:1")
    db.execute(
        "INSERT INTO idea_versions (idea_uuid, n, changed_fields, snapshot_encrypted) VALUES (%s, 1, '{title}', %s)",
        (iid, encrypt_json({"n": 1, "before": {"title": f"{NAME} waits"}}, context)),
    )
    db.execute(
        "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason) VALUES (%s, %s, 'related', %s)",
        (other, iid, f"Both mention {NAME}"),
    )
    run_id = db.execute(
        "INSERT INTO draft_runs (idea_uuid, state, receipt) VALUES (%s, 'done', %s::jsonb) RETURNING id",
        (iid, f'["Noted that {NAME} waits"]'),
    ).fetchone()["id"]
    mid, _ = message(db, iid, uid, f"The agent {NAME} keeps asking, and {NAME}son too")
    qid, aid, _ = answer(db, iid, reviewer, uid, code, f"Only {LOWER} so far")
    eid, _ = conversation(db, iid, crew, f"I spoke to {NAME} today")
    db.execute(
        "UPDATE questions SET text_encrypted = %s WHERE id = %s",
        (seal_text("questions", "text_encrypted", qid, f"Is {NAME} the only one?"), qid),
    )

    seen = masked_message(db, mid)
    start = seen.index(NAME)
    desk_hide(db, iid, source_kind="message", source_id=mid, start=start, end=start + len(NAME), by=reviewer)

    for needle in (NAME, LOWER):
        assert helpers.tables_containing(db, needle) == [], needle
    assert masked_message(db, mid).endswith(f"{mask('name', NAME)} keeps asking, and {NAME}son too")
    assert LOWER not in masked_in(db, "answers", aid) and NAME not in masked_in(
        db, "conversation_entries", eid
    )
    assert NAME not in masked_in(db, "questions", qid)
    snap = decrypt_json(bytes(db.execute("SELECT snapshot_encrypted FROM idea_versions WHERE idea_uuid = %s",
                                          (iid,)).fetchone()["snapshot_encrypted"]), context)  # fmt: skip
    assert NAME not in str(snap) and snap["before"]["title"].startswith("Name ••••")
    rows = db.execute(
        "SELECT DISTINCT source, source_id FROM hidden_details WHERE idea_uuid = %s AND found_by = 'reviewer'",
        (iid,),
    ).fetchall()
    assert {(r["source"], str(r["source_id"])) for r in rows} == {
        ("message", mid), ("answer", aid), ("conversation", eid), ("title", "title"), ("title", "summary"),
        ("title", "often"), ("title", "helper_text"), ("fix", "how"), ("fix", "needs"), ("fix", "solved_note"),
        ("fix", "risks"), ("part", "who"), ("desk", qid), ("version", "1"), ("similar", other),
        ("run", str(run_id)),
    }  # fmt: skip
    assert own_words(db, "conversation", eid, idea_uuid=iid) == f"I spoke to {NAME} today"  # the author's own


def test_l_hide_rules_7_a_selection_needs_three_characters_and_fix_and_conversation_are_desk_sources(
    hdb: Any,
) -> None:
    """Review fix 3 and 9: "a" or "5" is refused; the fix and lane F's conversation can be hidden from."""
    db = hdb
    NAME = made_up_name()
    reviewer, _ = person(db)
    crew, _ = person(db)
    uid, code = person(db)
    iid = idea(db, code, shared=True, title="A 5 day wait for refunds")
    for start, end in ((0, 1), (2, 3), (1, 2)):
        with pytest.raises(HideError) as short:
            desk_hide(db, iid, source_kind="title", source_id="title", start=start, end=end, by=reviewer)
        assert short.value.code == "range_invalid"
    db.execute("INSERT INTO idea_fix (idea_uuid, how) VALUES (%s, %s)", (iid, f"Ask {NAME} to resend"))
    d = desk_hide(db, iid, source_kind="fix", source_id="how", start=4, end=4 + len(NAME), by=reviewer)
    assert d["kind"] == "name"
    how = db.execute("SELECT how FROM idea_fix WHERE idea_uuid = %s", (iid,)).fetchone()["how"]
    assert how == f"Ask {mask('name', NAME)} to resend"
    with pytest.raises(HideError) as no_field:
        desk_hide(db, iid, source_kind="fix", source_id="basis", start=0, end=4, by=reviewer)
    assert no_field.value.code == "not_found"

    eid, out = conversation(db, iid, crew, "The branch at Ward 7 sent it back")
    start = out.masked.index("Ward 7")
    c = desk_hide(db, iid, source_kind="conversation", source_id=eid, start=start, end=start + 6, by=reviewer)
    assert c["kind"] == "name" and "Ward 7" not in masked_in(db, "conversation_entries", eid)
    _ = uid


def test_l_hide_rules_2_7_the_browsers_offsets_after_an_emoji(hdb: Any) -> None:
    """Review fix 8 (BLD-C068): the desk's range in UTF-16 units (an emoji counts twice) hides the right words."""
    db = hdb
    NAME = made_up_name()
    reviewer, _ = person(db)
    uid, code = person(db)
    iid = idea(db, code, shared=True)
    text = f"Refund late 😀 for {NAME} again"
    mid, _ = message(db, iid, uid, text)
    seen = masked_message(db, mid)
    at = seen.index(NAME)
    start, end = to_utf16(seen, at), to_utf16(seen, at + len(NAME))
    assert start == at + 1  # the browser's count
    desk_hide(db, iid, source_kind="message", source_id=mid, start=start, end=end, by=reviewer, units="utf16")
    assert masked_message(db, mid) == f"Refund late 😀 for {mask('name', NAME)} again"
    with pytest.raises(HideError) as split:
        e = seen.index("😀")
        desk_hide(
            db, iid, source_kind="message", source_id=mid, start=e + 1, end=e + 6, by=reviewer, units="utf16"
        )
    assert split.value.code == "range_invalid"


def test_l_hide_rules_6_show_it_is_refused_on_what_the_desk_hid(hdb: Any) -> None:
    """Review fix 4: the desk's hide wins. A detail the desk found, or one the owner had shown and the desk hid
    again, cannot be shown (nor its "Hide it" changed) by the owner."""
    db = hdb
    _, PAN, _, WORDS = made_up()
    NAME = made_up_name()
    reviewer, _ = person(db)
    uid, code = person(db)
    iid = idea(db, code, shared=True)
    mid, out = message(db, iid, uid, f"{WORDS} {NAME} sent it.")
    seen = masked_message(db, mid)
    start = seen.index(NAME)
    found = desk_hide(
        db, iid, source_kind="message", source_id=mid, start=start, end=start + len(NAME), by=reviewer
    )
    with pytest.raises(HideError) as refused:
        show(db, iid, found["id"], reason="made_up_example", by=uid)
    assert (refused.value.status, refused.value.code) == (403, "forbidden")
    with pytest.raises(HideError) as refused_again:
        hide_again(db, iid, found["id"], by=uid)
    assert (refused_again.value.status, refused_again.value.code) == (403, "forbidden")

    pan_id = next(d["id"] for d in out.details if d["kind"] == "pan")
    show(db, iid, pan_id, reason="made_up_example", by=uid)
    seen = masked_message(db, mid)
    assert PAN in seen
    at = seen.index(PAN)
    again = desk_hide(db, iid, source_kind="message", source_id=mid, start=at, end=at + len(PAN), by=reviewer)
    assert again["id"] == pan_id and again["state"] == "hidden" and PAN not in masked_message(db, mid)
    with pytest.raises(HideError) as refused_pan:
        show(db, iid, pan_id, reason="made_up_example", by=uid)
    assert refused_pan.value.code == "forbidden"


def test_l_hide_rules_7_title_and_part_and_drafts_are_not_for_the_desk(hdb: Any) -> None:
    db = hdb
    FOLIO = made_up()[0]
    reviewer, _ = person(db)
    uid, code = person(db)
    iid = idea(db, code, shared=True, title=f"Folio {FOLIO} shows the wrong nominee")
    db.execute(
        "INSERT INTO idea_parts (idea_uuid, key, state, value) VALUES (%s, 'who', 'filled', %s::jsonb)",
        (iid, '["Investors", "Meena Pillai at the branch"]'),
    )
    d = desk_hide(db, iid, source_kind="title", source_id="title", start=6, end=6 + len(FOLIO), by=reviewer)
    assert (
        d["kind"] == "folio"
        and db.execute("SELECT title FROM ideas WHERE id = %s", (iid,)).fetchone()["title"]
        == "Folio Folio ••••89 shows the wrong nominee"
    )
    p = desk_hide(db, iid, source_kind="part", source_id="who.1", start=0, end=12, by=reviewer)
    assert p["masked"] == "Name ••••ai"
    value = db.execute(
        "SELECT value FROM idea_parts WHERE idea_uuid = %s AND key = 'who'", (iid,)
    ).fetchone()["value"]
    assert value == ["Investors", "Name ••••ai at the branch"]

    draft = idea(db, code)
    with pytest.raises(HideError) as hidden_draft:
        desk_hide(db, draft, source_kind="title", source_id="title", start=0, end=3, by=reviewer)
    assert hidden_draft.value.code == "not_found"
    _ = uid


def test_l_hide_rules_4_the_scope_is_the_idea_row_so_show_it_still_works_after_send(hdb: Any) -> None:
    """The draft and the shared idea are one `ideas` row; values sit under `DRAFT-<idea uuid>` before and after send."""
    db = hdb
    FOLIO, _, _, WORDS = made_up()
    uid, code = person(db)
    iid = idea(db, code)
    mid, out = message(db, iid, uid, WORDS)
    assert scope_for(iid) == f"DRAFT-{iid}"
    db.execute(
        "UPDATE ideas SET status = 'checking', idea_id = next_idea_ref() WHERE id = %s", (iid,)
    )  # send
    folio_id = next(d["id"] for d in out.details if d["kind"] == "folio")
    shown = show(db, iid, folio_id, reason="internal_reference", by=uid)
    assert shown["state"] == "shown" and FOLIO in masked_message(db, mid)
    tag = db.execute("SELECT vault_tag FROM hidden_details WHERE id = %s", (folio_id,)).fetchone()[
        "vault_tag"
    ]
    assert vault.mapping(db, scope_for(iid))[tag][1] == FOLIO  # still resolves after send
    masked, count = hide_text(db, iid, f"Folio {FOLIO} again", by=uid, source="desk")
    assert count == 1 and masked == "Folio Folio ••••89 again"
    tags = db.execute(
        "SELECT DISTINCT vault_tag FROM hidden_details WHERE idea_uuid = %s AND kind = 'folio'", (iid,)
    )
    assert {r["vault_tag"] for r in tags} == {
        tag
    }  # the same value keeps one tag across draft and shared idea


def test_l_hide_rules_4_sealed_words_of_two_ideas_never_meet(hdb: Any) -> None:
    """Review fix 2 (BLD-C066): two ideas' "version 2" edits keep their own words; ids that are row ids or already
    start with the idea's uuid are kept as they are, so callers that remove their rows by id still find them."""
    db = hdb
    a_uid, a_code = person(db)
    b_uid, b_code = person(db)
    a, b = idea(db, a_code, shared=True), idea(db, b_code, shared=True)
    folio_a, folio_b = made_up()[0], made_up()[0]
    with db.transaction():
        hide_message(
            db, a, f"Folio {folio_a} for A", by=a_uid, source="edit", source_id="2", gatekeeper=False
        )
    with db.transaction():
        hide_message(
            db, b, f"Folio {folio_b} for B", by=b_uid, source="edit", source_id="2", gatekeeper=False
        )
    assert own_words(db, "edit", "2", idea_uuid=a) == f"Folio {folio_a} for A"
    assert own_words(db, "edit", "2", idea_uuid=b) == f"Folio {folio_b} for B"
    keys = db.execute(
        "SELECT idea_uuid, source_id, owner_user_id FROM idea_words_sealed WHERE idea_uuid = ANY(%s::uuid[])",
        ([a, b],),
    ).fetchall()
    assert {(str(r["idea_uuid"]), r["source_id"], str(r["owner_user_id"])) for r in keys} == {
        (a, f"{a}:2", a_uid), (b, f"{b}:2", b_uid),
    }  # fmt: skip
    row_id, prefixed = str(uuid.uuid4()), f"{a}:3:fix.how"
    assert sealed_key(a, row_id) == row_id and sealed_key(a, prefixed) == prefixed
    with pytest.raises(HideError) as theirs, db.transaction():  # another person's row is never overwritten
        hide_message(db, a, f"Folio {folio_b}", by=b_uid, source="edit", source_id="2", gatekeeper=False)
    assert theirs.value.code == "conflict"
    assert own_words(db, "edit", "2", idea_uuid=a) == f"Folio {folio_a} for A"


def test_l_hide_rules_1_lane_fs_conversation_and_an_answer_are_hidden_for_their_authors(hdb: Any) -> None:
    """Review fix 7: a conversation message (lane F: the entry's id, the author's users.id) and an answer keep their
    authors' words sealed for them, and only the author may show a detail of theirs."""
    db = hdb
    FOLIO, PAN, _, _ = made_up()
    reviewer, _ = person(db)
    crew, _ = person(db)
    uid, code = person(db)
    iid = idea(db, code, shared=True)
    eid, said = conversation(db, iid, crew, f"Folio {FOLIO} came back again")
    assert said.masked == "Folio Folio ••••89 came back again" and said.hidden_count == 1
    assert masked_in(db, "conversation_entries", eid) == said.masked
    assert own_words(db, "conversation", eid, idea_uuid=iid) == f"Folio {FOLIO} came back again"
    owner = db.execute(
        "SELECT owner_user_id FROM idea_words_sealed WHERE source = 'conversation' AND source_id = %s", (eid,)
    ).fetchone()["owner_user_id"]
    assert str(owner) == crew
    hid = said.details[0]["id"]
    with pytest.raises(HideError) as not_sharers:
        show(db, iid, hid, reason="internal_reference", by=uid)
    assert not_sharers.value.code == "not_found"
    assert show(db, iid, hid, reason="internal_reference", by=crew)["state"] == "shown"
    assert FOLIO in masked_in(db, "conversation_entries", eid)

    _, aid, ans = answer(db, iid, reviewer, uid, code, f"PAN {PAN} was on the form")
    assert ans.masked == "PAN PAN ••••4F was on the form"
    assert masked_in(db, "answers", aid) == ans.masked
    assert own_words(db, "answer", aid, idea_uuid=iid) == f"PAN {PAN} was on the form"
    assert helpers.tables_containing(db, PAN) == []


ADDRESS = "Flat 12, Green Park, Pune"


def gatekeeper_output(**personal: Any) -> dict[str, Any]:
    from gateway.spec import load

    out = dict(load("gatekeeper").example("01-problem-clean.json").output)
    out["personal_data"] = personal or {"found": False, "confidence": 0.9, "spans": []}
    return out


def address_found() -> dict[str, Any]:
    span = {
        "field": "details",
        "quote": ADDRESS,
        "data_type": "address",
        "confidence": 0.9,
        "reason": "Home address",
    }
    return gatekeeper_output(found=True, confidence=0.9, spans=[span])


def test_l_hide_detect_the_gatekeeper_runs_in_fake_mode_and_not_when_the_assistant_is_off(hdb: Any) -> None:
    """Review fix 7: with gatekeeper=True the gateway's finds are hidden (found_by gatekeeper); with ai.all off no
    model is called and the patterns still run."""
    from core import killswitch
    from gateway.routes import FAKE_SCRIPT

    db = hdb
    FOLIO = made_up()[0]
    uid, code = person(db)
    iid = idea(db, code)
    FAKE_SCRIPT.append(address_found())
    mid, out = message(db, iid, uid, f"Forms come back from {ADDRESS} every week", gatekeeper=True)
    assert out.masked == "Forms come back from Name ••••ne every week"
    row = db.execute("SELECT found_by, kind FROM hidden_details WHERE source_id = %s", (mid,)).fetchone()
    assert (row["found_by"], row["kind"]) == ("gatekeeper", "name")
    calls = db.execute("SELECT count(*) AS n FROM llm_calls WHERE ref_id = %s", (scope_for(iid),)).fetchone()[
        "n"
    ]
    assert calls >= 1

    db.execute("UPDATE kill_switches SET state = 'off' WHERE name = 'ai.all'")
    killswitch.clear_cache()
    try:
        _, off = message(db, iid, uid, f"Forms from {ADDRESS}, folio {FOLIO}", seq=2, gatekeeper=True)
    finally:
        db.execute("UPDATE kill_switches SET state = 'on' WHERE name = 'ai.all'")
        killswitch.clear_cache()
    assert (
        off.masked == "Forms from Name ••••ne, folio Folio ••••89"
    )  # the gatekeeper's earlier find, as a known value
    after = db.execute("SELECT count(*) AS n FROM llm_calls WHERE ref_id = %s", (scope_for(iid),)).fetchone()[
        "n"
    ]
    assert after == calls  # no model call with the assistant off


def test_l_hide_detect_a_gatekeeper_failure_is_audited_and_rechecked(hdb: Any) -> None:
    """Review fix 5 (BLD-C067): the text goes on with the patterns, `hide.gatekeeper_skipped` is audited with IDs
    and the code only, a `hide.recheck` job is queued, and the re-check hides what the gatekeeper finds in the
    message and in every other copy."""
    from gateway.routes import FAKE_SCRIPT, RouteError

    db = hdb
    uid, code = person(db)
    iid = idea(db, code, shared=True, title=f"Forms lost at {ADDRESS}")
    FAKE_SCRIPT.append(RouteError("connection"))
    mid, out = message(db, iid, uid, f"Forms come back from {ADDRESS} every week", gatekeeper=True)
    assert out.masked == f"Forms come back from {ADDRESS} every week" and out.hidden_count == 0
    skipped = db.execute(
        "SELECT after FROM audit_log WHERE action = 'hide.gatekeeper_skipped' AND entity = %s",
        (f"idea:{iid}",),
    ).fetchone()["after"]
    assert skipped["code"] == "connection" and skipped["source_id"] == mid and ADDRESS not in str(skipped)
    job = db.execute(
        "SELECT id, payload FROM jobs WHERE type = 'hide.recheck' AND payload->>'idea_uuid' = %s", (iid,)
    ).fetchone()
    assert job is not None and skipped["recheck_job"] == job["id"]
    assert job["payload"] == {"idea_uuid": iid, "source": "message", "source_id": mid, "by": uid}

    FAKE_SCRIPT.append(RouteError("connection"))
    with pytest.raises(Exception) as still_down:
        hide_recheck.run(db, job["payload"])
    assert type(still_down.value).__name__ == "GatekeeperUnavailable"

    FAKE_SCRIPT.append(address_found())
    hide_recheck.run(db, job["payload"])
    assert masked_message(db, mid) == "Forms come back from Name ••••ne every week"
    title = db.execute("SELECT title FROM ideas WHERE id = %s", (iid,)).fetchone()["title"]
    assert title == "Forms lost at Name ••••ne"
    assert helpers.tables_containing(db, ADDRESS) == []
    assert own_words(db, "message", mid, idea_uuid=iid) == f"Forms come back from {ADDRESS} every week"


def test_l_hide_rules_1_a_failure_inside_leaves_the_callers_transaction_usable(
    hdb: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review fix 7: hide's work runs in savepoints, so the caller can carry on (and roll back) after a failure."""
    import hide.core

    db = hdb
    FOLIO = made_up()[0]
    uid, code = person(db)
    iid = idea(db, code)

    def broken_audit(conn: Any, *args: Any, **kwargs: Any) -> None:
        conn.execute("SELECT 1 / 0")

    monkeypatch.setattr(hide.core, "audit", broken_audit)
    mid = str(uuid.uuid4())
    with db.transaction():
        with pytest.raises(psycopg.errors.DivisionByZero):
            hide_message(db, iid, f"Folio {FOLIO}", by=uid, source_id=mid, gatekeeper=False)
        assert db.execute("SELECT 1 AS one").fetchone()["one"] == 1  # still usable
        left = db.execute("SELECT count(*) AS n FROM hidden_details WHERE source_id = %s", (mid,)).fetchone()[
            "n"
        ]
        assert left == 0  # nothing of the failed hide stayed


def count(conn: Any, sql: str, *args: Any) -> int:
    return int(conn.execute(sql, args).fetchone()["n"])


def test_l_hide_rules_4_l_convo_10_forget_drops_a_removed_entry_and_keeps_a_value_another_text_holds(
    hdb: Any,
) -> None:
    """J (lane F's L-CONVO/10, BLD-C066): `forget` drops a removed conversation message's details, its sealed words
    and the vault values only it held. A value also hidden in another message stays, with that message's detail and
    words. An edit's version id is found under the idea's uuid. Audited with IDs and counts only."""
    db = hdb
    FOLIO, PAN, _, _ = made_up()
    crew, _ = person(db)
    uid, code = person(db)
    iid = idea(db, code, shared=True)
    gone, said = conversation(db, iid, crew, f"Folio {FOLIO} came back. PAN {PAN} was on the form")
    kept, _ = conversation(db, iid, crew, f"PAN {PAN} again")
    assert said.counts == {"folio": 1, "pan": 1}
    scope = scope_for(iid)
    tag_of = {v: t for t, (_, v) in vault.mapping(db, scope).items()}
    assert {FOLIO, PAN} <= set(tag_of)
    entity = f"idea:{iid}"
    audits = "SELECT count(*) AS n FROM audit_log WHERE action = 'hide.forgotten' AND entity = %s"
    before = count(db, audits, entity)
    vault_before = count(db, "SELECT count(*) AS n FROM pseudonym_vault WHERE scope_id = %s", scope)

    with db.transaction():  # the removal and the forgetting, together; hide's lock first
        removed = forget(db, iid, source="conversation", source_id=gone)
        db.execute("DELETE FROM conversation_entries WHERE id = %s", (gone,))
    assert removed == 2
    assert (
        count(
            db, "SELECT count(*) AS n FROM hidden_details WHERE idea_uuid = %s AND source_id = %s", iid, gone
        )
        == 0
    )
    assert own_words(db, "conversation", gone, idea_uuid=iid) is None
    assert count(db, "SELECT count(*) AS n FROM idea_words_sealed WHERE source_id = %s", gone) == 0
    values = {v for _, (_, v) in vault.mapping(db, scope).items()}
    assert FOLIO not in values and PAN in values
    assert (
        count(db, "SELECT count(*) AS n FROM pseudonym_vault WHERE scope_id = %s", scope) == vault_before - 1
    )
    still = db.execute(
        "SELECT kind, vault_tag FROM hidden_details WHERE idea_uuid = %s AND source_id = %s", (iid, kept)
    ).fetchall()
    assert [(r["kind"], r["vault_tag"]) for r in still] == [("pan", tag_of[PAN])]
    assert own_words(db, "conversation", kept, idea_uuid=iid) == f"PAN {PAN} again"
    assert count(db, audits, entity) == before + 1
    row = db.execute(
        "SELECT actor, after FROM audit_log WHERE action = 'hide.forgotten' AND entity = %s ORDER BY id DESC LIMIT 1",
        (entity,),
    ).fetchone()
    assert row["actor"] == "system"
    assert row["after"] == {"source": "conversation", "source_id": gone, "hidden": 2, "sealed": 1, "vault": 1}
    assert FOLIO not in str(row["after"]) and PAN not in str(row["after"])

    with db.transaction():
        hide_message(db, iid, f"Folio {FOLIO} fixed", by=uid, source="edit", source_id="2", gatekeeper=False)
    with db.transaction():
        assert forget(db, iid, source="edit", source_id="2") == 1
    assert own_words(db, "edit", "2", idea_uuid=iid) is None
    assert FOLIO not in {v for _, (_, v) in vault.mapping(db, scope).items()}
    assert forget(db, iid, source="edit", source_id="2") == 0  # nothing left: nothing audited
    assert count(db, audits, entity) == before + 2
    with pytest.raises(ValueError):
        forget(db, iid, source="nowhere", source_id=kept)


def test_l_hide_rules_7_stale_when_the_text_changed_under_the_selection(hdb: Any) -> None:
    """F (lane B's `selected`, BLD-C066): another hide moved the masked copy under the page, so the old range with the
    words the reviewer selected is refused with `stale` and nothing is hidden; read again, the same words hide. A
    title works the same; without `selected` a range off the text is still `range_invalid`; a selection over 300
    characters is `selection_too_long`."""
    db = hdb
    NAME, OTHER = made_up_name(), made_up_name()
    reviewer, _ = person(db)
    second, _ = person(db)
    uid, code = person(db)
    iid = idea(db, code, shared=True, title="A 5 day wait for refunds")
    mid, _ = message(db, iid, uid, f"Refund late 😀 for {OTHER} and then {NAME} again")
    seen = masked_message(db, mid)
    at, o = seen.index(NAME), seen.index(OTHER)
    start, end = to_utf16(seen, at), to_utf16(seen, at + len(NAME))
    desk_hide(
        db, iid, source_kind="message", source_id=mid, start=to_utf16(seen, o), end=to_utf16(seen, o + len(OTHER)),
        by=second, units="utf16", selected=OTHER,
    )  # fmt: skip
    details = "SELECT count(*) AS n FROM hidden_details WHERE idea_uuid = %s"
    before = count(db, details, iid)
    with pytest.raises(HideError) as stale:
        desk_hide(
            db, iid, source_kind="message", source_id=mid, start=start, end=end, by=reviewer, units="utf16",
            selected=NAME,
        )  # fmt: skip
    assert (stale.value.status, stale.value.code) == (409, "stale")
    assert count(db, details, iid) == before and NAME in masked_message(db, mid)
    now = masked_message(db, mid)
    at = now.index(NAME)
    d = desk_hide(
        db, iid, source_kind="message", source_id=mid, start=to_utf16(now, at), end=to_utf16(now, at + len(NAME)),
        by=reviewer, units="utf16", selected=f" {NAME} ",
    )  # fmt: skip
    assert d["masked"] == mask("name", NAME) and NAME not in masked_message(db, mid)

    with pytest.raises(HideError) as title_stale:
        desk_hide(
            db, iid, source_kind="title", source_id="title", start=2, end=7, by=reviewer, units="utf16",
            selected="9 day",
        )  # fmt: skip
    assert title_stale.value.code == "stale"
    with pytest.raises(HideError) as off_text:
        desk_hide(
            db, iid, source_kind="title", source_id="title", start=2, end=900, by=reviewer, units="utf16"
        )
    assert off_text.value.code == "range_invalid"
    long_id, _ = message(db, iid, uid, "Refunds wait. " * 30, seq=2)
    with pytest.raises(HideError) as too_long:
        desk_hide(
            db, iid, source_kind="message", source_id=long_id, start=0, end=301, by=reviewer, units="utf16",
            selected=("Refunds wait. " * 30)[:301],
        )  # fmt: skip
    assert (too_long.value.status, too_long.value.code) == (422, "selection_too_long")
    assert count(db, details, iid) == before + 1


def test_l_hide_rules_7_a_reviewer_never_hides_on_their_own_or_a_merged_in_idea(hdb: Any) -> None:
    """G (BLD-C066): as lane B's `refuse_own` and the desk page's `own`, a reviewer is refused with 403 `forbidden`
    on their own idea and on an idea their contribution was merged into; the refusal carries its audit row (IDs and
    the action only) and changes nothing. Another reviewer hides as usual."""
    db = hdb
    NAME = made_up_name()
    reviewer, r_code = person(db)
    other, _ = person(db)
    _, code = person(db)
    own = idea(db, r_code, shared=True, title=f"{NAME} waits for refunds")
    with pytest.raises(HideError) as mine:
        desk_hide(db, own, source_kind="title", source_id="title", start=0, end=len(NAME), by=reviewer)
    assert (mine.value.status, mine.value.code) == (403, "forbidden")
    assert mine.value.audit == (reviewer, "hide.own_idea_refused", own, {"action": "desk_hide"})

    lead = idea(db, code, shared=True, title=f"{NAME} waits again")
    db.execute(
        "INSERT INTO merges (lead_idea_uuid, merged_idea_uuid, via, by_user_id) VALUES (%s, %s, 'review_desk', %s)",
        (lead, own, other),
    )
    with pytest.raises(HideError) as merged:
        desk_hide(db, lead, source_kind="title", source_id="title", start=0, end=len(NAME), by=reviewer)
    assert (merged.value.status, merged.value.code) == (403, "forbidden")
    assert count(db, "SELECT count(*) AS n FROM hidden_details WHERE idea_uuid = %s", lead) == 0
    assert db.execute("SELECT title FROM ideas WHERE id = %s", (lead,)).fetchone()["title"].startswith(NAME)
    d = desk_hide(db, lead, source_kind="title", source_id="title", start=0, end=len(NAME), by=other)
    assert d["kind"] == "name"


def test_l_hide_detect_a_recheck_waits_while_the_assistant_is_off_and_is_audited_when_it_gives_up(
    hdb: Any,
) -> None:
    """B (BLD-C067, BLD-C231): a re-check queued while the assistant was on, run while `ai.all` is off, waits
    (`JobWaits`: its try is given back, as a file's check does) and calls no model, so a switch-off never uses up its
    tries. Back on with the gateway still down, its last attempt goes dead and is audited (`hide.recheck_gave_up`) with
    IDs and the code only, and its words are marked done, so the re-check sweep does not ask about them again."""
    import jobs.handlers  # noqa: F401 (registers hide.recheck and its on_dead)
    from core import killswitch
    from gateway.routes import FAKE_SCRIPT, RouteError
    from jobs.runner import JobWaits, run_one

    db = hdb
    uid, code = person(db)
    iid = idea(db, code, shared=True)
    FAKE_SCRIPT.append(RouteError("connection"))
    mid, out = message(db, iid, uid, f"Forms come back from {ADDRESS} every week", gatekeeper=True)
    job = db.execute(
        "SELECT id, payload, max_attempts FROM jobs WHERE type = 'hide.recheck' AND payload->>'idea_uuid' = %s",
        (iid,),
    ).fetchone()
    calls = "SELECT count(*) AS n FROM llm_calls WHERE ref_id = %s"
    calls_before = count(db, calls, scope_for(iid))
    gave = "SELECT count(*) AS n FROM audit_log WHERE action = 'hide.recheck_gave_up' AND entity = %s"
    gave_before = count(db, gave, f"idea:{iid}")
    state = "SELECT state, attempts, last_error FROM jobs WHERE id = %s"
    db.execute("UPDATE kill_switches SET state = 'off' WHERE name = 'ai.all'")
    killswitch.clear_cache()
    try:
        with pytest.raises(JobWaits) as off:
            hide_recheck.run(db, job["payload"])
        assert (off.value.code, off.value.seconds) == ("waiting_gatekeeper", 300)
        assert masked_message(db, mid) == out.masked  # nothing lost while it waits
        db.execute(
            "UPDATE jobs SET attempts = max_attempts - 1, run_at = '1999-01-01' WHERE id = %s", (job["id"],)
        )  # the runner's last attempt, first in its queue
        assert run_one(db, "test-hide-recheck")
        waiting = db.execute(state, (job["id"],)).fetchone()
        assert (waiting["state"], waiting["last_error"]) == ("queued", "waiting_gatekeeper")
        assert waiting["attempts"] == job["max_attempts"] - 1  # not a try
    finally:
        db.execute("UPDATE kill_switches SET state = 'on' WHERE name = 'ai.all'")
        killswitch.clear_cache()
    assert count(db, calls, scope_for(iid)) == calls_before  # no model call while the assistant is off

    FAKE_SCRIPT.append(RouteError("connection"))  # back on, the gateway still down: the last attempt fails
    db.execute("UPDATE jobs SET run_at = '1999-01-01' WHERE id = %s", (job["id"],))
    assert run_one(db, "test-hide-recheck")
    done = db.execute(state, (job["id"],)).fetchone()
    assert (done["state"], done["last_error"]) == ("dead", "GatekeeperUnavailable")
    assert count(db, gave, f"idea:{iid}") == gave_before + 1
    row = db.execute(
        "SELECT actor, after FROM audit_log WHERE action = 'hide.recheck_gave_up' AND entity = %s ORDER BY id DESC",
        (f"idea:{iid}",),
    ).fetchone()
    assert row["actor"] == "system"
    assert row["after"] == {
        "source": "message", "source_id": mid, "code": "GatekeeperUnavailable", "recheck_job": job["id"],
        "attempts": job["max_attempts"],
    }  # fmt: skip
    assert sealed_done(db, mid) is not None  # the audit row is the record: the sweep does not ask again


def sealed_done(conn: Any, source_id: str, source: str = "message") -> Any:
    """`idea_words_sealed.gatekeeper_done_at` for one text (BLD-C231): None while it waits for the gatekeeper."""
    row = conn.execute(
        "SELECT gatekeeper_done_at FROM idea_words_sealed WHERE source = %s AND source_id = %s",
        (source, source_id),
    ).fetchone()
    assert row is not None
    return row["gatekeeper_done_at"]


def no_stray_rechecks(conn: Any) -> None:
    """Re-checks other tests left queued (the shared database keeps `jobs`) would count toward the sweep's cap."""
    conn.execute("DELETE FROM jobs WHERE type = 'hide.recheck' AND state IN ('queued', 'running')")


def recheck_jobs(conn: Any, idea_uuid: str) -> list[Any]:
    return conn.execute(
        "SELECT id, payload, state FROM jobs WHERE type = 'hide.recheck' AND payload->>'idea_uuid' = %s ORDER BY id",
        (idea_uuid,),
    ).fetchall()


def test_l_hide_detect_bld_c231_words_written_while_the_assistant_is_off_are_checked_once_it_is_back(
    hdb: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEC-131 (3), BLD-C231: a message hidden while `ai.all` is off gets the patterns and names only, its sealed words
    stay unchecked and nothing is queued. Once the assistant is back, the sweep queues one re-check (the caller's own
    id, the same dedupe key), which finds the address and marks the words done; nothing is asked twice, and a message
    hidden with the assistant on is marked done at once and never swept."""
    from core import killswitch
    from gateway.routes import FAKE_SCRIPT

    monkeypatch.setattr(hide_recheck, "SETTLE", "0 seconds")
    db = hdb
    no_stray_rechecks(db)
    uid, code = person(db)
    iid = idea(db, code, shared=True)
    db.execute("UPDATE kill_switches SET state = 'off' WHERE name = 'ai.all'")
    killswitch.clear_cache()
    try:
        mid, out = message(db, iid, uid, f"Forms come back from {ADDRESS} every week", gatekeeper=True)
        assert out.hidden_count == 0 and not out.gatekeeper_checked and sealed_done(db, mid) is None
        assert recheck_jobs(db, iid) == []  # nothing queued while off
        assert hide_recheck.queue_unchecked(db) == 0  # and the sweep waits for the switches
    finally:
        db.execute("UPDATE kill_switches SET state = 'on' WHERE name = 'ai.all'")
        killswitch.clear_cache()

    FAKE_SCRIPT.append(gatekeeper_output())  # nothing found: marked done at once
    checked, done = message(db, iid, uid, "Mandates bounce at capture", seq=2, gatekeeper=True)
    assert done.gatekeeper_checked and sealed_done(db, checked) is not None

    assert hide_recheck.queue_unchecked(db) == 1
    jobs = recheck_jobs(db, iid)
    assert [j["payload"] for j in jobs] == [
        {"idea_uuid": iid, "source": "message", "source_id": mid, "by": uid}
    ]
    assert hide_recheck.queue_unchecked(db) == 0  # queued already: never twice

    FAKE_SCRIPT.append(address_found())
    hide_recheck.run(db, jobs[0]["payload"])
    assert ADDRESS not in masked_message(db, mid)
    assert sealed_done(db, mid) is not None
    db.execute("UPDATE jobs SET state = 'done' WHERE id = %s", (jobs[0]["id"],))
    assert hide_recheck.queue_unchecked(db) == 0  # every text has had its check


def test_l_hide_detect_bld_c231_the_sweep_keeps_at_most_five_rechecks_going_and_new_words_wait_again(
    hdb: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLD-C231: after a switch-on the backlog yields to live work: at most `RECHECK_OUTSTANDING` (5) re-checks are
    running or due at once, topped up as they finish. New words hidden while the assistant is off take a checked
    text back to unchecked."""
    from core import killswitch
    from gateway.routes import FAKE_SCRIPT

    monkeypatch.setattr(hide_recheck, "SETTLE", "0 seconds")
    db = hdb
    no_stray_rechecks(db)
    uid, code = person(db)
    iid = idea(db, code, shared=True)
    db.execute("UPDATE kill_switches SET state = 'off' WHERE name = 'ai.all'")
    killswitch.clear_cache()
    try:
        mids = [message(db, iid, uid, f"Mandate {n} bounced at capture", seq=n + 1)[0] for n in range(7)]
    finally:
        db.execute("UPDATE kill_switches SET state = 'on' WHERE name = 'ai.all'")
        killswitch.clear_cache()
    assert hide_recheck.RECHECK_OUTSTANDING == 5
    assert hide_recheck.queue_unchecked(db) == 5
    assert hide_recheck.queue_unchecked(db) == 0  # five already due
    first = recheck_jobs(db, iid)[:3]  # three re-checks finish: their words are marked done, their jobs done
    db.execute("UPDATE jobs SET state = 'done' WHERE id = ANY(%s)", ([j["id"] for j in first],))
    db.execute(
        "UPDATE idea_words_sealed SET gatekeeper_done_at = now() WHERE source = 'message' AND source_id = ANY(%s)",
        ([j["payload"]["source_id"] for j in first],),
    )
    assert hide_recheck.queue_unchecked(db) == 2  # room for three, but only the last two are left
    assert len(recheck_jobs(db, iid)) == 7

    FAKE_SCRIPT.append(gatekeeper_output())
    words = "Mandates bounce at capture"
    with db.transaction():
        hide_message(db, iid, words, by=uid, source_id=mids[0], gatekeeper=True)
    assert sealed_done(db, mids[0]) is not None
    db.execute("UPDATE kill_switches SET state = 'off' WHERE name = 'ai.all'")
    killswitch.clear_cache()
    try:
        with db.transaction():
            hide_message(db, iid, words + " every week", by=uid, source_id=mids[0], gatekeeper=True)
        assert sealed_done(db, mids[0]) is None  # new words, not yet checked
    finally:
        db.execute("UPDATE kill_switches SET state = 'on' WHERE name = 'ai.all'")
        killswitch.clear_cache()


def test_l_hide_rules_7_two_desk_hides_on_an_unmapped_authors_message_leave_a_correct_copy(hdb: Any) -> None:
    """C (BLD-C066): a conversation message whose author is no longer mapped has no own words and no owner, so each
    desk hide masks its copy in place and its details keep no span; a second hide never garbles the copy."""
    db = hdb
    NAME, OTHER = made_up_name(), made_up_name()
    reviewer, _ = person(db)
    _, code = person(db)
    iid = idea(db, code, shared=True)
    eid, unmapped = str(uuid.uuid4()), f"CTR-{secrets.token_hex(3)}"  # a code no longer in contributor_map
    text = f"Ask {NAME} and then {OTHER} at the branch. {NAME} knows"
    db.execute(
        "INSERT INTO conversation_entries (id, idea_uuid, type, author_code, text_encrypted) "
        "VALUES (%s, %s, 'message', %s, %s)",
        (eid, iid, unmapped, seal_text("conversation_entries", "text_encrypted", eid, text)),
    )
    for value in (NAME, OTHER):
        seen = masked_in(db, "conversation_entries", eid)
        at = seen.index(value)
        d = desk_hide(
            db, iid, source_kind="conversation", source_id=eid, start=at, end=at + len(value), by=reviewer,
            selected=value,
        )  # fmt: skip
        assert d["kind"] == "name"
    assert masked_in(db, "conversation_entries", eid) == (
        f"Ask {mask('name', NAME)} and then {mask('name', OTHER)} at the branch. {mask('name', NAME)} knows"
    )
    rows = db.execute(
        "SELECT span_start, found_by FROM hidden_details WHERE idea_uuid = %s AND source_id = %s", (iid, eid)
    ).fetchall()
    assert len(rows) == 2 and all(r["span_start"] is None and r["found_by"] == "reviewer" for r in rows)
    assert count(db, "SELECT count(*) AS n FROM idea_words_sealed WHERE source_id = %s", eid) == 0
    assert helpers.tables_containing(db, NAME) == [] and helpers.tables_containing(db, OTHER) == []
