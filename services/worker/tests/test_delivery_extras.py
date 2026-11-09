"""Delivery extras: evidence files (BLD-131) and Friday check-in replies (BLD-132). The file store is an in-memory
stand-in here; the HTTP path and the real checks run in the end-to-end suite. Synthetic people only."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import pytest

from attachments import service as attachments
from delivery import extras, service
from tests import test_delivery
from tests.test_delivery import approved
from tests.test_ones import person, refused

ones_db = test_delivery.ones_db
cast = test_delivery.cast
crew = test_delivery.crew

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
NOW = dt.datetime(2026, 12, 18, 9, 0, tzinfo=dt.UTC)  # a Friday


def test_week_of_is_the_ist_monday() -> None:
    assert extras.week_of(dt.datetime(2026, 12, 18, 9, 0, tzinfo=dt.UTC)) == dt.date(2026, 12, 14)
    # 23:30 UTC on Sunday is Monday morning in India: a new week
    assert extras.week_of(dt.datetime(2026, 12, 20, 23, 30, tzinfo=dt.UTC)) == dt.date(2026, 12, 21)


@pytest.fixture
def memory_store(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], bytes]:
    files: dict[tuple[str, str], bytes] = {}
    monkeypatch.setattr(attachments.store, "put", lambda b, k, d: files.__setitem__((b, k), d))
    monkeypatch.setattr(attachments.store, "get", lambda b, k: files[(b, k)])
    monkeypatch.setattr(attachments.store, "delete", lambda b, k: files.pop((b, k), None))
    return files


@pytest.mark.stack
def test_evidence_owner_only_quarantined_and_opened_only_when_clean(
    ones_db: Any, crew: dict[str, str], memory_store: dict[tuple[str, str], bytes]
) -> None:
    db = ones_db
    _idea, did = approved(db, crew)
    stranger = person(db)
    refused("owner_only", extras.add_evidence, db, crew["sponsor"], did, "results.pdf", PDF)
    out = extras.add_evidence(db, crew["owner"], did, "results.pdf", PDF)
    row = db.execute(
        "SELECT delivery_id, idea_uuid, state FROM attachments WHERE id = %s", (out["id"],)
    ).fetchone()
    assert (row["delivery_id"], row["idea_uuid"], row["state"]) == (did, None, "quarantine")
    job = db.execute(
        "SELECT payload FROM jobs WHERE type = 'attachment.process' AND dedupe_key = %s",
        (f"attachment:{out['id']}",),
    ).fetchone()
    assert job is not None
    # Not clean: nobody can open it, the owner included.
    refused("not_available", extras.evidence_content, db, crew["owner"], did, out["id"])
    # Clean: everyone on the delivery can open it; a stranger can't even see it exists.
    db.execute("UPDATE attachments SET state = 'clean' WHERE id = %s", (out["id"],))
    s = attachments.get_settings()
    memory_store[(s.s3_bucket_clean, f"att/{out['id']}")] = PDF
    data, mime, _name = extras.evidence_content(db, crew["sponsor"], did, out["id"])
    assert (data, mime) == (PDF, "application/pdf")
    refused("not_found", extras.evidence_content, db, stranger, did, out["id"])
    # Delivery files never reach the idea route's digest.
    assert attachments.digest(db, out["id"]) in ("not_an_idea_file", "switched_off")
    view = extras.evidence(db, service._delivery(db, did), crew["owner"], set())
    assert view[0]["can_open"] and view[0]["can_remove"]
    # Only the uploader (or an admin) removes it; every step is audited with IDs only.
    refused("uploader_only", extras.remove_evidence, db, crew["sponsor"], did, out["id"])
    extras.remove_evidence(db, crew["owner"], did, out["id"])
    actions = [
        r["action"]
        for r in db.execute(
            "SELECT action, after FROM audit_log WHERE entity = %s ORDER BY id", (f"delivery:{did}",)
        ).fetchall()
        if r["action"].startswith("delivery.evidence")
    ]
    assert actions == ["delivery.evidence_added", "delivery.evidence_opened", "delivery.evidence_removed"]
    for r in db.execute("SELECT after FROM audit_log WHERE entity = %s", (f"delivery:{did}",)).fetchall():
        assert "results.pdf" not in json.dumps(r["after"])


@pytest.mark.stack
def test_evidence_waits_for_the_work_to_start(
    ones_db: Any, crew: dict[str, str], memory_store: dict[tuple[str, str], bytes]
) -> None:
    db = ones_db
    _idea, did = test_delivery.started(db, crew)
    db.execute("UPDATE deliveries SET owner_user_id = %s WHERE id = %s", (crew["owner"], did))
    refused("not_open_for_evidence", extras.add_evidence, db, crew["owner"], did, "plan.pdf", PDF)


@pytest.mark.stack
def test_checkin_on_the_fix_track_replaces_within_the_week_and_blocked_tells_the_sponsor(
    ones_db: Any, crew: dict[str, str]
) -> None:
    db = ones_db
    _idea, did = approved(db, crew, "fix")
    refused("owner_only", extras.check_in, db, crew["sponsor"], did, {"status": "on_track"}, NOW)
    refused("status_required", extras.check_in, db, crew["owner"], did, {"status": "great"}, NOW)
    first = extras.check_in(db, crew["owner"], did, {"status": "on_track"}, NOW)
    again = extras.check_in(
        db, crew["owner"], did, {"status": "blocked", "note": "Waiting for the AMC file layout"}, NOW
    )
    assert first["id"] == again["id"] and again["week_of"] == "2026-12-14"
    d = service._delivery(db, did)
    view = extras.checkins(db, d, crew["owner"], set(), NOW)
    assert view["replied_this_week"] and view["recent"][0]["status"] == "blocked"
    assert view["recent"][0]["note"] == "Waiting for the AMC file layout"
    stored = db.execute(
        "SELECT note_encrypted FROM delivery_checkins WHERE id = %s", (first["id"],)
    ).fetchone()
    assert b"AMC file layout" not in bytes(stored["note_encrypted"])  # sealed at rest
    routed = db.execute(
        "SELECT payload FROM jobs WHERE type = 'comms.route' AND payload->>'event' = 'delivery.checkin_blocked'"
    ).fetchall()
    assert routed and crew["sponsor"] in routed[-1]["payload"]["refs"]["current_owner_ids"]


@pytest.mark.stack
def test_checkin_is_for_the_fix_track_only(ones_db: Any, crew: dict[str, str]) -> None:
    db = ones_db
    _idea, did = approved(db, crew)  # a build
    refused("owner_only", extras.check_in, db, crew["owner"], did, {"status": "on_track"}, NOW)
