"""L-NOTIFY and L-INBOX: the one entry point other lanes call to tell people something (BLD-A180).

`post` writes one inbox item per recipient (in-app, at once) and queues the other channels the person's
preferences allow: email now, Teams once IT approves it (DEC-105, off). It is called inside the caller's
transaction, so the item exists exactly when the change that caused it does.

What goes in: IDs and enums only (non-negotiable 3). The line a person reads is rendered from the HR-signed
templates by kind when the inbox is read, never stored. A decision's reason is read in the app only: email and
Teams say a decision arrived, with a link (BLD-E004).

Until lane E's cut-over adds the inbox columns to `notifications` (kind, from, idea_id, needs_you, due_at,
archived_at, actions; 20261121500100), this is a stub: it validates its arguments and returns no IDs. The
signature is the contract and does not change when the body lands.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from core.db import Conn

InboxKind = Literal[
    "questions",
    "teamup_request",
    "teamup_answer",
    "decision",
    "decision_reversed",
    "desk_merge",
    "worth_revised",
    "stage_moved",
    "build_ask",
    "mention",
    "crew_joined",
    "comment",
    "draft_kept",
    "sent_to_desk",
    "answer_reminder",
]  # E-ENUMS.inbox
INBOX_KINDS: frozenset[str] = frozenset(InboxKind.__args__)  # type: ignore[attr-defined]

Ref = str | int | bool | None


@dataclass(frozen=True)
class Action:
    """E-ENTITIES `Action`: a button on the inbox item. `to` is an app route, `op` a server operation name."""

    label: str
    style: Literal["primary", "line", "text"] = "line"
    to: str | None = None
    op: str | None = None


@dataclass(frozen=True)
class Posted:
    """What `post` did: the inbox item IDs, one per recipient who got one (none while this is a stub)."""

    ids: list[int] = field(default_factory=list)


class NotifyError(ValueError):
    pass


def post(
    conn: Conn,
    kind: InboxKind,
    recipients: Sequence[str],
    *,
    idea_id: str | None = None,
    sender: str | Literal["system"] = "system",
    needs_you: bool = False,
    due_at: dt.datetime | None = None,
    actions: Sequence[Action] = (),
    refs: Mapping[str, Ref] | None = None,
    dedupe_key: str | None = None,
) -> Posted:
    """Tell `recipients` (users.id values) about something.

    - `kind`: one of E-ENUMS.inbox. Lane F's team-up and merge kinds are added here when lane F names them.
    - `idea_id`: the idea's row id (`ideas.id`, a UUID), so drafts work too; None for items about no idea.
    - `sender`: a users.id, or "system".
    - `needs_you`, `due_at`: show the item under "Needs you", with its due date (L-INBOX).
    - `actions`: the buttons on the item.
    - `refs`: the kind's body as IDs, enums, numbers and booleans only; the template turns them into words.
    - `dedupe_key`: posting the same key to the same person twice keeps one item (reminders, retries).

    The sender is never also a recipient; a recipient listed twice gets one item.
    """
    if kind not in INBOX_KINDS:
        raise NotifyError(f"unknown inbox kind {kind!r}")
    if any(not isinstance(r, str) or not r for r in recipients):
        raise NotifyError("recipients are users.id values")
    for key, value in (refs or {}).items():
        if not isinstance(value, str | int | bool) and value is not None:
            raise NotifyError(f"ref {key!r} must be an ID, enum, number or boolean")
    for a in actions:
        if a.to is None and a.op is None:
            raise NotifyError("an action needs a route (to) or an operation (op)")
    _ = (conn, idea_id, sender, needs_you, due_at, dedupe_key)  # used once the inbox columns land
    return Posted()
