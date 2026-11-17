"""What the admin path shares: the pack's error shape (A-API.conventions/2), the role check, the audit row, the
idea and person lookups, staff-written text checks, and who is credited on an idea.

Messages here are shown on the admin page under the field they name. They are staff-facing, not drawn by the pack
(`L-DECIDE.after` OPEN, `L-IMPACT/8` OPEN), and are listed for HR in docs/BUILD_LOG.md (BLD-E008).
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from psycopg.types.json import Jsonb

from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from pii.patterns import blocks

log = get_logger("programme")

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
IDEA_REF = re.compile(r"^IDEA-[0-9]{4}-[0-9]{6}$")
REASON_MIN, REASON_MAX = 10, 500

MSG_FORBIDDEN = "You can't do this. Ask an admin."
MSG_NO_IDEA = "No idea has that reference. Check it reads like IDEA-2026-000123."
MSG_NO_PERSON = "No one active has that work email."
MSG_REASON = "Give a reason of at least 10 characters."
MSG_DETAILS = "Take out the customer's details. Write it without them."


class Refused(Exception):
    """A refusal in the pack's shape: `{error: {code, message, field?}}`. Codes are IDs; messages are this
    package's own copy; a person's text never goes in one."""

    def __init__(self, status: int, code: str, message: str = "", *, field: str | None = None) -> None:
        super().__init__(code)
        self.status, self.code, self.message, self.field = status, code, message, field

    def body(self) -> dict[str, Any]:
        err: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.field:
            err["field"] = self.field
        return {"error": err}


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def roles(conn: Conn, user_id: str) -> set[str]:
    """The person's live org-wide grants (a build-team grant is per idea and gives no admin power)."""
    rows = conn.execute(
        "SELECT g.role FROM role_grants g JOIN users u ON u.id = g.user_id AND u.active WHERE g.user_id = %s "
        "AND g.scope_id IS NULL AND g.valid_from <= now() AND (g.valid_to IS NULL OR g.valid_to > now())",
        (user_id,),
    ).fetchall()
    return {str(r["role"]) for r in rows}


def need(conn: Conn, user_id: str, allowed: set[str]) -> set[str]:
    """Defence in depth: the web app checked the capability; the worker checks the grants again."""
    have = roles(conn, user_id)
    if not have & allowed:
        raise Refused(403, "forbidden", MSG_FORBIDDEN)
    return have


def audit(
    conn: Conn,
    actor: str,
    action: str,
    entity: str,
    after: dict[str, Any] | None = None,
    *,
    before: dict[str, Any] | None = None,
    reason: str | None = None,
) -> None:
    """One audit row. `actor` is a users.id (written as "user:<id>") or a "system:<name>" process. `after` and
    `before` hold IDs, enums and numbers only; `reason` is the staff-written reason, as for role changes."""
    who = actor if actor.startswith("system:") else f"user:{actor}"
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, before, after, reason) VALUES (%s, %s, %s, %s, %s, %s)",
        (who, action, entity, Jsonb(before) if before is not None else None,
         Jsonb(after) if after is not None else None, reason),
    )  # fmt: skip


def idea(conn: Conn, ref: Any, *, lock: bool = False) -> dict[str, Any]:
    if not isinstance(ref, str) or not IDEA_REF.match(ref.strip()):
        raise Refused(404, "not_found", MSG_NO_IDEA, field="idea")
    sql = (
        "SELECT id, idea_id, status, title, contributor_code, status_changed_at, shared_at FROM ideas "
        "WHERE idea_id = %s"
    )
    row = conn.execute(sql + (" FOR UPDATE" if lock else ""), (ref.strip(),)).fetchone()
    if row is None:
        raise Refused(404, "not_found", MSG_NO_IDEA, field="idea")
    return dict(row)


def user_by_email(conn: Conn, email: Any, field: str) -> str:
    if not isinstance(email, str) or not email.strip() or len(email) > 320:
        raise Refused(422, "email_required", "Enter a work email.", field=field)
    row = conn.execute(
        "SELECT id FROM users WHERE lower(email) = lower(%s) AND active", (email.strip(),)
    ).fetchone()
    if row is None:
        raise Refused(404, "no_such_person", MSG_NO_PERSON, field=field)
    return str(row["id"])


