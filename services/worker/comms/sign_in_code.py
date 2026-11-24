"""The sign-in code email (L-AUTH.rules/2-3), the email-code route of sign-in, built behind `auth.email_code`
(off until InfoSec approves it, BLD-E002). The web app generates the code and keeps only its hash; it passes the
code here once, to send at once. The code is never queued, stored or logged: no notification row, no job payload,
no log field. `comms.email` off stops it like any other email."""

from __future__ import annotations

import uuid

from comms import email_html
from comms.send import deliver
from comms.templates import load
from core import killswitch
from core.config import get_settings
from core.db import Conn
from core.logging import get_logger

log = get_logger("comms.sign_in_code")
TEMPLATE = "sign-in-code"


class CodeEmailRefused(Exception):
    def __init__(self, code: str, status: int) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


def send(conn: Conn, user_id: str, code: str, valid_minutes: int) -> None:
    uuid.UUID(user_id)  # ValueError for anything else: the endpoint answers 400
    if not (code.isdigit() and 4 <= len(code) <= 10) or not 1 <= valid_minutes <= 60:
        raise CodeEmailRefused("bad_request", 400)
    if not killswitch.is_on("auth.email_code", conn):
        raise CodeEmailRefused("paused", 503)
    if not killswitch.is_on("comms.email", conn):
        raise CodeEmailRefused("email_paused", 503)
    row = conn.execute("SELECT email, name, active FROM users WHERE id = %s", (user_id,)).fetchone()
    if row is None or not row["active"]:
        raise CodeEmailRefused("no_recipient", 404)
    first = str(row["name"]).split()[0] if row["name"] else "there"
    data = {"recipient": {"first_name": first}, "code": {"value": code, "valid_minutes": valid_minutes}}
    deliver(str(row["email"]), email_html.compose(load(TEMPLATE), data, get_settings().app_base_url))
    log.info("auth.code_emailed", user_id=user_id)
