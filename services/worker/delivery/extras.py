"""Delivery extras: evidence files (BLD-131) and Friday check-in replies from the screen (BLD-132).

**Evidence.** The owner (or an admin) attaches files that back the numbers: before-and-after counts for a fix,
results at 30 and 90 days. Each file goes through the same pipeline as research files (attachments/service.py):
quarantine, virus scan, the personal-data patterns per location, and the deep checks when they are on. Nobody can
open a file until it is `clean` (non-negotiable 8); everyone who can see the delivery can open a clean file.
Uploads obey `attachments.upload`; opening obeys `attachments.open` (both checked by the web app's route map).

**Check-ins.** Every Friday the fix track's owner gets a check-in message (delivery/jobs.py). They can now reply
on the delivery page: on track, at risk or blocked, with an optional short note (checked text, stored encrypted).
One reply a week; a later reply in the same week replaces it. "Blocked" tells the sponsor and the delivery PM at
once, so someone can help. Every step is audited with IDs and codes only.
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from attachments import service as attachments
from comms.route import emit
from core.db import Conn
from delivery import service
from ones.service import roles
from ones.text import checked, seal, unseal

IST = ZoneInfo("Asia/Kolkata")
CHECKIN_STATUSES = ("on_track", "at_risk", "blocked")
CHECKIN_WORDS = {"on_track": "On track", "at_risk": "At risk", "blocked": "Blocked"}
STATE_WORDS = {
    "quarantine": "Being checked",
    "processing": "Being checked",
    "awaiting_check": "Waiting for a deeper check",
    "clean": "Checked",
    "rejected": "Not accepted",
}
REJECTION_WORDS = {
    "virus": "The virus check flagged it",
    "check_failed": "The checks could not finish; upload it again",
    "too_big": "Too long to check in full",
    "unreadable": "We could not read it",
}


# --- Evidence ---------------------------------------------------------------------------------------------------


def _may_add(conn: Conn, d: dict[str, Any], actor: str, have: set[str] | None = None) -> bool:
    have = have if have is not None else roles(conn, actor)
    return "admin" in have or actor == str(d.get("owner_user_id"))


def add_evidence(conn: Conn, actor: str, delivery_id: Any, name: str, data: bytes) -> dict[str, Any]:
    d = service._delivery(conn, delivery_id)
    if not _may_add(conn, d, actor):
        raise service.Refused(403, "owner_only")
    try:
        out = attachments.accept_evidence(conn, delivery_id=int(d["id"]), user_id=actor, name=name, data=data)
    except attachments.AttachmentRefused as exc:
        raise service.Refused(exc.status, exc.code) from None
    service._audit(conn, actor, "delivery.evidence_added", f"delivery:{d['id']}", {"attachment": out["id"]})
    return out


def evidence(conn: Conn, d: dict[str, Any], viewer_id: str, have: set[str]) -> list[dict[str, Any]]:
    """The delivery's files for its page. Names were checked at upload; rejection reasons are codes, never text."""
    rows = conn.execute(
        "SELECT id, name, bytes, state, rejection, uploaded_by_user, created_at FROM attachments "
        "WHERE delivery_id = %s ORDER BY created_at, id",
        (d["id"],),
    ).fetchall()
    admin = "admin" in have
    out = []
    for r in rows:
        rej = dict(r["rejection"] or {})
        code = str(rej.get("code") or rej.get("type") or "")
        out.append(
            {
                "id": r["id"], "name": r["name"], "bytes": int(r["bytes"]), "state": r["state"],
                "state_words": STATE_WORDS.get(r["state"], r["state"]),
                "rejection_words": (REJECTION_WORDS.get(code) or "It holds personal data; take it out and upload "
                                    "it again") if r["state"] == "rejected" else None,
                "can_open": r["state"] == "clean",
                "can_remove": d["state"] != "closed" and (admin or str(r["uploaded_by_user"]) == viewer_id),
                "added_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
        )  # fmt: skip
    return out


def _evidence_row(conn: Conn, d: dict[str, Any], att_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT id, state, uploaded_by_user FROM attachments WHERE id = %s AND delivery_id = %s",
        (att_id, d["id"]),
    ).fetchone()
    if row is None:
        raise service.Refused(404, "not_found")
    return dict(row)


def evidence_content(conn: Conn, viewer_id: str, delivery_id: Any, att_id: str) -> tuple[bytes, str, str]:
    """A clean evidence file's bytes, for someone who can see the delivery. Anything not clean is refused."""
    d = service._delivery(conn, delivery_id)
    if not service.can_see(conn, d, viewer_id):
        raise service.Refused(404, "not_found")
    _evidence_row(conn, d, att_id)
    try:
        data, mime, name = attachments.content(conn, att_id)
    except attachments.AttachmentRefused as exc:
        raise service.Refused(exc.status, exc.code) from None
    service._audit(conn, viewer_id, "delivery.evidence_opened", f"delivery:{d['id']}", {"attachment": att_id})
    return data, mime, name


def remove_evidence(conn: Conn, actor: str, delivery_id: Any, att_id: str) -> dict[str, Any]:
    d = service._delivery(conn, delivery_id)
    if d["state"] == "closed":
        raise service.Refused(409, "closed")
    row = _evidence_row(conn, d, att_id)
    if "admin" not in roles(conn, actor) and str(row["uploaded_by_user"]) != actor:
        raise service.Refused(403, "uploader_only")
    attachments.remove(conn, att_id)
    service._audit(conn, actor, "delivery.evidence_removed", f"delivery:{d['id']}", {"attachment": att_id})
    return {"removed": att_id}


# --- Friday check-ins -------------------------------------------------------------------------------------------


def week_of(now: dt.datetime) -> dt.date:
    """The Monday of the IST week that `now` falls in."""
    day = now.astimezone(IST).date()
    return day - dt.timedelta(days=day.weekday())


def _may_check_in(conn: Conn, d: dict[str, Any], actor: str, have: set[str] | None = None) -> bool:
    if d["track"] != "fix" or d["state"] != "in_delivery":
        return False
    have = have if have is not None else roles(conn, actor)
    return "admin" in have or actor == str(d.get("owner_user_id"))


def check_in(
    conn: Conn, actor: str, delivery_id: Any, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.UTC)
    status = body.get("status")
    if status not in CHECKIN_STATUSES:
        raise service.Refused(400, "status_required")
    note_raw = str(body.get("note") or "").strip()
    d = service._delivery(conn, delivery_id)
    if not _may_check_in(conn, d, actor):
        raise service.Refused(403, "owner_only")
    note = checked(conn, note_raw, min_chars=5, max_chars=400) if note_raw else None  # before the transaction
    week = week_of(now)
    with conn.transaction():
        d = service._delivery(conn, d["id"], lock=True)
        if not _may_check_in(conn, d, actor):
            raise service.Refused(409, "not_in_fix_track")
        row = conn.execute(
            "INSERT INTO delivery_checkins (delivery_id, week_of, status, by_user) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (delivery_id, week_of) DO UPDATE SET status = EXCLUDED.status, by_user = EXCLUDED.by_user "
            "RETURNING id, (xmax = 0) AS created",
            (d["id"], week, status, actor),
        ).fetchone()
        assert row is not None
        conn.execute(
            "UPDATE delivery_checkins SET note_encrypted = %s WHERE id = %s",
            (seal(note, f"checkin:{row['id']}") if note else None, row["id"]),
        )
        service._audit(
            conn, actor, "delivery.checkin", f"delivery:{d['id']}",
            {"status": status, "week_of": week.isoformat(), "note": bool(note), "replaced": not row["created"]},
        )  # fmt: skip
        if status == "blocked":
            helpers = sorted({str(u) for u in (d["sponsor_user_id"], d["pm_user_id"]) if u})
            if helpers:
                emit(
                    conn,
                    "delivery.checkin_blocked",
                    {"delivery_id": d["id"], "subject_id": d["subject_id"], "current_owner_ids": helpers},
                )
    return {"id": row["id"], "week_of": week.isoformat(), "status": status}


def checkins(
    conn: Conn, d: dict[str, Any], viewer_id: str, have: set[str], now: dt.datetime | None = None
) -> dict[str, Any]:
    """The last six weeks' replies, and whether this week's is still open for the owner."""
    now = now or dt.datetime.now(dt.UTC)
    rows = conn.execute(
        "SELECT id, week_of, status, note_encrypted FROM delivery_checkins WHERE delivery_id = %s "
        "ORDER BY week_of DESC LIMIT 6",
        (d["id"],),
    ).fetchall()
    this_week = week_of(now)
    replied = any(r["week_of"] == this_week for r in rows)
    return {
        "recent": [
            {
                "week_of": r["week_of"].isoformat(),
                "status": r["status"],
                "status_words": CHECKIN_WORDS[r["status"]],
                "note": unseal(r["note_encrypted"], f"checkin:{r['id']}"),
            }
            for r in rows
        ],
        "this_week": this_week.isoformat(),
        "replied_this_week": replied,
        "can_reply": _may_check_in(conn, d, viewer_id, have),
        "statuses": [{"id": s, "words": CHECKIN_WORDS[s]} for s in CHECKIN_STATUSES],
    }
