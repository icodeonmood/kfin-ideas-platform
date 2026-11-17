"""Other lanes' entry points, each behind one function, so a change to theirs touches only this file.

- `tell`: L-NOTIFY and L-INBOX (lane A, `notify.post`, BLD-A180), called inside the caller's transaction. `refs`
  carry IDs, enums, numbers and booleans only; lane A renders the inbox line from the kind at read time.
- `hide`: L-HIDE (lane C). Until lane C's `hide_text` is on main, a message is masked with the shared patterns
  (kind + •••• + last two characters, DEC-103), the way lane B's desk adapter does, before it is sealed or anyone
  else sees it (L-CONVO/7). Only the masked copy is kept (BLD-F054).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence

from core.config import get_settings
from core.db import Conn
from notify import Action
from notify import post as notify_post
from pii.patterns import scan

Ref = str | int | bool | None


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
