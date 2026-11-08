"""Automatic switch-offs outside the gateway (§7.6): the scanner unreachable for 5 minutes turns off
`attachments.upload`; more than 5% bounced email in an hour (at least 20 sent) turns off `comms.email`. Each flip
is audited; nothing turns itself back on."""

from __future__ import annotations

import secrets
from typing import Any

import pytest

from core import killswitch
from core.watch import Watch

pytestmark = pytest.mark.stack


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def _state(db: Any, name: str) -> str:
    return str(db.execute("SELECT state FROM kill_switches WHERE name = %s", (name,)).fetchone()["state"])


def test_scanner_unreachable_for_five_minutes_turns_uploads_off(db: Any) -> None:
    killswitch.clear_cache()
    up = {"ok": False}
    clock = Clock()
    w = Watch(ping=lambda: up["ok"], clock=clock)
    assert w.scanner(db) is False  # first miss: start counting
    clock.t += 299
    assert w.scanner(db) is False and _state(db, "attachments.upload") == "on"
    up["ok"] = True
    assert w.scanner(db) is False and w.scanner_down_since is None  # it came back: the count restarts
    up["ok"] = False
    w.scanner(db)
    clock.t += 300
    assert w.scanner(db) is True and _state(db, "attachments.upload") == "off"
    audit = db.execute(
        "SELECT actor FROM audit_log WHERE action = 'alert.kill_switch_auto' AND entity = 'kill_switch:attachments.upload'"
    ).fetchone()
    assert audit["actor"] == "process:watch"
    up["ok"] = True
    w.scanner(db)
    assert _state(db, "attachments.upload") == "off"  # never back on by itself
    killswitch.set_switch(db, "attachments.upload", "on", reason="Scanner back, checked", actor="REV-0001")
    killswitch.clear_cache()


def _mail(db: Any, user: str, sent: int, bounced: int) -> None:
    for _ in range(sent):
        db.execute(
            "INSERT INTO notifications (user_id, channel, template, event, urgency, state, sent_at, send_after) "
            "VALUES (%s, 'email', 'submitted', 'idea.submitted', 'immediate', 'sent', now(), now())",
            (user,),
        )
    for _ in range(bounced):
        db.execute(
            "INSERT INTO notifications (user_id, channel, template, event, urgency, state, error_code, send_after) "
            "VALUES (%s, 'email', 'submitted', 'idea.submitted', 'immediate', 'failed', 'smtprecipientsrefused', "
            "now() + interval '5 minutes')",
            (user,),
        )


@pytest.mark.parametrize(
    ("sent", "bounced", "flips"),
    [(30, 1, False), (5, 5, False), (19, 2, True)],  # 3% · fewer than 20 emails · 9.5%
)
def test_bounces_over_five_percent_turn_email_off(db: Any, sent: int, bounced: int, flips: bool) -> None:
    killswitch.clear_cache()
    db.execute("DELETE FROM notifications")
    user = db.execute(
        "INSERT INTO users (emp_id_hash, name, email, source) VALUES (%s, 'Mail Person', %s, 'hr') RETURNING id",
        (f"test:{secrets.token_hex(3)}", f"m.{secrets.token_hex(3)}@kfintech.example"),
    ).fetchone()["id"]
    _mail(db, user, sent, bounced)
    assert Watch(ping=lambda: True).bounces(db) is flips
    assert _state(db, "comms.email") == ("off" if flips else "on")
    killswitch.set_switch(db, "comms.email", "on", reason="Reset after the bounce test", actor="REV-0001")
    killswitch.clear_cache()


def test_an_agent_that_fails_its_golden_set_on_deploy_switches_off(db: Any) -> None:
    from evalrunner.__main__ import switch_off_failing

    killswitch.clear_cache()
    results = [{"agent": "judge", "passed": False}, {"agent": "gatekeeper", "passed": True}]
    assert switch_off_failing(db, results, "fake") == []  # fake mode cannot measure a model
    assert switch_off_failing(db, results, "anthropic") == ["agent.judge"]
    assert _state(db, "agent.judge") == "off" and _state(db, "agent.gatekeeper") == "on"
    assert db.execute(
        "SELECT 1 FROM audit_log WHERE action = 'alert.kill_switch_auto' AND actor = 'process:eval'"
    ).fetchone()
    killswitch.set_switch(db, "agent.judge", "on", reason="Reset after the eval test", actor="REV-0001")
    killswitch.clear_cache()
