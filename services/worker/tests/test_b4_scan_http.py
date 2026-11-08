"""The scan over HTTP against the running stack: the waiting screen's status, and the person's choices.
Only the owner sees a scan; a blocked idea goes back to edit with the same IDs; "No, this is an idea" needs a
reason; taking a redirect ends there."""

from __future__ import annotations

import random
import time
from collections.abc import Iterator
from typing import Any

import generators as g
import pytest

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
    assert b.post(f"/api/submissions/{draft}/scan-choice", json={"choice": "edit"}).json() == {
        "next": f"/share/{draft}"
    }
    assert b.get(f"/api/submissions/{draft}").json()["stage"] == "draft"
    clean = "Investors call five times because SIP registrations slip when forms are re-checked by hand."
    resent = b.post(f"/api/submissions/{draft}/submit", json={"canvas": full_canvas(details=clean)})
    assert resent.status_code == 202 and resent.json()["idea_id"] == idea_id
    assert settled(b, draft)["outcome"] == "ready"


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
