"""Automatic switch-offs outside the gateway (§7.6 "Flips itself when"). Run by the worker's ticker every minute.

- `attachments.upload`: the virus scanner has not answered for 5 minutes. Files already uploaded are untouched.
- `capture.voice`: outside dev and test, voice notes are on while `SPEECH_MODE` is `fake` (DEC-096, BLD-C007): a
  sample sentence would stand in for people's words; or while `local` has no isolated speech service
  (`SPEECH_ENGINE_URL`, BLD-C012). Also checked once when the worker starts.
- `capture.voice` and `speech.hosted`: outside dev and test, `SPEECH_MODE` is `sarvam` (DEC-108, non-negotiable 2's
  voice exception) and `SARVAM_API_KEY` is missing from the worker's env: both go off with the reason "Sarvam key
  missing (automatic)", which the go/no-go report repeats word for word (BLD-C115). This guard FLIPS the switches:
  an audited automatic switch-off. Nothing turns them back on when the key arrives; a person puts the key in the
  worker's env, restarts the worker and switches both on from the Admin page with a reason.
- `comms.email`: more than 5% of the email sent in the last hour bounced (the receiving server refused it), with
  at least 20 emails in that hour so one bad address cannot stop all mail. Only refusals the SMTP server gives at
  send time count; the Graph mailbox's delivery reports are not read on day one.
- `comms.email`: email through Graph cannot go at all (BLD-A243): the token is refused or out of reach, the Graph
  settings are missing, or Graph's send answers 401 (after a fresh token), 403 or 404. The send loop calls
  `email_stopped` at once, on the first such answer, with the code and the HTTP status in the reason. Emails stay
  queued, none spends a try; a person fixes the cause and switches `comms.email` back on.

Each flip is audited (`alert.kill_switch_auto`) and logged as an error so the product lead and InfoSec hear of it.
Nothing switches itself back on: a person checks the cause and flips it back from the Admin page.

Not a switch-off: on every tick where `ai.all` and `agent.gatekeeper` are both on, the file checks waiting for the
gatekeeper are made due now (`waiting_files`, BLD-C226), so a file is checked within a tick of a switch-on from
the Admin page, the CLI or anywhere else, and after a worker starts with the assistant already on.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from psycopg.types.json import Jsonb

from core import killswitch
from core.config import get_settings
from core.db import Conn
from core.logging import get_logger

log = get_logger("watch")
ACTOR = "process:watch"
SARVAM_KEY_MISSING = "Sarvam key missing (automatic)"  # the go/no-go row says "off: " + this (BLD-C115)
SCANNER_DOWN_S = 300.0
BOUNCE_SHARE = 0.05
BOUNCE_MIN_SENT = 20
# SMTP refusals that mean the address or message was rejected for good (error codes are exception class names).
BOUNCE_CODES = ("smtprecipientsrefused", "smtpdataerror")


def switch_off(conn: Conn, name: str, reason: str, actor: str = ACTOR) -> bool:
    killswitch.clear_cache()
    if not killswitch.is_on(name, conn):
        return False
    killswitch.set_switch(conn, name, "off", reason=reason, actor=actor)
    killswitch.clear_cache()
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'alert.kill_switch_auto', %s, %s)",
        (actor, f"kill_switch:{name}", Jsonb({"state": "off"})),
    )
    log.error("watch.switched_off", switch=name)
    return True


def email_stopped(conn: Conn, code: str, status: int | None) -> bool:
    """Email through Graph cannot go (BLD-A243): `comms.email` off, audited, with the code and status as the reason
    (a code is the status family, never Graph's text). Called by the send loops, not the ticker."""
    where = f"{code} (HTTP {status})" if status else code
    return switch_off(conn, "comms.email", f"Email through Graph stopped: {where} (automatic)")


class Watch:
    def __init__(
        self, ping: Callable[[], bool] | None = None, clock: Callable[[], float] = time.monotonic
    ) -> None:
        if ping is None:
            from attachments.clamav import ping as clamav_ping

            ping = clamav_ping
        self.ping, self.clock = ping, clock
        self.scanner_down_since: float | None = None

    def scanner(self, conn: Conn) -> bool:
        if self.ping():
            self.scanner_down_since = None
            return False
        now = self.clock()
        if self.scanner_down_since is None:
            self.scanner_down_since = now
            log.warning("watch.scanner_unreachable")
            return False
        if now - self.scanner_down_since < SCANNER_DOWN_S:
            return False
        return switch_off(conn, "attachments.upload", "Virus scanner unreachable for 5 minutes (automatic)")

    @staticmethod
    def bounces(conn: Conn) -> bool:
        # Only email since the switch last changed (or the last hour, if later): bounces from before a person
        # switched email back on must not switch it off again (B8 review). A failed row's `send_after` is its
        # failure time plus 5 minutes (comms/send.py).
        row = conn.execute(
            "WITH since AS (SELECT greatest(now() - interval '1 hour', "
            "(SELECT changed_at FROM kill_switches WHERE name = 'comms.email')) AS t) "
            "SELECT count(*) FILTER (WHERE state IN ('sent', 'read') AND sent_at > (SELECT t FROM since)) AS sent, "
            "count(*) FILTER (WHERE state = 'failed' AND error_code = ANY(%s) "
            "AND send_after - interval '5 minutes' > (SELECT t FROM since)) AS bounced "
            "FROM notifications WHERE channel = 'email'",
            (list(BOUNCE_CODES),),
        ).fetchone()
        sent, bounced = (int(row["sent"]), int(row["bounced"])) if row else (0, 0)
        total = sent + bounced
        if total < BOUNCE_MIN_SENT or bounced / total <= BOUNCE_SHARE:
            return False
        return switch_off(conn, "comms.email", "More than 5% of email bounced in the last hour (automatic)")

    @staticmethod
    def speech_route(conn: Conn) -> bool:
        """Voice notes off outside dev and test when the route is fake (BLD-C007), the engine would run inside the
        worker instead of the isolated speech service (BLD-C012), or the Sarvam route has no key (BLD-C115: then
        hosted speech goes off too)."""
        s = get_settings()
        if not s.is_production_like:
            return False
        if s.speech_mode == "sarvam" and not s.sarvam_api_key.strip():
            voice = switch_off(conn, "capture.voice", SARVAM_KEY_MISSING)
            hosted = switch_off(conn, "speech.hosted", SARVAM_KEY_MISSING)
            return voice or hosted
        if s.speech_mode == "fake":
            reason = "SPEECH_MODE is fake outside dev and test (automatic, DEC-096)"
        elif s.speech_mode == "local" and not s.speech_engine_url:
            reason = "Speech engine not isolated: SPEECH_ENGINE_URL unset outside dev and test (automatic, BLD-C012)"
        else:
            return False
        return switch_off(conn, "capture.voice", reason)

    @staticmethod
    def waiting_files(conn: Conn) -> bool:
        """File checks waiting for the gatekeeper run now, batched, while both switches are on (BLD-C226)."""
        from attachments.files import requeue_waiting

        return requeue_waiting(conn) > 0

    @staticmethod
    def unchecked_texts(conn: Conn) -> bool:
        """Sealed texts written while the assistant was off get the gatekeeper's check, a few re-checks at a time,
        while both switches are on (DEC-131 (3), BLD-C231)."""
        from hide.recheck import queue_unchecked

        return queue_unchecked(conn) > 0

    def run(self, conn: Conn) -> None:
        for check in (
            self.scanner,
            self.bounces,
            self.speech_route,
            self.waiting_files,
            self.unchecked_texts,
        ):
            try:
                check(conn)
            except Exception as exc:  # one watch failing must not stop the other, or the ticker
                log.warning("watch.check_failed", error_type=type(exc).__name__)
