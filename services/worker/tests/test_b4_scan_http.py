"""The scan over HTTP against the running stack: the waiting screen's status, and the person's choices.
Only the owner sees a scan; a blocked idea goes back to edit with the same IDs; "No, this is an idea" needs a
reason; taking a redirect ends there."""

from __future__ import annotations

import random
import secrets
import time
from collections.abc import Iterator
from typing import Any

import generators as g
import pytest
from psycopg.types.json import Jsonb

from core.db import connect
from tests.test_b3_submissions_api import full_canvas
from tests.web import Browser, people

pytestmark = pytest.mark.stack


@pytest.fixture
def me() -> Iterator[Any]:
    with connect(autocommit=True) as conn, people(conn) as make:
        yield make(), make, conn


def submit(b: Browser, details: str) -> tuple[str, str]:
    created = b.post("/api/submissions", json={"mode": "full", "canvas": full_canvas(details=details)})
    draft = created.json()["id"]
    sent = b.post(f"/api/submissions/{draft}/submit", json={"canvas": full_canvas(details=details)})
    assert sent.status_code == 202, sent.text
    return draft, sent.json()["idea_id"]


def settled(b: Browser, draft: str, timeout: float = 30.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        r = b.get(f"/api/submissions/{draft}/scan-status")
        assert r.status_code == 200, r.text
        body: dict[str, Any] = r.json()
        if body["state"] not in ("queued", "running"):
            return body
        assert time.monotonic() < deadline, body
        time.sleep(0.3)


def test_ready_and_owner_only(me: Any) -> None:
    person, make, _ = me
    b = person.browser()
    draft, _ = submit(b, "Ops re-key the same nominee details into two screens for every new folio we open.")
    status = settled(b, draft)
    assert status["outcome"] == "ready" and status["ready"]["neutral_summary"]
    assert make().browser().get(f"/api/submissions/{draft}/scan-status").status_code == 404
    choice = b.post(f"/api/submissions/{draft}/scan-choice", json={"choice": "edit"})
    assert choice.status_code == 409  # nothing to edit: the scan did not stop


def test_blocked_goes_back_to_edit_with_the_same_ids(me: Any) -> None:
    person, _, _conn = me
    b = person.browser()
    name = g.person_name(random.Random(111))
    draft, idea_id = submit(b, f"The investor {name} called five times because her SIP registration slipped.")
    status = settled(b, draft)
    assert status["outcome"] == "blocked" and name in status["blocked"]["spans"][0]["quote"]
    assert status["blocked"]["can_contest"] is True  # BLD-082 option B: the person may choose to edit instead
    assert b.post(f"/api/submissions/{draft}/scan-choice", json={"choice": "edit"}).json() == {
        "next": f"/share/{draft}"
    }
    assert b.get(f"/api/submissions/{draft}").json()["stage"] == "draft"
    clean = "Investors call five times because SIP registrations slip when forms are re-checked by hand."
    resent = b.post(f"/api/submissions/{draft}/submit", json={"canvas": full_canvas(details=clean)})
    assert resent.status_code == 202 and resent.json()["idea_id"] == idea_id
    assert settled(b, draft)["outcome"] == "ready"


def test_a_block_can_no_longer_be_contested(me: Any) -> None:
    """DEC-106 (R3): "This is not personal data" (BLD-082 option B) is retired. A gatekeeper block is edited out
    until lane C's Check it hides details instead of blocking them (DEC-103); nothing is audited as a contest."""
    person, _, conn = me
    b = person.browser()
    name = g.person_name(random.Random(111))
    draft, idea_id = submit(b, f"The investor {name} called five times because her SIP registration slipped.")
    assert settled(b, draft)["outcome"] == "blocked"
    contest = b.post(f"/api/submissions/{draft}/scan-choice", json={"choice": "not_personal_data"})
    assert contest.status_code == 400 and contest.json() == {"error": "choice_required"}
    assert settled(b, draft)["outcome"] == "blocked"
    audit = conn.execute(
        "SELECT 1 FROM audit_log WHERE action = 'scan.contest' AND entity = %s", (f"idea:{idea_id}",)
    ).fetchone()
    assert audit is None


def test_the_desk_sees_contested_investor_items_first(me: Any) -> None:
    """The queue puts contested investor or customer blocks first, ahead of an item due sooner (BLD-082)."""
    _, make, conn = me
    refs = [f"IDEA-TEST-{secrets.token_hex(3)}" for _ in range(2)]
    plain = conn.execute(
        "INSERT INTO review_items (item_type, ref_id) VALUES ('idea', %s) RETURNING id", (refs[0],)
    ).fetchone()["id"]
    flagged = conn.execute(
        "INSERT INTO review_items (item_type, ref_id, reasons) VALUES ('idea', %s, %s) RETURNING id",
        (refs[1], Jsonb({"contested": "investor_or_customer"})),
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO sla_timers (entity_type, entity_id, stage, started_at, due_at) "
        "VALUES ('review_item', %s, 'review', now() - interval '9 days', now() - interval '8 days')",
        (str(plain),),
    )  # overdue, so it would lead the queue on due date alone
    try:
        items = make((("reviewer", None),)).browser().get("/api/review/items").json()["items"]
        order = [i["id"] for i in items if i["id"] in (plain, flagged)]
        assert order == [flagged, plain]
        assert next(i for i in items if i["id"] == flagged)["check_first"] is True
        assert next(i for i in items if i["id"] == plain)["check_first"] is False
        flags = [i["check_first"] for i in items]
        assert flags == sorted(flags, reverse=True), "check-first items come before the rest"
    finally:
        conn.execute(
            "DELETE FROM sla_timers WHERE entity_type = 'review_item' AND entity_id IN (%s, %s)",
            (str(plain), str(flagged)),
        )
        conn.execute("DELETE FROM review_items WHERE id IN (%s, %s)", (plain, flagged))


def test_a_pattern_block_cannot_be_contested(me: Any) -> None:
    """Pattern hits (PAN, Aadhaar, mobile, folio and the rest, §4.2 step 2) stay absolute: refused at submit, so
    there is no scan to contest."""
    person, _, conn = me
    b = person.browser()
    pan = g.pan(random.Random(9))
    leaked = f"Ops re-key the same nominee details twice; investor PAN {pan} came up again."
    draft = b.post("/api/submissions", json={"mode": "full"}).json()["id"]
    sent = b.post(f"/api/submissions/{draft}/submit", json={"canvas": full_canvas(details=leaked)})
    assert sent.status_code == 422 and sent.json()["error"] == "personal_data"
    contest = b.post(f"/api/submissions/{draft}/scan-choice", json={"choice": "not_personal_data"})
    assert contest.status_code in (404, 409)
    assert conn.execute("SELECT stage FROM ideas WHERE id = %s", (draft,)).fetchone()["stage"] == "draft"
    assert conn.execute("SELECT 1 FROM scans WHERE idea_uuid = %s", (draft,)).fetchone() is None


def test_redirect_override_needs_a_reason(me: Any) -> None:
    person, _, conn = me
    b = person.browser()
    draft, _ = submit(b, "My laptop VPN is not working since Monday morning and IT has not called back yet.")
    status = settled(b, draft)
    assert status["outcome"] == "redirect" and status["redirect"]["team"] == "IT helpdesk"
    short = b.post(f"/api/submissions/{draft}/scan-choice", json={"choice": "is_an_idea", "reason": "it is"})
    assert short.status_code == 422 and short.json()["error"] == "reason_too_short"
    ok = b.post(
        f"/api/submissions/{draft}/scan-choice",
        json={"choice": "is_an_idea", "reason": "VPN drops cost the whole ops floor two hours every day"},
    )
    assert ok.status_code == 200
    assert settled(b, draft)["outcome"] == "ready"
    blob = conn.execute(
        "SELECT override_reason_encrypted FROM scans WHERE idea_uuid = %s", (draft,)
    ).fetchone()
    assert blob["override_reason_encrypted"] is not None and b"ops floor" not in bytes(
        blob["override_reason_encrypted"]
    )


def test_taking_the_redirect(me: Any) -> None:
    person, _, conn = me
    b = person.browser()
    draft, _ = submit(
        b, "My outlook password is locked again and the reset link is not working for me today."
    )
    assert settled(b, draft)["outcome"] == "redirect"
    assert (
        b.post(f"/api/submissions/{draft}/scan-choice", json={"choice": "take_redirect"}).status_code == 200
    )
    assert conn.execute("SELECT stage FROM ideas WHERE id = %s", (draft,)).fetchone()["stage"] == "redirected"
    assert settled(b, draft)["outcome"] == "redirected"
