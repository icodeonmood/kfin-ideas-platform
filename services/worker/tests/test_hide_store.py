"""L-HIDE.rules/1 to /8 and L-HIDE.audit against a migrated test database (lane C, BLD-C060 to BLD-C063): what is
stored where, the masked copy, "Show it" and "Hide it", and the desk's "Hide this" in every copy. Values are
synthetic and made up for the test (non-negotiable 11)."""

from __future__ import annotations

import secrets
import uuid
from typing import Any

import pytest

from hide import HideError, desk_hide, hide_again, hide_message, hide_text, show
from hide.core import own_words, scope_for
from onepc.context import open_text, seal_text
from pii import vault
from tests import helpers

pytestmark = pytest.mark.stack

FOLIO, PAN, PHONE = "1234567/89", "ABCPK1234F", "9876543210"
WORDS = f"SIP failed for the investor. Folio {FOLIO}, PAN {PAN}, call {PHONE} after 6."


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


def message(conn: Any, idea_uuid: str, uid: str, text: str, seq: int = 1) -> tuple[str, Any]:
    mid = str(uuid.uuid4())
    out = hide_message(conn, idea_uuid, text, by=uid, source_id=mid, gatekeeper=False)
    conn.execute(
        "INSERT INTO idea_messages (id, idea_uuid, seq, via, text_encrypted, char_count) "
        "VALUES (%s, %s, %s, 'typed', %s, %s)",
        (mid, idea_uuid, seq, seal_text("idea_messages", "text_encrypted", mid, out.masked), len(text)),
    )
    return mid, out


def masked_message(conn: Any, mid: str) -> str:
    row = conn.execute("SELECT text_encrypted FROM idea_messages WHERE id = %s", (mid,)).fetchone()
    text = open_text("idea_messages", "text_encrypted", mid, row["text_encrypted"])
    assert text is not None
    return text


def test_l_hide_rules_3_4_the_masked_copy_is_all_others_get_and_no_value_is_stored_in_clear(db: Any) -> None:
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
    assert own_words(db, "message", mid) == WORDS  # the person's own copy, worker only
    tags = {
        r["vault_tag"]
        for r in db.execute("SELECT vault_tag FROM hidden_details WHERE idea_uuid = %s", (iid,))
    }
    values = {t: v for t, (_, v) in vault.mapping(db, scope_for(iid)).items() if t in tags}
    assert sorted(values.values()) == sorted([FOLIO, PAN, PHONE])
    audit = db.execute("SELECT after FROM audit_log WHERE action = 'hide.detected'").fetchone()
    assert audit["after"]["kinds"] == {"folio": 1, "pan": 1, "phone": 1}
    assert masked_message(db, mid) == out.masked


def test_l_hide_rules_6_show_needs_a_reason_and_an_edit_keeps_the_choice(db: Any) -> None:
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
    audit = db.execute("SELECT reason, after FROM audit_log WHERE action = 'hide.shown'").fetchone()
    assert audit["reason"] == "made_up_example" and PAN not in str(audit["after"])

    again = hide_message(db, iid, WORDS + " Thanks.", by=uid, source_id=mid, gatekeeper=False)
    kept = next(d for d in again.details if d["kind"] == "pan")
    assert kept["id"] == pan_id and kept["state"] == "shown"
    assert PAN in again.masked and again.hidden_count == 2

    hidden = hide_again(db, iid, pan_id, by=uid)
    assert hidden["state"] == "hidden" and "reason" not in hidden
    assert PAN not in masked_message(db, mid)


def test_l_hide_rules_1_hide_text_for_desk_written_text(db: Any) -> None:
    reviewer, _ = person(db)
    _, code = person(db)
    iid = idea(db, code, shared=True)
    masked, count = hide_text(
        db, iid, f"Please add a screenshot of folio {FOLIO} with it hidden", by=reviewer
    )
    assert masked == "Please add a screenshot of folio Folio ••••89 with it hidden" and count == 1
    row = db.execute("SELECT source, found_by FROM hidden_details WHERE idea_uuid = %s", (iid,)).fetchone()
    assert (row["source"], row["found_by"]) == ("desk", "patterns")


def test_l_hide_rules_7_the_desk_hides_a_missed_name_in_every_copy(db: Any) -> None:
    reviewer, _ = person(db)
    uid, code = person(db)
    iid = idea(db, code, shared=True, title="Kiran Rao waits for SIP refunds")
    text = f"The agent Kiran Rao keeps asking. It is about folio {FOLIO} every week"
    mid, _ = message(db, iid, uid, text)
    m2, _ = message(db, iid, uid, "Kiran Rao said the same on Monday", seq=2)
    seen = masked_message(db, mid)
    start = seen.index("Kiran Rao")
    detail = desk_hide(
        db, iid, source_kind="message", source_id=mid, start=start, end=start + len("Kiran Rao"), by=reviewer
    )
    assert detail["kind"] == "name" and detail["masked"] == "Name ••••ao" and detail["state"] == "hidden"
    assert "Kiran Rao" not in masked_message(db, mid) and "Kiran Rao" not in masked_message(db, m2)
    assert (
        db.execute("SELECT title FROM ideas WHERE id = %s", (iid,))
        .fetchone()["title"]
        .startswith("Name ••••ao")
    )
    assert own_words(db, "message", mid) == text  # the sharer's own words are unchanged
    rows = db.execute(
        "SELECT source_id, found_by FROM hidden_details WHERE idea_uuid = %s AND kind = 'name'", (iid,)
    ).fetchall()
    assert {(str(r["source_id"]), r["found_by"]) for r in rows} == {(mid, "reviewer"), (m2, "reviewer")}
    audit = db.execute("SELECT actor, after FROM audit_log WHERE action = 'hide.desk_hidden'").fetchone()
    assert audit["actor"] == f"user:{reviewer}" and "Kiran" not in str(audit["after"])
    assert helpers.tables_containing(db, "Kiran Rao") == []

    with pytest.raises(HideError) as twice:
        desk_hide(db, iid, source_kind="message", source_id=mid, start=start, end=start + 4, by=reviewer)
    assert twice.value.code == "already_hidden"
    with pytest.raises(HideError) as outside:
        desk_hide(db, iid, source_kind="message", source_id=mid, start=0, end=10_000, by=reviewer)
    assert outside.value.code == "range_invalid"

    # A new message on the same idea hides the value too.
    _, later = message(db, iid, uid, "Kiran Rao again", seq=3)
    assert later.masked == "Name ••••ao again"


def test_l_hide_rules_7_title_and_part_and_drafts_are_not_for_the_desk(db: Any) -> None:
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
