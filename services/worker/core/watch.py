"""Automatic switch-offs outside the gateway (§7.6 "Flips itself when"). Run by the worker's ticker every minute.

- `attachments.upload`: the virus scanner has not answered for 5 minutes. Files already uploaded are untouched.
- `comms.email`: more than 5% of the email sent in the last hour bounced (the receiving server refused it), with
  at least 20 emails in that hour so one bad address cannot stop all mail.

Each flip is audited (`alert.kill_switch_auto`) and logged as an error so the product lead and InfoSec hear of it.
Nothing switches itself back on: a person checks the cause and flips it back from the Admin page.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from psycopg.types.json import Jsonb

from core import killswitch
from core.db import Conn
from core.logging import get_logger

log = get_logger("watch")
ACTOR = "process:watch"
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
        row = conn.execute(
            "SELECT count(*) FILTER (WHERE state IN ('sent', 'read') AND sent_at > now() - interval '1 hour') AS sent, "
            "count(*) FILTER (WHERE state = 'failed' AND error_code = ANY(%s) "
            "AND send_after > now() - interval '65 minutes') AS bounced "
            "FROM notifications WHERE channel = 'email'",
            (list(BOUNCE_CODES),),
        ).fetchone()
        sent, bounced = (int(row["sent"]), int(row["bounced"])) if row else (0, 0)
        total = sent + bounced
        if total < BOUNCE_MIN_SENT or bounced / total <= BOUNCE_SHARE:
            return False
        return switch_off(conn, "comms.email", "More than 5% of email bounced in the last hour (automatic)")

    def run(self, conn: Conn) -> None:
        for check in (self.scanner, self.bounces):
            try:
                check(conn)
            except Exception as exc:  # one watch failing must not stop the other, or the ticker
                log.warning("watch.check_failed", error_type=type(exc).__name__)
