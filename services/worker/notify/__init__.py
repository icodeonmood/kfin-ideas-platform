"""L-NOTIFY and L-INBOX: the one entry point other lanes call to tell people something (BLD-A180, BLD-A200).

`post` writes one inbox item per recipient (in-app, at once) and queues the other channels the person's
preferences allow: email now, Teams once IT approves it (DEC-105, the `comms.teams` switch, off). It is called
inside the caller's transaction, so the item exists exactly when the change that caused it does. Delivery happens
later, in `comms.send.send_due`, with its own retries: a failing mail server never blocks the caller (L-NOTIFY/6).

What goes in: IDs and enums only (non-negotiable 3). The line a person reads is rendered from the HR-signed
templates (`comms/templates/inbox/<kind>.md`) by kind when the inbox is read or the email is sent, never stored.
No message carries hidden details, the person's raw words or a decision's reason (L-NOTIFY/3, BLD-E004): the
reason and a request's note are read in the app, by the IDs in `refs`.

`resolve` takes an item off "Needs you" when its action is done anywhere (L-INBOX.rules/3): answers sent, a
team-up request answered, withdrawn or closed.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Literal

from psycopg.types.json import Jsonb

from core import killswitch
from core.db import Conn
from core.logging import get_logger

log = get_logger("notify")

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
    "detail_hidden_by_desk",
]  # E-ENUMS.inbox, plus L-HIDE/7's kind agreed with lane C (BLD-A205)
INBOX_KINDS: frozenset[str] = frozenset(InboxKind.__args__)  # type: ignore[attr-defined]

# L-NOTIFY/4: always sent on at least one outside channel, even with both turned off; email is the fallback.
ALWAYS_OUTSIDE: frozenset[str] = frozenset({"decision", "decision_reversed", "desk_merge"})
# L-NOTIFY/2: "Reminders before a question is due" is its own setting.
REMINDER_KINDS: frozenset[str] = frozenset({"answer_reminder"})
# Kinds that carry no refs at all: the item says only that something happened (L-HIDE/7, /8: a hidden detail is never
# in a notification, not even as an ID that points at it).
NO_REFS_KINDS: frozenset[str] = frozenset({"detail_hidden_by_desk"})

Ref = str | int | bool | None

# A ref that is text must read like an ID or an enum: no spaces, so no sentence of anyone's words fits (L-NOTIFY/3).
_REF_TEXT = re.compile(r"^[A-Za-z0-9_.:@-]{1,120}$")
_KEY = re.compile(r"^[A-Za-z0-9_.:-]{1,200}$")
# Keys that name words a person wrote. Their value may only say whether there is one (a boolean), never carry it.
_WORDS_KEYS = re.compile(r"reason|note|text|words|body|message|summary|title|answer_text|question_text")


@dataclass(frozen=True)
class Action:
    """E-ENTITIES `Action`: a button on the inbox item. `to` is an app route (or one of the keys `answer`, `idea`,
    `conversation`, `draft`, resolved for the item's idea when it is read), `op` a server operation name."""

    label: str
    style: Literal["primary", "line", "text"] = "line"
    to: str | None = None
    op: str | None = None


@dataclass(frozen=True)
class Posted:
    """What `post` did: the inbox item IDs, one per recipient who got a new one."""

    ids: list[int] = field(default_factory=list)


class NotifyError(ValueError):
    pass


def _uuid(value: object, what: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise NotifyError(f"{what} must be a users.id or ideas.id value") from None


def _check_refs(refs: Mapping[str, Ref]) -> None:
    for key, value in refs.items():
        if not isinstance(value, str | int | bool) and value is not None:
            raise NotifyError(f"ref {key!r} must be an ID, enum, number or boolean")
        if isinstance(value, str):
            if _WORDS_KEYS.search(key.lower()):
                raise NotifyError(f"ref {key!r} would carry someone's words; pass an ID or a boolean")
            if not _REF_TEXT.match(value):
                raise NotifyError(f"ref {key!r} must be an ID or an enum, not text")


def outside_channels(kind: str, *, email: bool, teams: bool, reminders: bool, teams_on: bool) -> list[str]:
    """The outside channels one item goes on for one person (L-NOTIFY/1, /2, /4). Teams only while its switch is
    on (DEC-105); a decision, reversal or merge falls back to email when nothing else would carry it."""
    by_email, by_teams = email, teams and teams_on
    if kind in REMINDER_KINDS and not reminders:
        by_email = by_teams = False
    if kind in ALWAYS_OUTSIDE and not (by_email or by_teams):
        by_email = True
    return [c for c, on in (("email", by_email), ("teams", by_teams)) if on]


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

    - `kind`: one of E-ENUMS.inbox.
    - `idea_id`: the idea's row id (`ideas.id`, a UUID), so drafts work too; None for items about no idea.
    - `sender`: a users.id, or "system".
    - `needs_you`, `due_at`: show the item under "Needs you", with its due date (L-INBOX).
    - `actions`: the buttons on the item. None given: the kind's own (L-INBOX.kinds).
    - `refs`: the kind's body as IDs, enums, numbers and booleans only; the template turns them into words.
    - `dedupe_key`: posting the same key to the same person twice keeps one item (reminders, retries); `resolve`
      finds the item again by it.

    The sender is never also a recipient; a recipient listed twice gets one item; people who have left get none.
    """
    if kind not in INBOX_KINDS:
        raise NotifyError(f"unknown inbox kind {kind!r}")
    if any(not isinstance(r, str) or not r for r in recipients):
        raise NotifyError("recipients are users.id values")
    people = list(dict.fromkeys(_uuid(r, "a recipient") for r in recipients))
    refs = dict(refs or {})
    if refs and kind in NO_REFS_KINDS:
        raise NotifyError(f"{kind} carries no refs")
    _check_refs(refs)
    for a in actions:
        if a.to is None and a.op is None:
            raise NotifyError("an action needs a route (to) or an operation (op)")
    if dedupe_key is not None and not _KEY.match(dedupe_key):
        raise NotifyError("dedupe_key must be IDs and enums joined by ':'")
    idea = _uuid(idea_id, "idea_id") if idea_id is not None else None
    from_user = None if sender == "system" else _uuid(sender, "sender")
    people = [p for p in people if p != from_user]
    if not people:
        return Posted()

    rows = conn.execute(
        "SELECT u.id, coalesce(p.email, true) AS email, coalesce(p.teams, true) AS teams, "
        "coalesce(p.reminders, true) AS reminders FROM users u LEFT JOIN comms_prefs p ON p.user_id = u.id "
        "WHERE u.id = ANY(%s::uuid[]) AND u.active",
        (people,),
    ).fetchall()
    prefs = {str(r["id"]): r for r in rows}
    teams_on = killswitch.is_on("comms.teams", conn)
    template, event = f"inbox/{kind}", f"inbox.{kind}"
    payload, buttons = (
        Jsonb(refs),
        Jsonb([{k: v for k, v in asdict(a).items() if v is not None} for a in actions]),
    )
    ids: list[int] = []
    for person in people:
        pref = prefs.get(person)
        if pref is None:
            continue
        item = conn.execute(
            "INSERT INTO notifications (user_id, channel, template, payload, event, urgency, state, sent_at, kind, "
            "from_user_id, idea_uuid, needs_you, due_at, actions, dedupe_key) "
            "VALUES (%s, 'in_app', %s, %s, %s, 'immediate', 'sent', now(), %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (user_id, channel, dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING RETURNING id",
            (person, template, payload, event, kind, from_user, idea, needs_you, due_at, buttons, dedupe_key),
        ).fetchone()
        if item is None:  # this person already has it
            continue
        ids.append(int(item["id"]))
        channels = outside_channels(
            kind, email=pref["email"], teams=pref["teams"], reminders=pref["reminders"], teams_on=teams_on
        )
        for channel in channels:
            # Sent at once, never held for quiet hours or a digest: a 2-hour reminder cannot wait (L-NOTIFY/5).
            conn.execute(
                "INSERT INTO notifications (user_id, channel, template, payload, event, urgency, state, send_after, "
                "kind, from_user_id, idea_uuid, due_at, dedupe_key) "
                "VALUES (%s, %s, %s, %s, %s, 'immediate', 'queued', now(), %s, %s, %s, %s, %s) "
                "ON CONFLICT (user_id, channel, dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING",
                (person, channel, template, payload, event, kind, from_user, idea, due_at, dedupe_key),
            )
    if ids:
        log.info("notify.posted", inbox_kind=kind, item_count=len(ids))
    return Posted(ids=ids)


def resolve(conn: Conn, dedupe_key: str, *, recipients: Sequence[str] | None = None) -> int:
    """The action an item asked for is done (or no longer can be): it leaves "Needs you" for everyone who has it,
    or for `recipients` only. A key also resolves the keys under it (`qs:<set>` covers `qs:<set>:24` and
    `qs:<set>:2`). Returns how many items changed; calling it again changes nothing."""
    if not _KEY.match(dedupe_key):
        raise NotifyError("dedupe_key must be IDs and enums joined by ':'")
    people = None if recipients is None else [_uuid(r, "a recipient") for r in recipients]
    if people == []:
        return 0
    changed = conn.execute(
        "UPDATE notifications SET needs_you = false, resolved_at = now() WHERE channel = 'in_app' AND needs_you "
        "AND (dedupe_key = %s OR starts_with(dedupe_key, %s)) AND (%s::uuid[] IS NULL OR user_id = ANY(%s::uuid[]))",
        (dedupe_key, dedupe_key + ":", people, people),
    ).rowcount
    if changed:
        log.info("notify.resolved", item_count=changed)
    return changed
