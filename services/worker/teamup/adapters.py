"""The other lanes' entry points, each behind one function, so a change to theirs touches only this file.

- `tell`: L-NOTIFY and L-INBOX (lane A, `notify.post`). Called inside our transaction; `refs` carry IDs, enums,
  numbers and booleans only, never text.
- `resolve`: lane A's `notify.resolve(conn, dedupe_key, *, recipients=None)`, which clears the lead's "Needs you"
  item when a request is withdrawn, answered or closed. Called when present; until it lands on `main` the request
  id is logged instead.
- `say`: L-CONVO (lane F3, `convo.post`, SHIP_PLAN §5a). Used when importable; otherwise the line is written to
  `conversation_entries` directly, as an event with IDs only, exactly as lane B's `say` does.
- `hide`: L-HIDE (lane C). Until lane C's entry point is on `main`, free text others read (the note, the lead's
  reason) is masked with the shared patterns (kind + •••• + last two), as lane B's `adapters.hide` does.
- `note_min`: the team-up note's minimum length, a promise in the company repo's `rules/promises.md`.
"""

from __future__ import annotations

import datetime as dt
import importlib
from collections.abc import Mapping, Sequence
from types import ModuleType

from psycopg.types.json import Jsonb

from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from pii.patterns import scan

log = get_logger("teamup")

Ref = str | int | bool | None

TEAMUP_NOTE_MIN = 30  # P-PRODUCT.promises, L-TEAMUP.rules/2, L-MERGE.request: the pack's value


def _module(name: str) -> ModuleType | None:
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name != name:  # the module exists but something it imports does not: a real fault
            raise
        return None


def request_key(request_id: str) -> str:
    """The dedupe key of the lead's "Needs you" item for a request (team-up or draft merge request)."""
    return f"teamup_request:{request_id}"


def tell(
    conn: Conn,
    kind: str,
    recipients: Sequence[str],
    *,
    idea_uuid: str | None = None,
    sender: str = "system",
    needs_you: bool = False,
    due_at: dt.datetime | None = None,
    actions: Sequence[tuple[str, str, str | None, str | None]] = (),  # (label, style, to, op)
    refs: Mapping[str, Ref] | None = None,
    dedupe_key: str | None = None,
) -> None:
    """Tell people something through lane A's inbox. IDs and enums only in `refs` (non-negotiable 3)."""
    people = [r for r in dict.fromkeys(recipients) if r and r != sender]
    if not people:
        return
    notify = _module("notify")
    if notify is None:
        log.info("teamup.tell.pending", kind=kind, count=len(people))
        return
    notify.post(
        conn, kind, people, idea_id=idea_uuid, sender=sender, needs_you=needs_you, due_at=due_at,
        actions=[notify.Action(label=label, style=style, to=to, op=op) for label, style, to, op in actions],
        refs=refs, dedupe_key=dedupe_key,
    )  # fmt: skip


def resolve(conn: Conn, request_id: str) -> None:
    """Clear the lead's "Needs you" item for this request (idempotent on lane A's side)."""
    notify = _module("notify")
    fn = getattr(notify, "resolve", None) if notify is not None else None
    if fn is None:
        log.info("teamup.resolve.pending", request_id=request_id)
        return
    fn(conn, request_key(request_id))


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
    """A line in the idea's conversation, rendered from its code at read time. Payload: IDs only."""
    convo = _module("convo")
    post = getattr(convo, "post", None) if convo is not None else None
    if post is not None:
        post(
            conn, idea_uuid, event, author_user_id=author_user_id, author_code=author_code, payload=payload,
            question_set_id=question_set_id, entry_type=entry_type, at=at,
        )  # fmt: skip
        return
    conn.execute(
        "INSERT INTO conversation_entries (idea_uuid, type, event, payload, author_user_id, author_code, "
        "question_set_id, at) VALUES (%s, %s, %s, %s, %s, %s, %s, coalesce(%s, now()))",
        (
            idea_uuid,
            entry_type,
            event,
            Jsonb(dict(payload or {})),
            author_user_id,
            author_code,
            question_set_id,
            at,
        ),
    )


_KINDS = {"Mobile": "Phone", "Email": "Email", "Bank": "Account", "Date": "Date of birth"}


def _mask(value: str, label: str, before: str) -> str:
    """'Folio ••••89': the kind, unless the words just before already name it, then the last two characters."""
    first = label.split(" ")[0]
    kind = _KINDS.get(first, first)
    tail = "".join(ch for ch in value if ch.isalnum())[-2:]
    lead_in = before[-16:].lower().rstrip(" :#-")
    named = lead_in.endswith(kind.lower()) or lead_in.endswith(first.lower())
    return f"••••{tail}" if named else f"{kind} ••••{tail}"


def hide(conn: Conn, idea_uuid: str, text: str) -> tuple[str, int]:
    """The masked copy of `text` and how many details were hidden (L-HIDE; DEC-103)."""
    _ = (conn, idea_uuid)  # lane C's version keeps the values in the vault under the idea's scope
    matches = sorted(scan(text, kfin_domains=get_settings().kfin_domains), key=lambda m: m.start)
    out: list[str] = []
    last, n = 0, 0
    for m in matches:
        if m.start < last:
            continue
        out.append(text[last : m.start])
        out.append(_mask(text[m.start : m.end], m.label, text[: m.start]))
        last, n = m.end, n + 1
    out.append(text[last:])
    return "".join(out), n


def note_min() -> int:
    """`notes.teamup_note_min_chars` from the company repo's promises rule; the pack's 30 when it is not there."""
    from rules.loader import RulesConfigError, load_rule

    try:
        data = load_rule(get_settings().company_repo_path, "promises").data
    except RulesConfigError as exc:
        if any("missing" in p for p in exc.problems):  # no company repo yet (tests, a fresh stack)
            return TEAMUP_NOTE_MIN
        raise  # a broken rule must not pass silently (rules.loader, plan P1)
    return int((data.get("notes") or {}).get("teamup_note_min_chars", TEAMUP_NOTE_MIN))
