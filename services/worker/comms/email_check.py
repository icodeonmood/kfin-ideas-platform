"""One test message through Graph before `comms.email` goes on (BLD-A243; docs/UAT.md, "Email through Graph").

  python -m comms.email_check --to <test mailbox IT names> --actor ops:<staff code>

It sends one fixed test message, with no idea, no person and no template in it, through the transport every email
uses (`comms.send.deliver`), so IT sees the mailbox, the permission and the network rule work before anyone's email
goes out. It never reaches an employee: it refuses any address that belongs to someone in 1% Club. It runs only with
`EMAIL_MODE=graph`. It does not wait for `comms.email`, because it sends nobody's email: it is IT's check, like the
smoke checks. Each run is written to `audit_log` (`comms.email_check`, the result code only). It prints one line and
never the address: `email check: sent` (Graph accepted it), `email check: failed <code>` or `email check: refused …`.
"""

from __future__ import annotations

import argparse
import sys
from email.utils import parseaddr

from psycopg.types.json import Jsonb

from comms import email_html, graph
from comms.send import deliver
from core.config import get_settings
from core.db import Conn, connect
from core.logging import get_logger

log = get_logger("comms.email_check")
SUBJECT = "1% Club email check"
TEXT = (
    "This is a test message from the 1% Club server, sent by IT to check email through the service mailbox.\n\n"
    "Nobody needs to reply.\n"
)
HTML = (
    "<!doctype html><html><body><p>This is a test message from the 1% Club server, sent by IT to check email "
    "through the service mailbox.</p><p>Nobody needs to reply.</p></body></html>"
)


def check(conn: Conn, to: str, actor: str) -> tuple[int, str]:
    """(exit code, the line to print): 0 sent, 1 failed, 2 refused (nothing sent)."""
    if get_settings().email_mode.strip() != "graph":
        return 2, "email check: refused: EMAIL_MODE is not graph"
    address = parseaddr(to)[1].strip()
    if not address or address != to.strip() or address.count("@") != 1:
        return 2, "email check: refused: --to must be one email address"
    taken = conn.execute("SELECT 1 FROM users WHERE lower(email) = lower(%s) LIMIT 1", (address,)).fetchone()
    if taken:
        return (
            2,
            "email check: refused: that address belongs to someone in 1% Club; use the test mailbox IT named",
        )
    status: int | None = 202
    try:
        deliver(address, email_html.Email(subject=SUBJECT, text=TEXT, html=HTML))
        code = "sent"
    except (graph.EmailRetry, graph.EmailRefused) as exc:
        code, status = exc.code, exc.status
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'comms.email_check', 'comms:email', %s)",
        (actor, Jsonb({"result": code, "http_status": status})),
    )
    log.info("comms.email_checked", result_code=code, http_status=status)
    if code == "sent":
        return 0, "email check: sent (Graph accepted it, HTTP 202)"
    return 1, f"email check: failed {code}" + (f" (HTTP {status})" if status else "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m comms.email_check")
    parser.add_argument("--to", required=True, help="the test mailbox IT names, never an employee's")
    parser.add_argument("--actor", required=True, help="ops:<staff code>")
    args = parser.parse_args(argv)
    with connect(autocommit=True) as conn:
        rc, line = check(conn, args.to, args.actor)
    print(line)
    return rc


if __name__ == "__main__":
    sys.exit(main())
