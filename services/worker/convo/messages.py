"""Writing in an idea's conversation: `POST /ideas/:id/conversation/messages` and removing one's own message
(L-CONVO/5–7, /9, /10; A-API.inbox).

A message is masked before anyone else can see it (L-CONVO/7, through `adapters.hide`), then sealed; it is never
edited. Files are attached by ID only, and only once their checks have passed: this module never opens a file
(non-negotiable 8). A mention tells the person (`mention`), and gives a person who is not already in the
conversation that one message to read (L-CONVO/6, BLD-F052). The sharer hears of anyone else's message (`comment`),
once per hour of messages (BLD-F056). Logs and audit rows carry IDs only.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import uuid
from typing import Any

from psycopg.types.json import Jsonb

from convo import adapters
from convo.access import may_read_full, reader
from convo.reads import CLEAN_FILE_STATES, REMOVE_WITHIN, _mine, closed_message, entry_for
from convo.render import IST
from convo.store import Refused, audit, load_idea, not_found, now, seal, user_of
from core.db import Conn
from core.logging import get_logger

log = get_logger("convo")

MAX_CHARS = 4000  # BLD-F055
MAX_FILES = 5
MAX_MENTIONS = 10
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_ATT = re.compile(r"^ATT-[0-9]{4}-[0-9]{6}$")
_ROUTE = "POST /ideas/:id/conversation/messages"

EMPTY = "Write a message or attach a file first."  # L-CONVO/5 (Messages.md)
TOO_LONG = "Keep a message under 4,000 characters."
FILE_UNAVAILABLE = "This file can’t be added here. Add it again from this conversation."
FILE_NOT_CHECKED = "This file is still being checked. Send it once it shows as checked."
FILE_HAS_DETAIL = "This file has a customer detail in it. Hide the detail or remove the file first."
NOT_YOURS = "You can remove only your own messages."
TOO_LATE = "A message can be removed only in the first 5 minutes after sending."
KEY_REUSED = "This request was already sent with different words. Refresh and try again."


def _ids(value: Any, pattern: re.Pattern[str], limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for v in value:
        if isinstance(v, str) and pattern.match(v) and v not in out:
            out.append(v)
    return out[:limit]


def send(
    conn: Conn,
    ref: str,
    user_id: str,
    body: dict[str, Any],
    *,
    idempotency_key: str | None = None,
    at: dt.datetime | None = None,
) -> dict[str, Any]:
    """Write a message. Returns `{entry, hidden}`: the message as the sender sees it and how many details were
    hidden from it."""
    raw = body.get("text")
    text = raw.strip() if isinstance(raw, str) else ""
    file_ids = _ids(body.get("file_ids"), _ATT, MAX_FILES)
    mention_ids = [u for u in _ids(body.get("mentions"), _UUID, MAX_MENTIONS) if u != user_id]
    t = at or now()
    with conn.transaction():
        idea = load_idea(conn, ref)
        r = reader(conn, idea, user_id)
        if idea["status"] == "merged":
            raise Refused(409, "conversation_closed", closed_message(conn, idea))
        if not text and not file_ids:
            raise Refused(422, "empty_message", EMPTY, "text")
        if len(text) > MAX_CHARS:
            raise Refused(422, "too_long", TOO_LONG, "text")
        masked, hidden = adapters.hide(conn, str(idea["id"]), text) if text else ("", 0)
        if idempotency_key:
            first = _idempotent(conn, user_id, idempotency_key, masked, file_ids, mention_ids)
            if first is not None:
                return {"entry": entry_for(conn, idea, user_id, first, t), "hidden": 0}
        _check_files(conn, idea, r.code, file_ids)
        mentioned = _people(conn, mention_ids)

        entry_id = str(uuid.uuid4())
        as_code = r.code if (r.sharer or r.crew) else None
        conn.execute(
            "INSERT INTO conversation_entries (id, idea_uuid, type, author_code, author_user_id, text_encrypted, "
            "mentions, at) VALUES (%s, %s, 'message', %s, %s, %s, %s::uuid[], %s)",
            (entry_id, idea["id"], as_code, None if as_code else user_id, seal(masked, entry_id) if masked else None,
             mentioned, t),
        )  # fmt: skip
        if file_ids:
            conn.execute(
                "UPDATE attachments SET conversation_entry_id = %s WHERE id = ANY(%s)", (entry_id, file_ids)
            )
        _notify(conn, idea, user_id, entry_id, mentioned, t)
        if idempotency_key:
            conn.execute(
                "UPDATE idempotency_keys SET status = 201, response_json = %s WHERE user_id = %s AND key = %s",
                (Jsonb({"entry_id": entry_id}), user_id, idempotency_key),
            )
        log.info("convo.message.sent", idea_id=idea["idea_id"], entry_id=entry_id, files=len(file_ids),
                 mentions=len(mentioned), hidden=hidden)  # fmt: skip
        return {"entry": entry_for(conn, idea, user_id, entry_id, t), "hidden": hidden}


def _idempotent(
    conn: Conn, user_id: str, key: str, masked: str, file_ids: list[str], mention_ids: list[str]
) -> str | None:
    """A-API.conventions/3: the first result for a repeated key (the entry id), or None to go ahead. The hash is of
    the masked words and the IDs, never the typed words."""
    if not 8 <= len(key) <= 200:
        raise Refused(422, "idempotency_key_invalid", "", "Idempotency-Key")
    digest = hashlib.sha256(
        "\x1f".join([masked, ",".join(file_ids), ",".join(sorted(mention_ids))]).encode()
    ).hexdigest()
    made = conn.execute(
        "INSERT INTO idempotency_keys (key, user_id, route, request_hash) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (user_id, key) DO NOTHING RETURNING key",
        (key, user_id, _ROUTE, digest),
    ).fetchone()
    if made is not None:
        return None
    row = conn.execute(
        "SELECT route, request_hash, response_json FROM idempotency_keys WHERE user_id = %s AND key = %s",
        (user_id, key),
    ).fetchone()
    if row is None or row["route"] != _ROUTE or row["request_hash"] != digest:
        raise Refused(409, "idempotency_key_reused", KEY_REUSED)
    first = (row["response_json"] or {}).get("entry_id")
    if not first:
        raise Refused(409, "in_progress", "")
    return str(first)


def _check_files(conn: Conn, idea: dict[str, Any], code: str | None, file_ids: list[str]) -> None:
    """Each file: this idea's, uploaded by the sender, not on another message, and checked clean (L-CONVO/7;
    DEC-107 keeps a file with a customer detail off the crew's screens, so it is not sent here)."""
    if not file_ids:
        return
    rows = {
        str(f["id"]): dict(f)
        for f in conn.execute(
            "SELECT id, kind, state, file_state, uploaded_by_code, conversation_entry_id FROM attachments "
            "WHERE id = ANY(%s) AND idea_uuid = %s FOR UPDATE",
            (file_ids, idea["id"]),
        ).fetchall()
    }
    for fid in file_ids:
        f = rows.get(fid)
        if (
            f is None
            or code is None
            or f["uploaded_by_code"] != code
            or f["kind"] != "file"
            or f["conversation_entry_id"]
        ):
            raise Refused(422, "file_unavailable", FILE_UNAVAILABLE, "file_ids")
        clean = f["file_state"] in CLEAN_FILE_STATES or (f["file_state"] is None and f["state"] == "clean")
        if not clean:
            if f["file_state"] == "personal_data_found":
                raise Refused(422, "file_has_detail", FILE_HAS_DETAIL, "file_ids")
            raise Refused(422, "file_not_checked", FILE_NOT_CHECKED, "file_ids")


