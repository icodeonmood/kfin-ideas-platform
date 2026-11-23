"""The other lanes' entry points, each behind one function, so a change to theirs touches only this file.

- `tell`: L-NOTIFY and L-INBOX (lane A, `notify.post`). Called inside our transaction; `refs` carry IDs, enums,
  numbers and booleans only, never text.
- `resolve`: lane A's `notify.resolve(conn, dedupe_key, *, recipients=None)`, which clears the lead's "Needs you"
  item when a request is withdrawn, answered or closed. Called when present; until it lands on `main` the request
  id is logged instead.
- `say`: L-CONVO (lane F3, `convo.post`, SHIP_PLAN §5a). Used when importable; otherwise the line is written to
  `conversation_entries` directly, as an event with IDs only, exactly as lane B's `say` does.
- `hide`: L-HIDE (lane C's `hide.hide_text`: the patterns, then the gatekeeper, then names; DEC-103, BLD-F097) on
  the three team-up texts others read, as the sealed source `teamup`: the note (`source_id` = the request id), the
  lead's decline reason (`decline_id`) and a draft's ask (`ask_id`). Each value is kept in lane C's vault under the
  idea's scope and the typer's own words are sealed for them alone (`own_words`); everyone else reads the masked
  copy. `write_masked` is lane F's writer for lane C's re-check (`hide/recheck.py`).
- `gate`: lane C's `hide.gate` (BLD-C234): the gatekeeper asked for one of those texts BEFORE the transaction and
  `lock_hide`, so its model call holds no lock (BLD-F100); the answer goes back in as `hide(gate=...)`.
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
from hide import Gate as Gate
from hide import core as hide_core
from hide import gate as hide_gate
from hide import hide_text
from onepc.context import seal_text

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


HIDE_SOURCE = "teamup"  # lane C's sealed source for the three team-up texts (E-ENUMS sealed_source, BLD-F097)
_TEXT_TABLES = {  # where each team-up text's masked copy is stored, by its source_id's suffix
    "": ("teamup_requests",),  # the note
    "ask": ("merge_requests",),  # a draft's ask
    "decline": ("teamup_requests", "merge_requests"),  # the lead's reason, on the request's own table
}


def decline_id(request_id: str) -> str:
    """The hide `source_id` of the lead's decline reason on a team-up or draft merge request."""
    return f"{request_id}:decline"


def ask_id(merge_request_id: str) -> str:
    """The hide `source_id` of a draft's ask (the merge request's note)."""
    return f"{merge_request_id}:ask"


def gate(conn: Conn, idea_uuid: str, text: str) -> Gate:
    """Lane C's gatekeeper asked for a team-up text with no lock held (`hide.gate`, BLD-C234, BLD-F100), so the model
    call (seconds on the real route) runs before `lock_hide` and every row lock, not under them. Hand the result to
    `hide(gate=...)` with the SAME text: hide uses it only for that exact string and otherwise asks again under the
    lock. Lane C's gate checks no ownership: call it only once this person may write the text on this idea, and with
    no transaction open. Nothing is stored; the logs carry IDs only."""
    return hide_gate(conn, idea_uuid, text, source=HIDE_SOURCE)


def hide(
    conn: Conn, idea_uuid: str, text: str, *, by: str, source_id: str, gate: Gate | None = None
) -> tuple[str, int]:
    """The masked copy of a team-up text and how many details were hidden (L-HIDE, DEC-103, BLD-F097), through lane
    C's `hide_text`: patterns, then the gatekeeper, then names. `by` is the users.id of the person who typed it, the
    one person who reads it back (`own_words`). Call it in the transaction that stores the masked copy, after lane
    C's lock on every idea the transaction locks (`lock_hide`, taken first). `source_id` must be distinct across
    ideas: the request id for a note, `decline_id` for a reason, `ask_id` for a draft's ask. `gate`: the
    gatekeeper's finds for this same text, asked before the lock (`gate` above, BLD-F100)."""
    return hide_text(conn, idea_uuid, text, by=by, source=HIDE_SOURCE, source_id=source_id, gate=gate)


def own_words(conn: Conn, idea_uuid: str, source_id: str) -> str | None:
    """The typer's own words for one team-up text (lane C's `own_words`), or None when none were sealed (a request
    sent before BLD-F097, or seeded). Only ever handed to the person who typed it."""
    return hide_core.own_words(conn, HIDE_SOURCE, source_id, idea_uuid=idea_uuid)


def write_masked(conn: Conn, source_id: str, masked: str) -> int:
    """Lane F's writer for lane C's re-check (`hide/recheck.py`, BLD-F097): put a team-up text masked again in the
    copy others read. `source_id` names the text: "<request id>" a team-up note (`teamup_requests.note_encrypted`),
    "<request id>:decline" the lead's reason (`lead_reason_encrypted` on the table that holds the request), and
    "<merge request id>:ask" a draft's ask (`merge_requests.note_encrypted`). A note or an ask a merge has carried
    on (`merges.note_encrypted`) is written again too. Runs in the re-check's transaction, under lane C's lock on
    the idea. Returns how many copies were written; the log carries the request id and counts only."""
    rid, _, part = str(source_id).partition(":")
    if not hide_core.is_uuid(rid) or part not in _TEXT_TABLES:
        log.info("teamup.rewrite.unknown_source")
        return 0
    column = "lead_reason_encrypted" if part == "decline" else "note_encrypted"
    tables = _TEXT_TABLES[part]
    copies = 0
    for table in tables:
        sql = f"UPDATE {table} SET {column} = %s WHERE id = %s AND {column} IS NOT NULL"  # noqa: S608
        copies += conn.execute(sql, (seal_text(table, column, rid, masked), rid)).rowcount
    if copies and part != "decline":
        link = "merge_request_id" if part == "ask" else "teamup_request_id"
        sql = f"SELECT id FROM merges WHERE {link} = %s AND note_encrypted IS NOT NULL"  # noqa: S608
        for m in conn.execute(sql, (rid,)).fetchall():
            conn.execute(
                "UPDATE merges SET note_encrypted = %s WHERE id = %s",
                (seal_text("merges", "note_encrypted", str(m["id"]), masked), m["id"]),
            )
            copies += 1
    log.info("teamup.text_rewritten", request_id=rid, copies=copies)
    return copies


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
