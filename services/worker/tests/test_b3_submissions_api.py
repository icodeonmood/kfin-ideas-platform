"""Drafts and submit over HTTP: AT-B3-02 (required fields, errors tied to fields), AT-B3-03 (server half: the
same pattern rules refuse a generated PAN and only warn on a KFin email), AT-B3-04 (autosave; drafts encrypted,
owner only), AT-B3-08 (IDs with the same number, stage scanning, scan queued, within 300 ms)."""

import time
from collections.abc import Iterator
from typing import Any

import generators as g
import pytest

from core.db import connect
from tests.web import people

pytestmark = pytest.mark.stack

SYNTHETIC_DETAILS = "Ops re-check every SIP form by hand for missing bank or nominee fields, which delays registration by a day."


def full_canvas(**overrides: Any) -> dict[str, Any]:
    c: dict[str, Any] = {
        "kind": "problem",
        "one_line": "SIP registrations slip because forms are re-checked by hand",
        "details": SYNTHETIC_DETAILS,
        "who": {
            "segments": ["kfin_teams"],
            "frequency_or_reach": "daily",
            "today_alternative": "Manual re-checks",
        },
        "value": {
            "category": "cost_saving",
            "play": "process_improvement",
            "estimate": {"hours_saved_per_month": 120},
            "basis": "own_data",
        },
        "ecosystem": {
            "solved_elsewhere": "partly",
            "references": [],
            "our_advantage": "We run the intake already.",
        },
        "solution": {},
        "visibility": "org",
        "declarations": {"no_personal_data": True, "own_work_or_credited": True, "ip_terms": True},
    }
    c.update(overrides)
    return c


@pytest.fixture
def person() -> Iterator[Any]:
    with connect(autocommit=True) as conn, people(conn) as make:
        yield make(), make, conn


def test_draft_lifecycle_and_submit(person: Any) -> None:
    me, make, conn = person
    b = me.browser()
    created = b.post("/api/submissions", json={"mode": "full", "canvas": full_canvas(details="First words")})
    assert created.status_code == 201
    draft_id = created.json()["id"]

    # Autosave keeps the latest answers; the text is encrypted at rest.
    assert b.request("PUT", f"/api/submissions/{draft_id}", json={"canvas": full_canvas()}).status_code == 200
    assert b.get(f"/api/submissions/{draft_id}").json()["canvas"]["details"] == SYNTHETIC_DETAILS
    plain = conn.execute(
        "SELECT position(convert_to(%s, 'UTF8') in draft_encrypted) AS at FROM ideas WHERE id = %s",
        ("re-check every SIP form", draft_id),
    ).fetchone()["at"]
    assert plain == 0

    # Someone else cannot read or change my draft (it looks missing).
    other = make().browser()
    assert other.get(f"/api/submissions/{draft_id}").status_code == 404
    assert (
        other.request("PUT", f"/api/submissions/{draft_id}", json={"canvas": full_canvas()}).status_code
        == 404
    )

    started = time.perf_counter()
    r = b.post(f"/api/submissions/{draft_id}/submit", json={"canvas": full_canvas()})
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["idea_id"].split("-", 1)[1] == body["submission_id"].split("-", 1)[1]
    assert body["stage"] == "scanning"
    # The details are under the rubric's 150 characters, so "what it is" is not yet earned (AT-B3-05).
    assert body["strength"] == 4 and body["next_best"][0].startswith("Tell us a little more")
    assert elapsed_ms <= 300, f"submit took {elapsed_ms:.0f} ms"  # AT-B3-08

    row = conn.execute(
        "SELECT stage, idea_id, draft_encrypted, raw_encrypted, canvas FROM ideas WHERE id = %s", (draft_id,)
    ).fetchone()
    assert row["stage"] == "scanning" and row["idea_id"] == body["idea_id"]
    assert row["draft_encrypted"] is None and row["raw_encrypted"] is not None and row["canvas"] is None
    job = conn.execute(
        "SELECT state, payload FROM jobs WHERE dedupe_key = %s", (f"scan:{body['idea_id']}",)
    ).fetchone()
    assert job["state"] == "queued" and job["payload"]["idea_id"] == body["idea_id"]

    assert b.post(f"/api/submissions/{draft_id}/submit", json={"canvas": full_canvas()}).status_code == 409
    conn.execute("DELETE FROM jobs WHERE dedupe_key = %s", (f"scan:{body['idea_id']}",))


