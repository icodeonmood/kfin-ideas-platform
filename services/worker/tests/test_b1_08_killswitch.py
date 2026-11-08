"""AT-B1-08: with kill switch `submissions` off, `POST /api/submissions` returns 503 with a banner message while
GET routes still work; the change needs a reason and is written to `audit_log`."""

import json
import time
import urllib.error
import urllib.request

import pytest

from core import killswitch
from core.db import connect
from tests import helpers

pytestmark = pytest.mark.stack

WEB = "http://localhost:3000"


def _request(method: str, path: str) -> tuple[int, dict[str, object]]:
    req = urllib.request.Request(WEB + path, method=method, data=b"{}" if method != "GET" else None)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"{}")


def test_change_needs_a_reason_and_is_audited(test_database: str) -> None:
    with connect(helpers.db_url(test_database), autocommit=True) as conn:
        with pytest.raises(killswitch.KillSwitchError):
            killswitch.set_switch(conn, "submissions", "off", reason="", actor="REV-0001")
        with pytest.raises(killswitch.KillSwitchError):
            killswitch.set_switch(conn, "submissions", "off", reason="too short", actor="REV-0001")
        with pytest.raises(killswitch.KillSwitchError):
            killswitch.set_switch(
                conn, "no.such_switch", "off", reason="testing an unknown switch", actor="REV-0001"
            )
        killswitch.set_switch(conn, "submissions", "off", reason="AT-B1-08 automated test", actor="REV-0001")
        row = conn.execute(
            "SELECT actor, action, before, after, reason FROM audit_log WHERE entity = 'kill_switch:submissions' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row["actor"] == "REV-0001" and row["action"] == "kill_switch.set"
        assert row["before"] == {"state": "on"} and row["after"] == {"state": "off"}
        assert row["reason"] == "AT-B1-08 automated test"
        killswitch.set_switch(
            conn, "submissions", "on", reason="AT-B1-08 automated test done", actor="REV-0001"
        )


def test_python_cache_is_ten_seconds() -> None:
    assert killswitch.CACHE_SECONDS == 10.0


def test_web_refuses_submissions_when_switched_off() -> None:
    """Against the running stack: flips the dev database's switch and always restores it."""
    assert _request("POST", "/api/submissions")[0] == 501  # on: reaches the route (built in B3)
    with connect(autocommit=True) as conn:
        killswitch.set_switch(conn, "submissions", "off", reason="AT-B1-08 automated test", actor="REV-0001")
        try:
            deadline = time.monotonic() + 15  # web caches switch states for up to 10 seconds
            status, body = _request("POST", "/api/submissions")
            while status != 503 and time.monotonic() < deadline:
                time.sleep(0.5)
                status, body = _request("POST", "/api/submissions")
            assert status == 503
            assert body["switch"] == "submissions"
            assert "paused" in str(body["banner"]).lower()
            assert _request("PUT", "/api/submissions/any-draft")[0] == 503

            assert _request("GET", "/api/health") == (200, {"status": "ok"})
            status, body = _request("GET", "/api/status")
            assert status == 200
            assert any(p["switch"] == "submissions" for p in body["paused"])
        finally:
            killswitch.set_switch(
                conn, "submissions", "on", reason="AT-B1-08 automated test done", actor="REV-0001"
            )
        audit = conn.execute(
            "SELECT count(*) AS n FROM audit_log WHERE entity = 'kill_switch:submissions' AND reason LIKE 'AT-B1-08%%'"
        ).fetchone()
        assert audit["n"] >= 2
