"""The other lanes' entry points, each behind one function, so a change to theirs touches only this file.

- `tell`: L-NOTIFY and L-INBOX (lane A, `notify.post`, BLD-A180). A no-op until `notify` is importable.
- `resolve`: L-INBOX.rules/3 (lane A, `notify.resolve`): a Needs you item, and every item keyed under it, leaves the
  list once its action is done. A no-op until `notify` has `resolve` (it lands with lane A's inbox).
- `say`: L-CONVO (lane F, `convo.post`): a line in the idea's conversation, IDs only. Writes `conversation_entries`
  directly until `convo` is importable.
- `hide`: L-HIDE (lane C): free text masked before it is stored or shown to anyone else. Until lane C's entry point
  lands it masks what the shared patterns find (kind + •••• + last two), so nothing a reviewer types reaches a
  sharer unmasked.
- `schedule`: lane A's timers. A no-op until lane A publishes its interface; every screen works it out on read.
"""

from __future__ import annotations

import datetime as dt
import importlib
from collections.abc import Mapping, Sequence
from typing import Any

from psycopg.types.json import Jsonb

from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from pii.patterns import scan

log = get_logger("desk")

Ref = str | int | bool | None


def tell(
    conn: Conn,
    kind: str,
    recipients: Sequence[str],
    *,
    idea_uuid: str | None = None,
    sender: str = "system",
    needs_you: bool = False,
    due_at: dt.datetime | None = None,
    actions: Sequence[tuple[str, str, str]] = (),  # (label, route, style)
    refs: Mapping[str, Ref] | None = None,
    dedupe_key: str | None = None,
) -> None:
    """Tell people something through lane A's inbox. IDs and enums only in `refs` (non-negotiable 3)."""
    try:
        notify = importlib.import_module("notify")
    except ModuleNotFoundError:
        log.info("desk.tell.pending", kind=kind, count=len(recipients))
        return
    notify.post(
        conn, kind, [r for r in recipients if r], idea_id=idea_uuid, sender=sender, needs_you=needs_you,
        due_at=due_at, actions=[notify.Action(label=a, to=t, style=s) for a, t, s in actions], refs=refs,
        dedupe_key=dedupe_key,
    )  # fmt: skip


def questions_key(set_id: str) -> str:
    """A question set's inbox key (L-INBOX.kinds "Questions from the review desk"); every reminder for the set is
    keyed under it (`qs:<set>:<threshold>`), so resolving it clears them all (L-INBOX.rules/3)."""
    return f"qs:{set_id}"


def resolve(conn: Conn, dedupe_key: str) -> int:
    """Clear the Needs you item posted under `dedupe_key`, and every key under it (`qs:<set>` also clears the
    reminders `qs:<set>:<threshold>`), in the caller's transaction. Safe to call twice. Returns how many items it
    cleared; 0 while lane A's `notify.resolve` is not there."""
    try:
        notify = importlib.import_module("notify")
    except ModuleNotFoundError:
        notify = None
    fn = getattr(notify, "resolve", None)
    if fn is None:
        log.info("desk.resolve.pending")  # the key holds a row id: not logged
        return 0
    return int(fn(conn, dedupe_key) or 0)


def say(
    conn: Conn,
    idea_uuid: str,
    event: str,
    *,
    author_user_id: str | None = None,
    author_code: str | None = None,
    payload: Mapping[str, Ref] | None = None,
    question_set_id: str | None = None,
    entry_type: str = "event",
    at: dt.datetime | None = None,
) -> None:
    """A line in the idea's conversation ('Meera from the review desk opened it'), rendered by lane F at read time.
    Lane F's `convo.post` takes these same arguments (SHIP_PLAN §5a); the direct insert is the fallback until it is
    importable. Like `convo.post` (BLD-F013), the direct insert places each line just after the idea's last one, so
    lines written in one transaction (one `now()`, random ids) read back in the order they were written (L-CONVO)."""
    try:
        convo = importlib.import_module("convo")
    except ModuleNotFoundError:
        convo = None
    if convo is not None:
        convo.post(
            conn, idea_uuid, event, author_user_id=author_user_id, author_code=author_code, payload=dict(payload or {}),
            question_set_id=question_set_id, entry_type=entry_type, at=at,
        )  # fmt: skip
        return
    conn.execute(
        "INSERT INTO conversation_entries (idea_uuid, type, event, payload, author_user_id, author_code, "
        "question_set_id, at) VALUES (%(idea)s, %(type)s, %(event)s, %(payload)s, %(user)s, %(code)s, %(set)s, "
        "greatest(coalesce(%(at)s, now()), (SELECT max(e.at) FROM conversation_entries e WHERE e.idea_uuid = "
        "%(idea)s) + interval '1 microsecond'))",
        {
            "idea": idea_uuid,
            "type": entry_type,
            "event": event,
            "payload": Jsonb(dict(payload or {})),
            "user": author_user_id,
            "code": author_code,
            "set": question_set_id,
            "at": at,
        },
    )


_KINDS = {"Mobile": "Phone", "Email": "Email", "Bank": "Account", "Date": "Date of birth"}


def _mask(value: str, label: str, before: str) -> str:
    """'Folio ••••89': the kind, unless the words just before already name it, then the last two characters."""
    first = label.split(" ")[0]
    kind = _KINDS.get(first, first)
    tail = "".join(ch for ch in value if ch.isalnum())[-2:]
    named = before[-16:].lower().rstrip(" :#-").endswith(kind.lower()) or before[-16:].lower().rstrip(
        " :#-"
    ).endswith(first.lower())
    return f"••••{tail}" if named else f"{kind} ••••{tail}"


def hide(conn: Conn, idea_uuid: str, text: str) -> tuple[str, int]:
    """The masked copy of `text` and how many details were hidden (L-HIDE; DEC-103)."""
    _ = (conn, idea_uuid)  # lane C's version keeps the values in the vault under the idea's scope
    matches = sorted(scan(text, kfin_domains=get_settings().kfin_domains), key=lambda m: m.start)
    out, last, n = [], 0, 0
    for m in matches:
        if m.start < last:
            continue
        out.append(text[last : m.start])
        out.append(_mask(text[m.start : m.end], m.label, text[: m.start]))
        last, n = m.end, n + 1
    out.append(text[last:])
    return "".join(out), n


def schedule(
    conn: Conn, kind: str, entity: str, due_at: dt.datetime, payload: Mapping[str, Any] | None = None
) -> None:
    """Ask lane A's timer engine to call a lane B handler at `due_at`. Screens never depend on it having run."""
    _ = (conn, payload)
    target, _, target_id = entity.partition(":")
    log.info(
        "desk.schedule.pending", kind=kind, target=target, target_id=target_id
    )  # a bare ID passes the value scan