def text(value: Any, field: str, *, min_chars: int, max_chars: int, message: str) -> str:
    """Staff-written text (a reason, a team name, a measurement's line): trimmed, within its lengths, and free of
    anything the shared hidden-detail patterns block (customer identifiers never reach a table others read)."""
    clean = value.strip() if isinstance(value, str) else ""
    if not min_chars <= len(clean) <= max_chars:
        raise Refused(422, f"{field}_length", message, field=field)
    if blocks(clean, kfin_domains=get_settings().kfin_domains):
        raise Refused(422, "personal_data", MSG_DETAILS, field=field)
    return clean


def reason(value: Any, field: str = "reason") -> str:
    return text(value, field, min_chars=REASON_MIN, max_chars=REASON_MAX, message=MSG_REASON)


def owner_user(conn: Conn, contributor_code: Any) -> str | None:
    row = conn.execute(
        "SELECT m.user_id FROM contributor_map m JOIN users u ON u.id = m.user_id AND u.active "
        "WHERE m.contributor_code = %s",
        (contributor_code,),
    ).fetchone()
    return str(row["user_id"]) if row else None


def credited_users(conn: Conn, idea_uuid: Any) -> list[str]:
    """Everyone credited on an idea (E-ENTITIES Idea.credited, L-MERGE.effects/2): its sharer, and the sharer of
    every idea merged into it whose merge still stands. Active people only."""
    rows = conn.execute(
        "SELECT DISTINCT m.user_id FROM ideas i JOIN contributor_map m ON m.contributor_code = i.contributor_code "
        "JOIN users u ON u.id = m.user_id AND u.active WHERE i.id = %(idea)s OR i.id IN (SELECT merged_idea_uuid "
        "FROM merges WHERE lead_idea_uuid = %(idea)s AND reversed_at IS NULL)",
        {"idea": str(idea_uuid)},
    ).fetchall()
    return sorted(str(r["user_id"]) for r in rows)


def crew_users(conn: Conn, idea_uuid: Any) -> list[str]:
    """The idea's crew today (people who left are not told any more)."""
    rows = conn.execute(
        "SELECT DISTINCT m.user_id FROM crew_members c JOIN contributor_map m ON m.contributor_code = c.contributor_code "
        "JOIN users u ON u.id = m.user_id AND u.active WHERE c.idea_uuid = %s AND c.left_at IS NULL",
        (str(idea_uuid),),
    ).fetchall()
    return sorted(str(r["user_id"]) for r in rows)


def build_team_users(conn: Conn, idea_ref: str) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT g.user_id FROM role_grants g JOIN users u ON u.id = g.user_id AND u.active "
        "WHERE g.role = 'build_team' AND g.scope_id = %s AND g.valid_from <= now() "
        "AND (g.valid_to IS NULL OR g.valid_to > now())",
        (idea_ref,),
    ).fetchall()
    return sorted(str(r["user_id"]) for r in rows)


def admin_users(conn: Conn) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT g.user_id FROM role_grants g JOIN users u ON u.id = g.user_id AND u.active "
        "WHERE g.role = 'admin' AND g.scope_id IS NULL AND g.valid_from <= now() "
        "AND (g.valid_to IS NULL OR g.valid_to > now())"
    ).fetchall()
    return sorted(str(r["user_id"]) for r in rows)


def promise(section: str, key: str, default: Any) -> Any:
    """A number the product promises, from the company repo's rules/promises.md (BLD-A181); the pack's value if the
    file cannot be read (logged by name only)."""
    from rules import load_rule

    try:
        return load_rule(get_settings().company_repo_path, "promises").data[section][key]
    except Exception:  # an unreadable rule must not stop the admin path; the pack's own value stands in
        log.warning("programme.promise_default", rule_section=section, rule_key=key)
        return default


def day_label(ts: dt.datetime, *, year: bool = False) -> str:
    """ "18 Nov" (L-IMPACT/4 "Due 18 Nov"), in India time; "18 Nov 2026" with the year."""
    d = ts.astimezone(IST)
    return f"{d.day} {d:%b}" + (f" {d.year}" if year else "")
