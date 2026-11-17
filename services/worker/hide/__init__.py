"""L-HIDE: customers' personal details are hidden from everyone but the person who typed them (DEC-103, DEC-107).

Patterns, then the gatekeeper (when `ai.all` is on), then names in the same sentence as another detail, run on the
text before any other service, model, person or log sees it. The masked copy ("Folio ••••89") is the only copy
anyone else gets. Each value is stored encrypted in the worker-only vault; the person's own words in the worker-only
`idea_words_sealed`; `hidden_details` keeps the kind, span, mask and vault tag, never the value (`hide/core.py`).

Entry points other lanes call (fixed; lane C, BLD-C060):

`hide_text(conn, idea_uuid, text, *, by, source="desk", source_id=None) -> (masked_text, hidden_count)`
    Any text written on an idea: a desk question or reason ("desk"), an answer, a conversation message, an edit.
    Stores each value sealed with a `hidden_details` row and returns the masked copy and how many were hidden.
    `by` is the users.id of whoever typed it (the one person who may read the values). With a sealed source
    ("message", "answer", "conversation", "edit") and its `source_id`, their own words are sealed too. Runs inside
    the caller's transaction.

`hide_message(conn, idea_uuid, text, *, by, source="message", source_id, gatekeeper=True) -> Hidden`
    What drafts need (L-DRAFT, through lane C's adapter), for a message or an edit of one:
    - `Hidden.masked`: the masked copy, for `idea_messages.text_encrypted` and for every service and model;
    - `Hidden.spans`: `[{start, end, kind, hid}]` in the person's own text, for the dotted underline
      (L-HIDE.rules/2; `idea_messages.spans` takes start, end and kind);
    - `Hidden.details`: E-ENTITIES `HiddenDetail` for the draft panel and the `hidden` stream event;
    - `Hidden.counts`, `Hidden.hidden_count`, `Hidden.kinds_line` ("Folio number, PAN and phone number") and
      `Hidden.receipt` ("Hid 3 personal details from everyone but you: Folio ••••89, PAN ••••4F, Phone ••••10.").
    Re-running it on an edited message keeps each detail's id while its value is still there, and keeps the
    person's "Show it" for that value. Values a reviewer hid on the idea are hidden in every new text.

`preview(conn, text, *, idea_uuid=None) -> Hidden`
    Spans while the person types: patterns, names and the idea's hidden values, no model call, nothing stored.

`desk_hide`, `show`, `hide_again` (`hide/desk.py`) serve `POST /api/desk/ideas/:id/hide` and
`POST /api/drafts/:id/hidden/:hid/show|hide`. Files are `hide/files.py`.
"""

from __future__ import annotations

import uuid

from core.db import Conn
from hide.core import DETAIL_SOURCES, SEALED_SOURCES, Hidden, HideError, hide_into, preview
from hide.desk import desk_hide, hide_again, show
from hide.detect import Found, find, kinds_line, mask, receipt

__all__ = [
    "Found",
    "Hidden",
    "HideError",
    "desk_hide",
    "find",
    "hide_again",
    "hide_message",
    "hide_text",
    "kinds_line",
    "mask",
    "preview",
    "receipt",
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
