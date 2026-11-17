"""Other lanes' entry points, each behind one function, so a change to theirs touches only this file.

- `tell`: L-NOTIFY and L-INBOX (lane A, `notify.post`, BLD-A180), called inside the caller's transaction. `refs`
  carry IDs, enums, numbers and booleans only; lane A renders the inbox line from the kind at read time.
- `hide`: L-HIDE (lane C's `hide_message`, BLD-C060): patterns, then the gatekeeper when `ai.all` is on, then names
  next to another detail; each value is kept in lane C's vault for the writer's "Show it", and the writer's own words
  are sealed under the entry's id. It is called with `source="conversation"`, `source_id` = the entry's id and
  `by` = the author's users.id, inside the transaction that inserts the entry (L-CONVO/7, BLD-F054). Until lane C's
  package is importable here, a message is masked with the shared patterns only (kind + •••• + last two
  characters, DEC-103), the way lane B's desk adapter does. Either way only the masked copy is kept with the entry.
"""

from __future__ import annotations

import datetime as dt
import importlib
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from notify import Action
from notify import post as notify_post
from pii.patterns import scan


def _lane_c(module: str, name: str) -> Any:
    """One of lane C's L-HIDE names when its package is here (on main since 18 Nov), else None. A guarded import,
    through importlib so the type check passes the same with or without lane C."""
    try:
        return getattr(importlib.import_module(module), name)
    except (ImportError, AttributeError):
        return None


_hide_message: Callable[..., Any] | None = _lane_c("hide", "hide_message")
_hide_lock: Callable[[Conn, str], None] | None = _lane_c("hide.core", "lock")
_hide_scope: Callable[[str], str] | None = _lane_c("hide.core", "scope_for")
_HideError: type[Exception] | None = _lane_c("hide.core", "HideError")


class HideRefused(Exception):
    """Lane C refused to hide a text (its `HideError`), carrying its HTTP status only."""

    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status


log = get_logger("convo")

Ref = str | int | bool | None  # lane A's notify refs


def tell(
    conn: Conn,
    kind: str,
    recipients: Sequence[str],
    *,
    idea_uuid: str,
    sender: str,
    actions: Sequence[tuple[str, str, str]] = (),  # (label, route, style)
    refs: Mapping[str, Ref] | None = None,
    dedupe_key: str | None = None,
    due_at: dt.datetime | None = None,
) -> None:
    """Tell people something through lane A's inbox (in-app at once; email and Teams by their preferences)."""
    people = sorted({r for r in recipients if r and r != sender})
    if not people:
        return
    notify_post(
        conn, kind, people, idea_id=idea_uuid, sender=sender, due_at=due_at,  # type: ignore[arg-type]
        actions=[Action(label=a, to=t, style=s) for a, t, s in actions],  # type: ignore[arg-type]
        refs=refs, dedupe_key=dedupe_key,
    )  # fmt: skip


_KINDS = {"Mobile": "Phone", "Email": "Email", "Bank": "Account", "Date": "Date of birth"}


def _mask(value: str, label: str, before: str) -> str:
    """'Folio ••••89': the kind, unless the words just before already name it, then the last two characters."""
    first = label.split(" ")[0]
    kind = _KINDS.get(first, first)
    tail = "".join(ch for ch in value if ch.isalnum())[-2:]
    lead = before[-16:].lower().rstrip(" :#-")
    named = lead.endswith(kind.lower()) or lead.endswith(first.lower())
    return f"••••{tail}" if named else f"{kind} ••••{tail}"


def hide(conn: Conn, idea_uuid: str, text: str, *, by: str, entry_id: str) -> tuple[str, int]:
    """The masked copy of `text` and how many details were hidden (L-HIDE; DEC-103). Call it inside the
    transaction that inserts the entry `entry_id`, written by the user `by` (lane C's contract, BLD-F054)."""
    if _hide_message is not None:
        try:
            done = _hide_message(
                conn, idea_uuid, text, by=by, source="conversation", source_id=entry_id, gatekeeper=True
            )
        except Exception as exc:
            if _HideError is not None and isinstance(exc, _HideError):
                raise HideRefused(int(getattr(exc, "status", 503))) from None
            raise
        return done.masked, int(done.hidden_count)
    return pattern_mask(text)


def forget(conn: Conn, idea_uuid: str, entry_id: str) -> None:
    """Drop what L-HIDE kept for a removed message (L-CONVO/10, BLD-F067): its hidden details, the writer's sealed
    words, and each vault value no other text on the idea still uses. Lane C's recipe of 18 Nov, step for step, until
    its `hide.forget` lands (c/hide-3); then this body becomes that one call.

    Call it inside the removal's transaction, before any row lock: lane C's lock comes first, as every L-HIDE write
    takes it. IDs and counts only in the log."""
    if _hide_lock is None or _hide_scope is None:
        return  # lane C's package is not here, so nothing was kept
    _hide_lock(conn, idea_uuid)
    key = (idea_uuid, entry_id)
    tags = [
        str(r["vault_tag"])
        for r in conn.execute(
            "SELECT vault_tag FROM hidden_details WHERE idea_uuid = %s AND source = 'conversation' "
            "AND source_id = %s AND vault_tag IS NOT NULL",
            key,
        ).fetchall()
    ]
    details = conn.execute(
        "DELETE FROM hidden_details WHERE idea_uuid = %s AND source = 'conversation' AND source_id = %s", key
    ).rowcount
    words = conn.execute(
        "DELETE FROM idea_words_sealed WHERE idea_uuid = %s AND source = 'conversation' AND source_id = %s",
        key,
    ).rowcount
    values = 0
    if tags:
        values = conn.execute(
            "DELETE FROM pseudonym_vault v WHERE v.scope_id = %s AND v.tag = ANY(%s::text[]) AND NOT EXISTS "
            "(SELECT 1 FROM hidden_details h WHERE h.idea_uuid = %s AND h.vault_tag = v.tag)",
            (_hide_scope(idea_uuid), tags, idea_uuid),
        ).rowcount
    log.info(
        "convo.hidden_forgotten",
        entry_id=entry_id,
        hidden_count=details,
        sealed_count=words,
        vault_rows=values,
    )


def pattern_mask(text: str) -> tuple[str, int]:
    """The shared patterns only: the fallback until lane C's L-HIDE is importable, and the idempotency check's
    stable form of the words (a model's finds may differ between two tries of one request)."""
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
