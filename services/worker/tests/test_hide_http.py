"""L-HIDE.rules/6 and /7 over HTTP against the running stack (lane C, BLD-C060): S-R2 "Hide this" for the review
desk and the Ones Committee only, with its four errors in the A-API shape, and the sharer's "Show it" / "Hide it".
Synthetic people and values; everything created is removed afterwards (the vault scope too)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest

from core.db import connect
from hide import hide_message
from hide.core import scope_for
from onepc.context import seal_text
from pii import vault
from tests.web import people

pytestmark = pytest.mark.stack

FOLIO = "1234567/89"
WORDS = f"The agent Kiran Rao keeps asking. It is about folio {FOLIO} every week."


@pytest.fixture
def world() -> Iterator[dict[str, Any]]:
    with connect(autocommit=True) as conn, people(conn) as make:
        sharer, other = make(), make()
        reviewer = make((("reviewer", None),))
        committee = make((("core_committee", None),))
        row = conn.execute(
            "INSERT INTO ideas (contributor_code, status, kind, title, summary, idea_id) "
            "VALUES (%s, 'with_review_desk', 'problem', 'SIP mandates fail', 'Mandates bounce', next_idea_ref()) "
            "RETURNING id, idea_id",
            (sharer.contributor_code,),
        ).fetchone()
        iid, ref = str(row["id"]), str(row["idea_id"])
        mid = str(uuid.uuid4())
        with conn.transaction():  # the hide and the write of its masked copy, together (hide/__init__.py)
            out = hide_message(conn, iid, WORDS, by=sharer.user_id, source_id=mid, gatekeeper=False)
            conn.execute(
                "INSERT INTO idea_messages (id, idea_uuid, seq, via, text_encrypted, char_count) "
                "VALUES (%s, %s, 1, 'typed', %s, %s)",
                (mid, iid, seal_text("idea_messages", "text_encrypted", mid, out.masked), len(WORDS)),
            )
        try:
            yield {
                "conn": conn, "iid": iid, "ref": ref, "mid": mid, "masked": out.masked, "details": out.details,
                "sharer": sharer, "other": other, "reviewer": reviewer, "committee": committee,
            }  # fmt: skip
        finally:  # the people, the idea and its rows go in `people`; audit_log is append-only, so its rows stay
            vault.purge_scope(conn, scope_for(iid))
            conn.execute("DELETE FROM vault_counters WHERE scope_id = %s", (scope_for(iid),))


def test_l_hide_rules_7_s_r2_hide_this_for_the_desk_and_committee_only(world: dict[str, Any]) -> None:
    masked, mid = world["masked"], world["mid"]
    start = masked.index("Kiran Rao")
    body = {"source": {"kind": "message", "id": mid}, "start": start, "end": start + len("Kiran Rao")}
    path = f"/api/desk/ideas/{world['ref']}/hide"

    assert world["sharer"].browser().post(path, json=body).status_code == 403
    r = world["reviewer"].browser().post(path, json=body)
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["kind"] == "name" and detail["masked"] == "Name ••••ao" and detail["state"] == "hidden"
    assert set(detail) <= {"id", "kind", "masked", "state", "reason", "shown_at"}

    again = world["committee"].browser().post(f"/api/desk/ideas/{world['iid']}/hide", json=body)
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_hidden"
    assert again.json()["error"]["message"]
    bad = world["reviewer"].browser().post(path, json={**body, "start": 5, "end": 2})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "range_invalid"
    missing = world["reviewer"].browser().post("/api/desk/ideas/IDEA-1999-000001/hide", json=body)
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"
    short = world["reviewer"].browser().post(path, json={**body, "end": start + 2})
    assert short.status_code == 400 and short.json()["error"]["code"] == "range_invalid"
    for text in (r.text, again.text, bad.text, missing.text, short.text):
        assert "Kiran" not in text and FOLIO not in text

    # The desk's hide wins: the sharer cannot show it (review fix 4), and the worker's error object reaches the
    # screen as A-API's shape with the web's words.
    shown = (
        world["sharer"]
        .browser()
        .post(f"/api/drafts/{world['iid']}/hidden/{detail['id']}/show", json={"reason": "made_up_example"})
    )
    assert shown.status_code == 403 and shown.json()["error"]["code"] == "forbidden"
    assert shown.json()["error"]["message"] == "The review desk hid this, so it stays hidden."

    audit = (
        world["conn"]
        .execute(
            "SELECT actor FROM audit_log WHERE action = 'hide.desk_hidden' AND entity = %s",
            (f"idea:{world['iid']}",),
        )
        .fetchone()
    )
    assert audit["actor"] == f"user:{world['reviewer'].user_id}"


def test_l_hide_rules_6_show_it_and_hide_it_are_the_sharers_alone(world: dict[str, Any]) -> None:
    hid = next(d["id"] for d in world["details"] if d["kind"] == "folio")
    base = f"/api/drafts/{world['iid']}/hidden/{hid}"
    sharer = world["sharer"].browser()

    no_reason = sharer.post(f"{base}/show", json={})
    assert no_reason.status_code == 400 and no_reason.json()["error"]["code"] == "reason_required"
    assert (
        world["other"].browser().post(f"{base}/show", json={"reason": "made_up_example"}).status_code == 404
    )
    shown = sharer.post(f"{base}/show", json={"reason": "made_up_example"})
    assert shown.status_code == 200, shown.text
    assert shown.json()["state"] == "shown" and shown.json()["reason"] == "made_up_example"
    hidden = sharer.post(f"{base}/hide", json={})
    assert hidden.status_code == 200 and hidden.json()["state"] == "hidden"
    rows = (
        world["conn"]
        .execute(
            "SELECT action FROM audit_log WHERE entity = %s AND action IN ('hide.shown', 'hide.rehidden') ORDER BY id",
            (f"idea:{world['iid']}",),
        )
        .fetchall()
    )
    assert [r["action"] for r in rows] == ["hide.shown", "hide.rehidden"]
