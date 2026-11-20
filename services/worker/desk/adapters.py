"""The other lanes' entry points, each behind one function, so a change to theirs touches only this file.

- `tell`: L-NOTIFY and L-INBOX (lane A, `notify.post`, BLD-A180). A no-op until `notify` is importable.
- `resolve`: L-INBOX.rules/3 (lane A, `notify.resolve`): a Needs you item, and every item keyed under it, leaves the
  list once its action is done. A no-op until `notify` has `resolve` (it lands with lane A's inbox).
- `say`: L-CONVO (lane F, `convo.post`): a line in the idea's conversation, IDs only. Only through `convo.post`
  (BLD-B249).
- `hide`: L-HIDE (lane C, `hide.hide_text`): free text masked before it is stored or shown to anyone else, each value
  kept sealed in the vault under the idea with a `hidden_details` row. `by` is the users.id of whoever typed it.
  `hide_answer`, `answer_words` and `forget_answer`: a sharer's answer (lane C's `hide_message`, `own_words`).
  `hide_queued`: a question the reviewer queued, masked the same way and nothing else kept (lane C's `forget`).
- `lock_idea`, `lock_refs`: lane C's per-idea lock (`hide.core.lock`), taken FIRST in every transaction that hides,
  before any idea, set, answer or window row lock, so a reviewer's "Hide this" (which takes it first too) and a desk
  action on the same idea always queue in one order and never deadlock (BLD-B247).
- `schedule`: lane A's timers. A no-op until lane A publishes its interface; every screen works it out on read.
"""

from __future__ import annotations

import datetime as dt
import importlib
from collections.abc import Mapping, Sequence
from typing import Any

from core.db import Conn
from core.logging import get_logger
from hide import Hidden, forget, hide_message, hide_text, sealed_key
from hide.core import lock as hide_lock
from hide.core import own_words

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
    Written only through lane F's `convo.post` (SHIP_PLAN §5a): it places each line just after the idea's last one,
    so lines written in one transaction read back in the order they were written (BLD-F013, BLD-F057, L-CONVO). The
    desk has no direct insert of its own any more (BLD-B249)."""
    from convo import post  # here, not at the top: lane F's reads use the desk's words (`desk.when`)

    post(
        conn, idea_uuid, event, author_user_id=author_user_id, author_code=author_code, payload=dict(payload or {}),
        question_set_id=question_set_id, entry_type=entry_type, at=at,
    )  # fmt: skip


def hide(
    conn: Conn, idea_uuid: str, text: str, *, by: str, source: str = "desk", source_id: str | None = None
) -> tuple[str, int]:
    """The masked copy of `text` and how many details were hidden (L-HIDE; DEC-103), through lane C's `hide_text`
    inside the caller's transaction. The desk's own words (a question, a reason, a note) are `source="desk"`; a
    sharer's answer is `source="answer"` with its row id, so its details keep their ids across autosaves and the
    sharer's own words are sealed for them alone (BLD-B246)."""
    return hide_text(conn, idea_uuid, text, by=by, source=source, source_id=source_id)


def hide_queued(conn: Conn, idea_uuid: str, text: str, *, by: str, question_id: str) -> str:
    """The masked copy of a question the reviewer queued and has not sent (BLD-B272). It goes through `hide` exactly
    as a sent question does (the patterns, then the gatekeeper; L-HIDE.rules/1, /3), keyed by the question's row, and
    then what hide kept for it (its `hidden_details` rows, and each vault value no other row of the idea holds) is
    dropped in the same transaction (lane C's `forget`). Nobody but its reviewer reads a queued set, so no other page
    may count or show a detail from it: the sharer's page lists every `hidden_details` row of the idea. Only the masked
    copy is stored; at Send the questions go through `hide` again, as they always have."""
    masked, _ = hide(conn, idea_uuid, text, by=by, source="desk", source_id=question_id)
    forget(conn, idea_uuid, source="desk", source_id=question_id)
    return masked


def lock_idea(conn: Conn, idea_uuid: str) -> None:
    """Lane C's lock on one idea, held until the caller's transaction ends (re-entrant in one session). Take it as the
    first statement of any transaction that hides text on the idea, before any row lock (BLD-B247)."""
    hide_lock(conn, str(idea_uuid))


def lock_refs(conn: Conn, *refs: str) -> None:
    """`lock_idea` for ideas named by IDEA- reference or uuid, in uuid order (the order `merging.lock_pair` locks their
    rows in). Each uuid is read with no row lock; a reference that is no idea is left to the caller's own 404."""
    found: set[str] = set()
    for ref in refs:
        if not ref:
            continue
        column = "idea_id" if ref.startswith("IDEA-") else "id::text"
        row = conn.execute(f"SELECT id FROM ideas WHERE {column} = %s", (ref,)).fetchone()  # noqa: S608 (fixed)
        if row is not None:
            found.add(str(row["id"]))
    for idea_uuid in sorted(found):
        lock_idea(conn, idea_uuid)


def hide_answer(
    conn: Conn, idea_uuid: str, text: str, *, by: str, answer_id: str, gatekeeper: bool
) -> Hidden:
    """A sharer's answer, through lane C's `hide_message` with `source="answer"` and the answer's id: its details keep
    their ids across saves and the sharer's own words are sealed for them alone. Autosave runs the patterns only
    (`gatekeeper=False`, no model call per keystroke); sending runs the gatekeeper once (L-HIDE.rules/1; BLD-B247)."""
    return hide_message(
        conn, idea_uuid, text, by=by, source="answer", source_id=answer_id, gatekeeper=gatekeeper
    )


def answer_words(conn: Conn, idea_uuid: str, answer_id: str) -> str | None:
    """The sharer's own words for an answer, as they typed them (worker only; never returned to anyone else)."""
    return own_words(conn, "answer", answer_id, idea_uuid=str(idea_uuid))


def forget_answer(conn: Conn, idea_uuid: str, answer_id: str) -> None:
    """An answer emptied again holds no words: its details and its sealed words go, so a co-sharer who takes the empty
    draft over seals their own words under the same answer id (L-HIDE.rules/4, L-QUESTIONS.answer/4; BLD-B247)."""
    conn.execute(
        "DELETE FROM hidden_details WHERE idea_uuid = %s AND source = 'answer' AND source_id = %s",
        (idea_uuid, answer_id),
    )
    conn.execute(
        "DELETE FROM idea_words_sealed WHERE idea_uuid = %s AND source = 'answer' AND source_id = %s",
        (idea_uuid, sealed_key(str(idea_uuid), answer_id)),
    )


def schedule(
    conn: Conn, kind: str, entity: str, due_at: dt.datetime, payload: Mapping[str, Any] | None = None
) -> None:
    """Ask lane A's timer engine to call a lane B handler at `due_at`. Screens never depend on it having run."""
    _ = (conn, payload)
    target, _, target_id = entity.partition(":")
    log.info(
        "desk.schedule.pending", kind=kind, target=target, target_id=target_id
    )  # a bare ID passes the value scan
