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
from ideapage.read import COMMITTEE_ROLES, DESK_ROLES

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
# Kinds sent as the review desk as a whole (L-HIDE/7, BLD-A205): the reviewer who acted is never stored on the item or
# its email, so no later read can name them; the reader shows "The review desk". DEC-111 (BLD-B257): every kind the
# desk sends a sharer is one, so a sharer never sees a reviewer's name: the questions, their reminders, the decision,
# a desk merge and a revised worth. The reader checks the kind, so an item stored earlier with a reviewer as its
# sender reads as the desk too. A reversal is the Ones Committee's (`decision_reversed`): see AS_THE_COMMITTEE.
AS_THE_DESK: frozenset[str] = frozenset(
    {"detail_hidden_by_desk", "questions", "answer_reminder", "decision", "desk_merge", "worth_revised"}
)
# DEC-111 (BLD-A221): any item whose refs say `as_desk: true` is the review desk speaking as a whole, whatever its kind.
# Lane F posts `comment` and `mention` with it when the author writes as the desk (a reviewer not on the build team,
# S-08's own test). Like AS_THE_DESK, the reviewer is never stored on the item or its outside messages.
AS_DESK_REF = "as_desk"


def as_the_desk(kind: str, refs: Mapping[str, object] | None) -> bool:
    """True when an item is from the review desk as a whole, so no person is stored or shown (DEC-111)."""
    return kind in AS_THE_DESK or (refs or {}).get(AS_DESK_REF) is True


# DEC-113 (BLD-A231): a sharer never sees a committee member's name either; it reads "The Ones Committee", with no
# avatar or initials. The review desk and the committee still see each other's names. Kinds the committee sends: to a
# reader who holds a desk or committee role now (`sees_names`) the member is stored and named; for everyone else the
# member is never stored on the item or its outside messages, and the reader checks the role again, so an item stored
# earlier (or by the club seed) with the member as its sender reads as the committee too.
AS_THE_COMMITTEE: frozenset[str] = frozenset({"decision_reversed"})
# DEC-113 (BLD-A231): any item whose refs say `as_committee: true` is the Ones Committee speaking as one, whatever its
# kind. Lane F posts `comment` and `mention` with it, to recipients outside the desk and the committee, when a member
# writes in the conversation (S-08). As with `as_desk`, the member is never stored on the item or its outside messages.
AS_COMMITTEE_REF = "as_committee"
# Who reads the names of the people at the review desk and on the Ones Committee: the same live role grants as
# `ideapage.read.Viewer.sees_desk_names` (DEC-111, BLD-E053).
NAMES_ROLES: frozenset[str] = DESK_ROLES | COMMITTEE_ROLES


def as_the_committee(kind: str, refs: Mapping[str, object] | None) -> bool:
    """True when an item is the Ones Committee speaking as one to whoever reads it (`as_committee: true`), so no member
    is stored or shown (DEC-113). A committee kind (AS_THE_COMMITTEE) depends on the reader: see `sees_names`."""
    return (refs or {}).get(AS_COMMITTEE_REF) is True


def sees_names(conn: Conn, people: Sequence[str]) -> set[str]:
    """Those of `people` (users.id values) who hold a review desk or Ones Committee role now, read from the live role
    grants (DEC-111, DEC-113): they still read a committee member's name. Everyone else reads the committee as one."""
    ids = [p for p in dict.fromkeys(str(p) for p in people) if _is_uuid(p)]
    if not ids:
        return set()
    rows = conn.execute(
        "SELECT DISTINCT user_id FROM role_grants WHERE user_id = ANY(%s::uuid[]) AND role = ANY(%s::text[]) "
        "AND valid_from <= now() AND (valid_to IS NULL OR valid_to > now())",
        (ids, sorted(NAMES_ROLES)),
    ).fetchall()
    return {str(r["user_id"]) for r in rows}


Ref = str | int | bool | None

# A ref that is text must read like an ID or an enum: no spaces, so no sentence of anyone's words fits (L-NOTIFY/3).
_REF_TEXT = re.compile(r"^[A-Za-z0-9_.:@-]{1,120}$")
# A key is IDs, enums and times joined by ":"; a time may carry its offset ("20261119T1020+0530", lane B's reminder
# thresholds). No spaces, so no sentence fits.
_KEY = re.compile(r"^[A-Za-z0-9_.:+-]{1,200}$")
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
    """What `post` did: the inbox item IDs, one per recipient who got a new one (`ids`), and the open items a repeat
    post with the same key brought up to date (`updated`)."""

    ids: list[int] = field(default_factory=list)
    updated: list[int] = field(default_factory=list)


class NotifyError(ValueError):
    pass


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


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
    - `dedupe_key`: one item per person per key (reminders, retries); `resolve` finds the item again by it. A
      repeat post with the same key updates that person's item in place while it is open (not resolved): the latest
      `due_at`, `refs`, `actions` and `needs_you` replace the old ones on the same row, and an email or Teams message
      still waiting to go takes the new date and refs. No new row is written and no second outside message is queued;
      read and archived stay as they were (BLD-A188: lane B's "Give 2 more days" posts `questions` again under
      `qs:<set>` with the new `due_at`, so every screen shows one countdown, V-ACC.track/3). Once the item is resolved,
      a repeat post leaves it as it is and posts nothing.

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
    stored_from = None if as_the_desk(kind, refs) or as_the_committee(kind, refs) else from_user
    # DEC-113: a committee kind keeps its member only on the rows of people who hold a desk or committee role now
    named = sees_names(conn, people) if stored_from is not None and kind in AS_THE_COMMITTEE else None

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
    updated: list[int] = []
    for person in people:
        pref = prefs.get(person)
        if pref is None:
            continue
        sent_by = stored_from if named is None or person in named else None
        # A repeat key updates the open item in place (`xmax = 0` only on a fresh insert); a resolved one is left
        # alone and returns nothing.
        item = conn.execute(
            "INSERT INTO notifications (user_id, channel, template, payload, event, urgency, state, sent_at, kind, "
            "from_user_id, idea_uuid, needs_you, due_at, actions, dedupe_key) "
            "VALUES (%s, 'in_app', %s, %s, %s, 'immediate', 'sent', now(), %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (user_id, channel, dedupe_key) WHERE dedupe_key IS NOT NULL DO UPDATE SET "
            "due_at = EXCLUDED.due_at, payload = EXCLUDED.payload, actions = EXCLUDED.actions, "
            "needs_you = EXCLUDED.needs_you WHERE notifications.resolved_at IS NULL "
            "RETURNING id, (xmax = 0) AS inserted",
            (
                person,
                template,
                payload,
                event,
                kind,
                sent_by,
                idea,
                needs_you,
                due_at,
                buttons,
                dedupe_key,
            ),
        ).fetchone()
        if item is None:  # this person had it, and it is resolved: nothing to post
            continue
        if not item["inserted"]:  # an open item brought up to date; its outside messages are not sent again
            updated.append(int(item["id"]))
            conn.execute(
                "UPDATE notifications SET due_at = %s, payload = %s WHERE user_id = %s AND dedupe_key = %s "
                "AND channel <> 'in_app' AND state = 'queued'",
                (due_at, payload, person, dedupe_key),
            )
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
                (person, channel, template, payload, event, kind, sent_by, idea, due_at, dedupe_key),
            )
    if ids or updated:
        log.info("notify.posted", inbox_kind=kind, item_count=len(ids), updated_count=len(updated))
    return Posted(ids=ids, updated=updated)


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
