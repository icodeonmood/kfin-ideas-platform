"""The scan (B4): outcomes from the gatekeeper's output and the thresholds (ready, blocked, redirect, held),
AT-B4-06 (after a whole scan the idea sentence is in no plain column), AT-B4-09 (p95 under 15 s with a
realistic fake latency; the step is recorded as it moves) and AT-B4-10 (route down or `ai.all` off: saved,
`scan.async` retries, the person is told, the desk sees "awaiting scan"; when retries run out, `manual`)."""

from __future__ import annotations

import random
import statistics
import threading
import uuid
from typing import Any

import generators as g
import pytest

from core import killswitch
from core.config import get_settings
from core.crypto import encrypt_json
from core.db import connect
from gateway import limits
from gateway.routes import FAKE_SCRIPT, RouteError
from jobs import handlers  # noqa: F401 - registers handlers
from jobs.runner import run_one
from scan import pipeline
from scan.view import view
from tests.helpers import db_url, tables_containing

pytestmark = pytest.mark.stack
SENTENCE = "Branch staff photocopy every SIP mandate twice before it is couriered to Hyderabad"
_n = iter(range(700, 999))


def canvas(details: str, **extra: Any) -> dict[str, Any]:
    c: dict[str, Any] = {
        "mode": "quick",
        "kind": None,
        "one_line": "",
        "details": details,
        "who": {"segments": ["kfin_teams"], "frequency_or_reach": "", "today_alternative": ""},
        "value": {
            "category": "cost_saving",
            "play": None,
            "estimate": {"hours_saved_per_month": None, "note": ""},
            "basis": None,
        },
        "ecosystem": {"solved_elsewhere": None, "references": [], "our_advantage": ""},
        "solution": {"approach": "", "needs": "", "risks": ""},
        "visibility": "org",
        "visibility_reason": "",
        "declarations": {"no_personal_data": True, "own_work_or_credited": True, "ip_terms": True},
        "provenance": {},
    }
    c.update(extra)
    return c


def submitted(db: Any, c: dict[str, Any]) -> str:
    n = next(_n)
    idea_uuid = str(uuid.uuid4())
    db.execute(
        "INSERT INTO ideas (id, idea_id, submission_id, stage, capture_mode, contributor_code, raw_encrypted, "
        "submitted_at) VALUES (%s, %s, %s, 'scanning', 'quick', 'CTR-0a1b2c', %s, now())",
        (idea_uuid, f"IDEA-2026-000{n}", f"SUB-2026-000{n}", encrypt_json(c, idea_uuid)),
    )
    return idea_uuid


def scan_row(db: Any, idea_uuid: str) -> dict[str, Any]:
    return dict(db.execute("SELECT * FROM scans WHERE idea_uuid = %s", (idea_uuid,)).fetchone())


@pytest.fixture(autouse=True)
def clean() -> Any:
    killswitch.clear_cache()
    limits.reset()
    FAKE_SCRIPT.clear()
    yield
    FAKE_SCRIPT.clear()
    killswitch.clear_cache()


def test_ready_scan_keeps_text_out_of_plain_columns(db: Any) -> None:
    rng = random.Random(101)
    stranger = g.person_name(rng)
    idea = submitted(db, canvas(f"{SENTENCE}. {stranger} from the Pune branch counted 400 a week."))
    assert pipeline.run(db, idea) == "done"
    row = scan_row(db, idea)
    assert (row["state"], row["step"], row["outcome"]) == ("done", "done", "ready")
    shown = view(db, idea, "real")
    assert shown is not None and shown["outcome"] == "ready"
    paths = {s["path"] for s in shown["ready"]["suggested"]}
    assert {"kind", "one_line"} <= paths  # quick capture: the assistant suggests these
    assert stranger in next(s["value"] for s in shown["ready"]["suggested"] if s["path"] == "one_line")
    agents = [r["agent"] for r in db.execute("SELECT agent FROM llm_calls ORDER BY id").fetchall()]
    assert agents == ["gatekeeper", "canvas-assist"]
    # AT-B4-06: the sentence and the name are in no plain column anywhere in the database.
    assert tables_containing(db, SENTENCE) == []
    assert tables_containing(db, stranger) == []


def test_investor_details_block_and_only_the_owner_sees_them(db: Any) -> None:
    rng = random.Random(102)
    person = g.person_name(rng)
    idea = submitted(db, canvas(f"{SENTENCE}. The investor {person} complained twice about the delay."))
    pipeline.run(db, idea)
    assert scan_row(db, idea)["outcome"] == "blocked"
    assert db.execute("SELECT stage FROM ideas WHERE id = %s", (idea,)).fetchone()["stage"] == "blocked"
    owner = view(db, idea, "real")
    other = view(db, idea, "neutral")
    assert owner and other
    assert person in owner["blocked"]["spans"][0]["quote"]
    assert person not in str(other) and "a person" in other["blocked"]["spans"][0]["quote"]
    assert [r["agent"] for r in db.execute("SELECT agent FROM llm_calls").fetchall()] == ["gatekeeper"]

    # "This is not personal data": it goes through (flagged for the reviewer) without a second gatekeeper call.
    db.execute(
        "UPDATE scans SET overrides = '{\"not_personal_data\": true}', state = 'queued' WHERE idea_uuid = %s",
        (idea,),
    )
    db.execute("UPDATE ideas SET stage = 'scanning' WHERE id = %s", (idea,))
    pipeline.run(db, idea)
    assert scan_row(db, idea)["outcome"] == "ready"
    assert [r["agent"] for r in db.execute("SELECT agent FROM llm_calls ORDER BY id").fetchall()] == [
        "gatekeeper",
        "canvas-assist",
    ]