def test_required_fields_are_tied_to_their_fields(person: Any) -> None:
    me, _, _ = person
    b = me.browser()
    draft_id = b.post("/api/submissions", json={"mode": "full"}).json()["id"]
    r = b.post(f"/api/submissions/{draft_id}/submit", json={"canvas": {"one_line": " ".join(["word"] * 21)}})
    assert r.status_code == 422 and r.json()["error"] == "invalid"
    fields = {e["field"] for e in r.json()["details"]}
    assert {"kind", "one_line", "details", "value.category", "declarations.ip_terms"} <= fields


def test_personal_data_is_refused_on_save_and_submit(person: Any) -> None:
    me, _, conn = person
    b = me.browser()
    draft_id = b.post("/api/submissions", json={"mode": "full"}).json()["id"]
    leaked = full_canvas(details=f"{SYNTHETIC_DETAILS} Investor PAN {g.pan(g.default_rng(9))} called.")
    for r in (
        b.request("PUT", f"/api/submissions/{draft_id}", json={"canvas": leaked}),
        b.post(f"/api/submissions/{draft_id}/submit", json={"canvas": leaked}),
    ):
        assert r.status_code == 422 and r.json()["error"] == "personal_data"
        hit = r.json()["details"][0]
        assert hit["field"] == "details" and hit["label"] == "PAN" and hit["action"] == "block"
        assert "value" not in hit  # the matched value is never echoed back
    assert conn.execute("SELECT stage FROM ideas WHERE id = %s", (draft_id,)).fetchone()["stage"] == "draft"

    # A KFin email only warns: the idea goes through, with the warning noted.
    kfin = full_canvas(
        details=f"{SYNTHETIC_DETAILS} Write to {g.kfin_email(g.default_rng(4), ['kfintech.com'])}."
    )
    r = b.post(f"/api/submissions/{draft_id}/submit", json={"canvas": kfin})
    assert r.status_code == 202 and r.json()["warnings"][0]["label"] == "Email address"
    conn.execute("DELETE FROM jobs WHERE dedupe_key = %s", (f"scan:{r.json()['idea_id']}",))


def test_quick_capture_submits_with_three_answers(person: Any) -> None:
    me, _, conn = person
    b = me.browser()
    draft_id = b.post("/api/submissions", json={"mode": "quick"}).json()["id"]
    quick = {
        "details": "Investors call twice because the SIP confirmation SMS arrives a day late.",
        "who": {"segments": ["investors"]},
        "value": {"category": "not_sure"},
        "declarations": {"no_personal_data": True, "own_work_or_credited": True, "ip_terms": True},
    }
    r = b.post(f"/api/submissions/{draft_id}/submit", json={"canvas": quick})
    assert r.status_code == 202, r.text
    assert (
        conn.execute("SELECT capture_mode FROM ideas WHERE id = %s", (draft_id,)).fetchone()["capture_mode"]
        == "quick"
    )
    conn.execute("DELETE FROM jobs WHERE dedupe_key = %s", (f"scan:{r.json()['idea_id']}",))


def test_quick_capture_is_one_box_and_saves_not_sure(person: Any) -> None:
    """DEC-094: no category and one confirmation (all three declarations) are enough; the server saves the
    unchosen category as "not sure yet", the person's own answer, so the assistant never fills it (DEC-004)."""
    me, _, conn = person
    b = me.browser()
    draft_id = b.post("/api/submissions", json={"mode": "quick"}).json()["id"]
    details = "Branch staff re-type every change-of-address form because the scan is hard to read."
    r = b.post(
        f"/api/submissions/{draft_id}/submit",
        json={"canvas": {"details": details, "declarations": {"no_personal_data": True}}},
    )
    assert r.status_code == 422 and [e["field"] for e in r.json()["details"]] == ["declarations.all"]
    every = {"no_personal_data": True, "own_work_or_credited": True, "ip_terms": True}
    r = b.post(
        f"/api/submissions/{draft_id}/submit", json={"canvas": {"details": details, "declarations": every}}
    )
    assert r.status_code == 202, r.text
    row = conn.execute("SELECT category FROM ideas WHERE id = %s", (draft_id,)).fetchone()
    assert row["category"] == "not_sure"
    conn.execute("DELETE FROM jobs WHERE dedupe_key = %s", (f"scan:{r.json()['idea_id']}",))
