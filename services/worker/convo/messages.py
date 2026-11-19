"""Writing in an idea's conversation: `POST /ideas/:id/conversation/messages` and removing one's own message
(L-CONVO/5–7, /9, /10; A-API.inbox).

A message is masked before anyone else can see it (L-CONVO/7, through `adapters.hide`: lane C's L-HIDE), then sealed;
it is never edited. Files are attached by ID only, and only once their checks have passed: this module never opens a file
(non-negotiable 8). A mention tells the person (`mention`), and gives a person who is not already in the
conversation that one message to read (L-CONVO/6, BLD-F052). The sharer hears of anyone else's message (`comment`),
once per hour of messages (BLD-F056). When the writer speaks as the review desk (`reads.speaks_as`), both items
carry `as_desk: true` for anyone outside the review desk and the Ones Committee, so lane A's Inbox and email name the
desk, never the person, and store no sender (DEC-111, BLD-F084); when the writer speaks as the Ones Committee, they
carry `as_committee: true` the same way (DEC-113, BLD-F091). Logs and audit rows carry IDs only.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import uuid
from typing import Any

from psycopg.types.json import Jsonb

from convo import LOCK, adapters
from convo.access import may_read_full, reader, sees_desk_names
from convo.reads import CLEAN_FILE_STATES, REMOVE_WITHIN, _mine, closed_message, entry_for, speaks_as
from convo.render import COMMITTEE, DESK, IST
from convo.store import Refused, audit, load_idea, not_found, now, seal, user_of
from core.db import Conn
from core.logging import get_logger

log = get_logger("convo")

MAX_CHARS = 4000  # BLD-F055
MAX_FILES = 5
MAX_MENTIONS = 10
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_ATT = re.compile(r"^ATT-[0-9]{4}-[0-9]{6}$")
_ROUTE = "POST /ideas/{}/conversation/messages"  # with the idea's reference: a key is for one idea (A-API.conventions/3)
# As `convo.post` (BLD-F057): placed one microsecond after the idea's last line when its time would not be later.
_INSERT = (
    "INSERT INTO conversation_entries (id, idea_uuid, type, author_code, author_user_id, text_encrypted, mentions, at) "
    "VALUES (%(id)s, %(idea)s, 'message', %(code)s, %(user)s, %(text)s, %(mentions)s::uuid[], "
    "greatest(%(at)s, (SELECT max(e.at) FROM conversation_entries e WHERE e.idea_uuid = %(idea)s) "
    "+ interval '1 microsecond')) RETURNING at"
)

EMPTY = "Write a message or attach a file first."  # L-CONVO/5 (Messages.md)
TOO_LONG = "Keep a message under 4,000 characters."
FILE_UNAVAILABLE = "This file can’t be added here. Add it again from this conversation."
FILE_NOT_CHECKED = "This file is still being checked. Send it once it shows as checked."
FILE_HAS_DETAIL = "This file has a customer detail in it. Hide the detail or remove the file first."
NOT_YOURS = "You can remove only your own messages."
TOO_LATE = "A message can be removed only in the first 5 minutes after sending."
KEY_REUSED = "This request was already sent with different words. Refresh and try again."
TOO_MANY_FILES = "Attach up to 5 files to a message."  # BLD-F055: refused, never dropped
TOO_MANY_MENTIONS = "Mention up to 10 people in a message."
# BLD-F063: said only to readers who cannot add files, so it names who can without claiming a full list.
FILES_NOT_YOURS_TO_ADD = (
    "You can’t add files here. The person who shared this idea or the review desk can add them."
)
HIDE_FAILED = "We couldn’t check this message for customers’ details just now. Try again in a minute."


def _ids(value: Any, pattern: re.Pattern[str]) -> list[str]:
    """Each well-formed ID once, in the order given. The limits are checked after access, so a stranger still
    gets 404."""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for v in value:
        if isinstance(v, str) and pattern.match(v) and v not in out:
            out.append(v)
    return out


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
    file_ids = _ids(body.get("file_ids"), _ATT)
    mention_ids = [u for u in _ids(body.get("mentions"), _UUID) if u != user_id]
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
        if len(file_ids) > MAX_FILES:
            raise Refused(422, "too_many_files", TOO_MANY_FILES, "file_ids")
        if len(mention_ids) > MAX_MENTIONS:
            raise Refused(422, "too_many_mentions", TOO_MANY_MENTIONS, "mentions")
        if file_ids and not r.may_attach:
            raise Refused(422, "files_not_allowed", FILES_NOT_YOURS_TO_ADD, "file_ids")
        if idempotency_key:
            first = _idempotent(conn, idea, user_id, idempotency_key, text, file_ids, mention_ids)
            if first is not None:
                return {"entry": entry_for(conn, idea, user_id, first, t), "hidden": 0}
        _check_files(conn, idea, r.code, file_ids)
        mentioned = _people(conn, mention_ids)

        # The entry's id comes first: lane C's L-HIDE keeps the writer's own words and each hidden value under it
        # (source "conversation"), in this transaction (BLD-F054).
        entry_id = str(uuid.uuid4())
        try:
            masked, hidden = (
                adapters.hide(conn, str(idea["id"]), text, by=user_id, entry_id=entry_id) if text else ("", 0)
            )
        except adapters.HideRefused as exc:  # lane C's HideError: a ready message, never a 500 (BLD-F054)
            status = 503 if exc.status >= 500 else 422
            raise Refused(status, "hide_unavailable", HIDE_FAILED, "text") from None
        # After hiding, as lane B's desk takes them (L-HIDE's lock, then this one), so the two locks always come in
        # one order; before the last line's time is read, so two writers cannot tie (BLD-F057).
        conn.execute(LOCK, (str(idea["id"]),))
        as_code = r.code if (r.sharer or r.crew) else None
        placed = conn.execute(
            _INSERT,
            {"id": entry_id, "idea": idea["id"], "code": as_code, "user": None if as_code else user_id,
             "text": seal(masked, entry_id) if masked else None, "mentions": mentioned, "at": t},
        ).fetchone()  # fmt: skip
        assert placed is not None
        t = placed["at"]  # after the idea's last line when the clock would tie with it (BLD-F057)
        if file_ids:
            conn.execute(
                "UPDATE attachments SET conversation_entry_id = %s WHERE id = ANY(%s)", (entry_id, file_ids)
            )
        role = speaks_as(conn, idea, r)
        _notify(
            conn, idea, user_id, entry_id, mentioned, t, as_desk=role == DESK, as_committee=role == COMMITTEE
        )
        if idempotency_key:
            conn.execute(
                "UPDATE idempotency_keys SET status = 201, response_json = %s WHERE user_id = %s AND key = %s",
                (Jsonb({"entry_id": entry_id}), user_id, idempotency_key),
            )
        log.info("convo.message.sent", idea_id=idea["idea_id"], entry_id=entry_id, files=len(file_ids),
                 mentions=len(mentioned), hidden=hidden)  # fmt: skip
        return {"entry": entry_for(conn, idea, user_id, entry_id, t), "hidden": hidden}


def _idempotent(
    conn: Conn,
    idea: dict[str, Any],
    user_id: str,
    key: str,
    text: str,
    file_ids: list[str],
    mention_ids: list[str],
) -> str | None:
    """A-API.conventions/3: the first result for a repeated key (the entry id), or None to go ahead. The route and
    the hash carry the idea, so one key on two ideas is refused rather than read as a repeat. The hash is of the
    words masked by the shared patterns (stable between two tries, unlike a model's finds) and the IDs, never the
    typed words."""
    if not 8 <= len(key) <= 200:
        raise Refused(422, "idempotency_key_invalid", "", "Idempotency-Key")
    masked = adapters.pattern_mask(text)[0] if text else ""
    route = _ROUTE.format(idea["idea_id"])
    digest = hashlib.sha256(
        "\x1f".join([str(idea["id"]), masked, ",".join(file_ids), ",".join(sorted(mention_ids))]).encode()
    ).hexdigest()
    made = conn.execute(
        "INSERT INTO idempotency_keys (key, user_id, route, request_hash) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (user_id, key) DO NOTHING RETURNING key",
        (key, user_id, route, digest),
    ).fetchone()
    if made is not None:
        return None
    row = conn.execute(
        "SELECT route, request_hash, response_json FROM idempotency_keys WHERE user_id = %s AND key = %s",
        (user_id, key),
    ).fetchone()
    if row is None or row["route"] != route or row["request_hash"] != digest:
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
    conn: Conn,
    idea: dict[str, Any],
    sender: str,
    entry_id: str,
    mentioned: list[str],
    t: dt.datetime,
    *,
    as_desk: bool = False,
    as_committee: bool = False,
) -> None:
    """`mention` to each person mentioned (L-INBOX: opens the conversation at the message), and `comment` to the
    sharer when someone else writes, one item per hour of messages.

    DEC-111 (BLD-F084): when the writer speaks as the review desk, the item says so (`as_desk: true`, lane A's key)
    for each recipient outside the review desk and the Ones Committee, who read the desk in the conversation too; lane
    A then stores no sender and names the desk. The desk's comments keep their own hourly item (the key ends ":desk"),
    so a burst from the desk and the crew in one hour never puts one sender's name on the other's item. DEC-113
    (BLD-F091): the same for the Ones Committee, with `as_committee: true` and a key ending ":committee". `sender`
    stays the writer's users.id: `tell` uses it to leave the writer out."""
    ref, idea_uuid = str(idea["idea_id"]), str(idea["id"])
    at_message = (("Open the conversation", f"/ideas/{ref}/conversation#entry-{entry_id}", "primary"),)
    speaks = "as_desk" if as_desk else "as_committee" if as_committee else None

    def refs_for(u: str) -> dict[str, str | bool]:
        if speaks and not sees_desk_names(conn, u):
            return {"entry_id": entry_id, speaks: True}
        return {"entry_id": entry_id}

    for u in mentioned:
        outside = not may_read_full(conn, idea, u)
        if outside:  # L-CONVO/6: this message only; the grant is the mention itself (BLD-F052)
            audit(conn, sender, "convo.mention_access", f"idea:{ref}", {"entry_id": entry_id, "user_id": u})
        adapters.tell(conn, "mention", [u], idea_uuid=idea_uuid, sender=sender, actions=at_message,
                      refs=refs_for(u), dedupe_key=f"convo.mention:{entry_id}")  # fmt: skip
    sharer = user_of(conn, idea["contributor_code"])
    if sharer and sharer != sender and sharer not in mentioned:
        hour = t.astimezone(IST).strftime("%Y%m%d%H")
        refs = refs_for(sharer)
        key = f"convo.comment:{idea_uuid}:{hour}"
        if speaks and speaks in refs:  # ":desk" or ":committee"
            key += ":" + speaks.removeprefix("as_")
        adapters.tell(conn, "comment", [sharer], idea_uuid=idea_uuid, sender=sender,
                      actions=(("Open the conversation", f"/ideas/{ref}/conversation", "primary"),),
                      refs=refs, dedupe_key=key)  # fmt: skip


def remove(
    conn: Conn, ref: str, user_id: str, entry_id: str, *, at: dt.datetime | None = None
) -> dict[str, Any]:
    """`DELETE /ideas/:id/conversation/messages/:entryId`: the sender's own message, within 5 minutes; it then reads
    "Message removed" for everyone (L-CONVO/10). The words are dropped, not kept: the sealed masked copy, and what
    L-HIDE kept for the writer (BLD-F067). Its files come off it."""
    t = at or now()
    if not _UUID.match(entry_id):
        raise not_found()
    with conn.transaction():
        idea = load_idea(conn, ref)
        r = reader(conn, idea, user_id)
        # No row lock yet: L-HIDE's lock must come before any (lane C's recipe), and the UPDATE below guards the race.
        row = conn.execute(
            "SELECT * FROM conversation_entries WHERE id = %s AND idea_uuid = %s AND type = 'message'",
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
            adapters.forget(conn, str(idea["id"]), entry_id)  # L-HIDE's lock first, then what it kept
            done = conn.execute(
                "UPDATE conversation_entries SET deleted_at = %s, text_encrypted = NULL "
                "WHERE id = %s AND deleted_at IS NULL",
                (t, entry_id),
            ).rowcount
            if done:
                conn.execute(
                    "UPDATE attachments SET conversation_entry_id = NULL WHERE conversation_entry_id = %s",
                    (entry_id,),
                )
                audit(
                    conn, user_id, "convo.message_removed", f"idea:{idea['idea_id']}", {"entry_id": entry_id}
                )
        return {"entry": entry_for(conn, idea, user_id, entry_id, t)}
