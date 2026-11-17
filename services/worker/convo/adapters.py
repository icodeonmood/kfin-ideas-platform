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
from notify import Action
from notify import post as notify_post
from pii.patterns import scan


def _lane_c_hide() -> Callable[..., Any] | None:
    """Lane C's `hide.hide_message` when its package is here (on main from Wed 18 Nov), else None. A guarded import,
    through importlib so the type check passes the same before and after lane C lands."""
    try:
        return importlib.import_module("hide").hide_message  # type: ignore[no-any-return]
    except (ImportError, AttributeError):
        return None


_hide_message = _lane_c_hide()

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
        done = _hide_message(conn, idea_uuid, text, by=by, source="conversation", source_id=entry_id)
        return done.masked, done.hidden_count
    return pattern_mask(text)


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
