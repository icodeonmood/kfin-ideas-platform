"""L-HIDE: customers' personal details are hidden from everyone but the person who typed them (DEC-103, DEC-107).

Patterns, then the gatekeeper (when `ai.all` is on), then names in the same sentence as another detail, run on the
text before any other service, model, person or log sees it. The masked copy ("Folio ••••89") is the only copy
anyone else gets. Each value is stored encrypted in the worker-only vault; the person's own words in the worker-only
`idea_words_sealed`; `hidden_details` keeps the kind, span, mask and vault tag, never the value (`hide/core.py`).

Entry points other lanes call (fixed; lane C, BLD-C060):

Call every entry point that stores inside ONE transaction with the caller's own write of the masked copy:

    with conn.transaction():
        hidden = hide_message(conn, idea_uuid, text, by=user_id, source="conversation", source_id=entry_id)
        conn.execute("UPDATE conversation_entries SET text_encrypted = %s WHERE id = %s", (seal(hidden.masked), …))

The idea's advisory lock is taken inside and held until that transaction ends, so a reviewer's "Hide this" cannot
land between the hiding and the write. On an autocommit connection with no transaction around the call, the lock
ends with the call and the guarantee is lost. The gatekeeper's model call runs before the lock is taken. A failure
inside rolls back only hide's own savepoints, so the caller's transaction stays usable (BLD-C067).

Lock order (BLD-C067): every caller takes hide's advisory lock, `hide.core.lock(conn, idea_uuid)`, BEFORE any idea,
answer, conversation entry or other row lock in the same transaction. Calling `hide_text`, `hide_message` or `forget`
before your own `SELECT … FOR UPDATE` or `UPDATE` does that for you; if you must lock rows first, call
`hide.core.lock(conn, idea_uuid)` at the start of the transaction (it is re-entrant within one transaction). Then a
`hide_message` call holds that lock across the gatekeeper's model call, which BLD-C067 otherwise avoids: a known cost
for such callers, not the pattern to copy, until a pre-gate (`hide.gate`, not built) lets them ask the gatekeeper
before any lock.
`desk_hide`, `show` and `hide_again` take the advisory lock first and the rows after it; lane B's desk transactions
take it first too. Two transactions that take the two kinds of lock in opposite orders can deadlock.

`hide_text(conn, idea_uuid, text, *, by, source="desk", source_id=None) -> (masked_text, hidden_count)`
    Any text written on an idea: a desk question or reason ("desk"), an answer, a conversation message, an edit.
    Stores each value sealed with a `hidden_details` row and returns the masked copy and how many were hidden.
    `by` is the users.id of whoever typed it (the one person who may read the values). With a sealed source
    ("message", "answer", "conversation", "edit") and its `source_id`, their own words are sealed too.

`hide_message(conn, idea_uuid, text, *, by, source="message", source_id, gatekeeper=True) -> Hidden`
    What drafts need (L-DRAFT, through lane C's adapter), for a message or an edit of one:
    - `Hidden.masked`: the masked copy, for `idea_messages.text_encrypted` and for every service and model;
    - `Hidden.spans`: `[{start, end, kind, hid}]` in the person's own text, for the dotted underline
      (L-HIDE.rules/2; `idea_messages.spans` takes start, end and kind);
    - `Hidden.details`: E-ENTITIES `HiddenDetail` for the draft panel and the `hidden` stream event;
    - `Hidden.counts`, `Hidden.hidden_count`, `Hidden.kinds_line` ("Folio number, PAN and phone number") and
      `Hidden.receipt` ("Hid 3 personal details from everyone but you: Folio ••••89, PAN ••••4F, Phone ••••10.").
    Re-running it on an edited message keeps each detail's id while its value is still there, and keeps the
    person's "Show it" for that value. Values a reviewer hid on the idea are hidden in every new text, as whole
    words in any case. Lane F's conversation: `source="conversation"`, `source_id` = the conversation_entries id,
    `by` = the author's users.id. The sealed words are keyed by `core.sealed_key`: row ids and ids that start with
    the idea's uuid as they are, any other id under the idea's uuid (BLD-C066). When the gatekeeper cannot run,
    the text goes on with the patterns and names, `hide.gatekeeper_skipped` is audited and a re-check is queued
    (`hide/recheck.py`).

`forget(conn, idea_uuid, *, source, source_id) -> int`
    A text is removed (lane F's L-CONVO/10: a conversation message removed within five minutes; lane C's own
    removals): drops its `hidden_details` rows, the person's sealed words (by `sealed_key`) and each vault value no
    other `hidden_details` row of the idea still holds, so a value also hidden in another text stays. Returns how
    many `hidden_details` rows were removed. Takes the advisory lock first; call it in the transaction that removes
    the text, before your own row locks. Logged and audited (`hide.forgotten`) with IDs and counts only.

`preview(conn, text, *, idea_uuid=None) -> Hidden`
    Spans while the person types: patterns, names and the idea's hidden values, no model call, nothing stored.
    It has no HTTP route: A-API names none, and lane C's draft (its message path and channels) is its only caller.

Offsets in `Hidden.spans` count code points (Python's). The browser counts UTF-16 units: the web edge converts spans
on the way out (`apps/web/src/server/hide-offsets.ts`), and the desk's "Hide this" sends `units: "utf16"`, which
the worker converts against the text the reviewer read (the web app never holds it).

`desk_hide`, `show`, `hide_again` (`hide/desk.py`) serve `POST /api/desk/ideas/:id/hide` and
`POST /api/drafts/:id/hidden/:hid/show|hide`. Files are `hide/files.py`.
"""

from __future__ import annotations

import uuid

from core.db import Conn
from hide.core import (
    DETAIL_SOURCES,
    SEALED_SOURCES,
    Hidden,
    HideError,
    forget,
    hide_into,
    preview,
    sealed_key,
)
from hide.desk import desk_hide, hide_again, show
from hide.detect import Found, find, kinds_line, mask, receipt

__all__ = [
    "Found",
    "Hidden",
    "HideError",
    "desk_hide",
    "find",
    "forget",
    "hide_again",
    "hide_message",
    "hide_text",
    "kinds_line",
    "mask",
    "preview",
    "receipt",
    "sealed_key",
    "show",
]


def hide_text(
    conn: Conn, idea_uuid: str, text: str, *, by: str, source: str = "desk", source_id: str | None = None
) -> tuple[str, int]:
    """Hide the customers' details in `text` written on an idea. Returns (masked_text, hidden_count)."""
    if source not in DETAIL_SOURCES:
        raise ValueError("unknown hide source")
    sid = source_id or str(uuid.uuid4())
    done = hide_into(conn, idea_uuid, text, by=by, source=source, source_id=sid, seal=source_id is not None)
    return done.masked, done.hidden_count


def hide_message(
    conn: Conn,
    idea_uuid: str,
    text: str,
    *,
    by: str,
    source: str = "message",
    source_id: str,
    gatekeeper: bool = True,
) -> Hidden:
    """Hide a draft message (or an answer, conversation message or edit) and seal the person's own words."""
    if source not in SEALED_SOURCES:
        raise ValueError("hide_message takes a message, answer, conversation or edit")
    return hide_into(conn, idea_uuid, text, by=by, source=source, source_id=source_id, gatekeeper=gatekeeper)