def test_redirect_and_override_and_hold(db: Any) -> None:
    idea = submitted(
        db, canvas("My laptop VPN is not working since Monday and I cannot reach the CAS screen.")
    )
    pipeline.run(db, idea)
    shown = view(db, idea, "real")
    assert shown and shown["outcome"] == "redirect"
    assert shown["redirect"]["team"] == "IT helpdesk" and shown["redirect"]["override_reason_min_chars"] == 15
    db.execute(
        "UPDATE scans SET overrides = '{\"is_an_idea\": true}', state = 'queued' WHERE idea_uuid = %s",
        (idea,),
    )
    pipeline.run(db, idea)
    assert scan_row(db, idea)["outcome"] == "ready"

    held = submitted(db, canvas("test test test, please ignore this one"))
    pipeline.run(db, held)
    assert scan_row(db, held)["outcome"] == "held"


def test_route_down_saves_and_retries_async(db: Any) -> None:
    db.execute("DELETE FROM jobs")
    idea = submitted(db, canvas(SENTENCE))
    FAKE_SCRIPT.append(RouteError("connection"))
    assert pipeline.run(db, idea) == "waiting"
    row = scan_row(db, idea)
    assert row["state"] == "waiting" and row["error_code"] == "connection"
    assert view(db, idea, "real")["state"] == "waiting"  # the person is told they will hear within the hour
    idea_row = db.execute("SELECT stage, raw_encrypted FROM ideas WHERE id = %s", (idea,)).fetchone()
    assert idea_row["stage"] == "scanning" and idea_row["raw_encrypted"] is not None
    job = db.execute(
        "SELECT type, run_at > now() + interval '50 seconds' AS later FROM jobs WHERE type = 'scan.async'"
    ).fetchone()
    assert job == {"type": "scan.async", "later": True}

    db.execute("UPDATE jobs SET run_at = now() WHERE type = 'scan.async'")
    assert run_one(db, "test-worker")
    assert scan_row(db, idea)["outcome"] == "ready"


def test_ai_off_queues_until_it_is_back(db: Any) -> None:
    db.execute("DELETE FROM jobs")
    killswitch.set_switch(db, "ai.all", "off", reason="Testing the scan fallback", actor="REV-0001")
    killswitch.clear_cache()
    idea = submitted(db, canvas(SENTENCE))
    assert pipeline.run(db, idea) == "waiting"
    db.execute("UPDATE jobs SET run_at = now() WHERE type = 'scan.async'")
    assert run_one(db, "test-worker")  # still off: waits again without using a retry
    jobs = db.execute("SELECT state, attempts FROM jobs WHERE type = 'scan.async' ORDER BY id").fetchall()
    assert [j["state"] for j in jobs] == ["done", "queued"]
    killswitch.set_switch(db, "ai.all", "on", reason="Testing the scan fallback", actor="REV-0001")
    killswitch.clear_cache()
    db.execute("UPDATE jobs SET run_at = now() WHERE state = 'queued'")
    assert run_one(db, "test-worker")
    assert scan_row(db, idea)["outcome"] == "ready"


def test_retries_exhausted_go_to_the_desk(db: Any) -> None:
    db.execute("DELETE FROM jobs")
    idea = submitted(db, canvas(SENTENCE))
    FAKE_SCRIPT.extend([RouteError("connection"), RouteError("connection")])
    pipeline.run(db, idea)
    db.execute("UPDATE jobs SET run_at = now(), max_attempts = 1 WHERE type = 'scan.async'")
    assert run_one(db, "test-worker")
    row = scan_row(db, idea)
    assert row["state"] == "manual" and row["error_code"] == "retries_exhausted"
    assert db.execute("SELECT 1 FROM audit_log WHERE action = 'alert.scan_manual'").fetchone()


def test_p95_under_15_seconds_with_realistic_latency(db: Any, test_database: str, monkeypatch: Any) -> None:
    monkeypatch.setattr(get_settings(), "llm_fake_latency", "realistic")
    steps: list[str] = []
    real_set = pipeline._set

    def spy(conn: Any, idea_uuid: str, **cols: Any) -> None:
        if "step" in cols and idea_uuid == first:
            steps.append(cols["step"])
        real_set(conn, idea_uuid, **cols)

    monkeypatch.setattr(pipeline, "_set", spy)
    ideas = [submitted(db, canvas(f"{SENTENCE} (case {i})")) for i in range(20)]
    first = ideas[0]

    def one(idea: str) -> None:
        with connect(db_url(test_database), autocommit=True) as c:
            pipeline.run(c, idea)

    threads = [threading.Thread(target=one, args=(i,)) for i in ideas]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    rows = db.execute(
        "SELECT outcome, duration_ms FROM scans WHERE idea_uuid = ANY(%s::uuid[])", (ideas,)
    ).fetchall()
    assert len(rows) == 20 and all(r["outcome"] == "ready" for r in rows)
    p95 = statistics.quantiles([r["duration_ms"] for r in rows], n=20)[18]
    assert p95 <= 15_000, p95
    assert steps == ["gatekeeper", "canvas_assist", "done"]  # the waiting screen shows each step
