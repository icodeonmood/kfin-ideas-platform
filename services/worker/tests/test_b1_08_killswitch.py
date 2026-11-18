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
from tests.web import WEB

pytestmark = pytest.mark.stack


def _request(method: str, path: str, token: str | None = None) -> tuple[int, dict[str, object]]:
    req = urllib.request.Request(WEB + path, method=method, data=b"{}" if method != "GET" else None)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Cookie", f"ideas_session={token}")
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
    """Against the running stack: flips the dev database's switch and always restores it. Since B2 every
    /api call needs a session, so a synthetic person with a session makes the requests."""
    from tests.web import people

    with connect(autocommit=True) as conn, people(conn) as make:
        token = make().token
        assert _request("POST", "/api/submissions", token)[0] == 201  # on: reaches the route (starts a draft)
        killswitch.set_switch(conn, "submissions", "off", reason="AT-B1-08 automated test", actor="REV-0001")
        try:
            deadline = time.monotonic() + 15  # web caches switch states for up to 10 seconds
            status, body = _request("POST", "/api/submissions", token)
            while status != 503 and time.monotonic() < deadline:
                time.sleep(0.5)
                status, body = _request("POST", "/api/submissions", token)
            assert status == 503
            assert body["switch"] == "submissions"
            assert "paused" in str(body["banner"]).lower()
            assert _request("PUT", "/api/submissions/any-draft", token)[0] == 503

            assert _request("GET", "/api/health") == (200, {"status": "ok"})
            # The proxy and the route handlers are separate bundles, each with its own 10-second switch cache, so
            # /api/status can list the switch a little after the proxy first refused (BLD-A178).
            deadline = time.monotonic() + 15
            status, body = _request("GET", "/api/status", token)
            while time.monotonic() < deadline and not (
                status == 200 and any(p["switch"] == "submissions" for p in body.get("paused", []))
            ):
                time.sleep(0.5)
                status, body = _request("GET", "/api/status", token)
            assert status == 200
            assert any(p["switch"] == "submissions" for p in body["paused"])
        finally:
            killswitch.set_switch(
                conn, "submissions", "on", reason="AT-B1-08 automated test done", actor="REV-0001"
            )
            # Leave the stack as we found it: wait out the web app's 10-second switch cache.
            deadline = time.monotonic() + 15
            while _request("POST", "/api/submissions", token)[0] == 503 and time.monotonic() < deadline:
                time.sleep(0.5)
        audit = conn.execute(
            "SELECT count(*) AS n FROM audit_log WHERE entity = 'kill_switch:submissions' AND reason LIKE 'AT-B1-08%%'"
        ).fetchone()
        assert audit["n"] >= 2
