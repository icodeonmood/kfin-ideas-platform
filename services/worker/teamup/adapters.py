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
- `lock_hide`: lane C's per-idea lock (`hide.core.lock`), taken FIRST, in uuid order, in a transaction that can reach
  lane C's hide or `forget`, before `store.lock_ideas` takes the ideas' rows in the same order (BLD-B247, BLD-F096).
- `drop_queued`: lane B's `desk.asking.drop_queued`: a merged idea's queued question sets go, and first what lane C's
  hide kept for each of their questions (L-MERGE.effects/5, BLD-B272).
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
from hide import core as hide_core
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
    """A line in the idea's conversation, rendered from its code at read time. Payload: IDs only.

    The conversation reads `ORDER BY at, id` and ids are random, so lines said in one action at one time would
    come out shuffled ("Kavya joined" before "Ravi merged"). Each line is placed just after the idea's last line
    when its time would tie or come before it, so the conversation reads in the order things were said."""
    at = _next_at(conn, idea_uuid, at)
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


def _next_at(conn: Conn, idea_uuid: str, at: dt.datetime | None) -> dt.datetime:
    """`at` (now by default), or one microsecond after the idea's last conversation line if that is not earlier."""
    t = at or dt.datetime.now(dt.UTC)
    row = conn.execute(
        "SELECT max(at) AS last FROM conversation_entries WHERE idea_uuid = %s", (idea_uuid,)
    ).fetchone()
    last = row["last"] if row else None
    return last + dt.timedelta(microseconds=1) if last is not None and last >= t else t


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


def lock_hide(conn: Conn, *idea_uuids: object) -> None:
    """Lane C's lock on each idea, in uuid order (the order `store.lock_ideas` locks their rows in), held until the
    caller's transaction ends and re-entrant in one session (BLD-B247, BLD-F096). Take it as the first lock of any
    transaction that can reach lane C's hide or `forget` on these ideas, before any row lock: a reviewer's "Hide this"
    takes it first too, and lane B's desk merge takes both ideas' locks first (`desk.adapters.lock_refs`, then
    `lock_pair`), so a team-up answer and a desk action on the same two ideas always queue in one order."""
    for idea_uuid in sorted({str(u) for u in idea_uuids if u}):
        hide_core.lock(conn, idea_uuid)


def drop_queued(conn: Conn, idea_uuid: str) -> list[str]:
    """Lane B's `desk.asking.drop_queued` (BLD-B272): every reviewer's queued question set on the idea goes with its
    questions, and first, for each question, what lane C's hide kept for it (`forget`): a reviewer's "Hide this"
    writes a `hidden_details` row keyed by every question's id, and the sharer's page lists every row of the idea.
    Lane C's lock on the idea must be held already (`lock_hide`, taken first). Returns the deleted sets' ids."""
    from desk.asking import drop_queued as desk_drop_queued  # lane B's module, loaded when a merge needs it

    return desk_drop_queued(conn, idea_uuid)


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