def _people(conn: Conn, ids: list[str]) -> list[str]:
    if not ids:
        return []
    found = {
        str(u["id"])
        for u in conn.execute("SELECT id FROM users WHERE id = ANY(%s::uuid[]) AND active", (ids,)).fetchall()
    }
    return [u for u in ids if u in found]


def _notify(
    conn: Conn, idea: dict[str, Any], sender: str, entry_id: str, mentioned: list[str], t: dt.datetime
) -> None:
    """`mention` to each person mentioned (L-INBOX: opens the conversation at the message), and `comment` to the
    sharer when someone else writes, one item per hour of messages."""
    ref, idea_uuid = str(idea["idea_id"]), str(idea["id"])
    at_message = (("Open the conversation", f"/ideas/{ref}/conversation#entry-{entry_id}", "primary"),)
    for u in mentioned:
        outside = not may_read_full(conn, idea, u)
        if outside:  # L-CONVO/6: this message only; the grant is the mention itself (BLD-F052)
            audit(conn, sender, "convo.mention_access", f"idea:{ref}", {"entry_id": entry_id, "user_id": u})
        adapters.tell(conn, "mention", [u], idea_uuid=idea_uuid, sender=sender, actions=at_message,
                      refs={"entry_id": entry_id, "outside": outside}, dedupe_key=f"convo.mention:{entry_id}")  # fmt: skip
    sharer = user_of(conn, idea["contributor_code"])
    if sharer and sharer != sender and sharer not in mentioned:
        hour = t.astimezone(IST).strftime("%Y%m%d%H")
        adapters.tell(conn, "comment", [sharer], idea_uuid=idea_uuid, sender=sender,
                      actions=(("Open the conversation", f"/ideas/{ref}/conversation", "primary"),),
                      refs={"entry_id": entry_id}, dedupe_key=f"convo.comment:{idea_uuid}:{hour}")  # fmt: skip


def remove(
    conn: Conn, ref: str, user_id: str, entry_id: str, *, at: dt.datetime | None = None
) -> dict[str, Any]:
    """`DELETE /ideas/:id/conversation/messages/:entryId`: the sender's own message, within 5 minutes; it then reads
    "Message removed" for everyone (L-CONVO/10). The words are dropped, not kept, and its files come off it."""
    t = at or now()
    if not _UUID.match(entry_id):
        raise not_found()
    with conn.transaction():
        idea = load_idea(conn, ref)
        r = reader(conn, idea, user_id)
        row = conn.execute(
            "SELECT * FROM conversation_entries WHERE id = %s AND idea_uuid = %s AND type = 'message' FOR UPDATE",
            (entry_id, idea["id"]),
        ).fetchone()
        if row is None:
            raise not_found()
        mine = _mine(dict(row), r)
        if not mine:
            visible = r.full or user_id in [str(u) for u in (row["mentions"] or [])]
            raise Refused(403, "not_yours", NOT_YOURS) if visible else not_found()
        if row["deleted_at"] is None:
            if t > row["at"] + REMOVE_WITHIN:
                raise Refused(409, "too_late", TOO_LATE)
            conn.execute(
                "UPDATE conversation_entries SET deleted_at = %s, text_encrypted = NULL WHERE id = %s",
                (t, entry_id),
            )
            conn.execute(
                "UPDATE attachments SET conversation_entry_id = NULL WHERE conversation_entry_id = %s",
                (entry_id,),
            )
            audit(conn, user_id, "convo.message_removed", f"idea:{idea['idea_id']}", {"entry_id": entry_id})
        return {"entry": entry_for(conn, idea, user_id, entry_id, t)}
