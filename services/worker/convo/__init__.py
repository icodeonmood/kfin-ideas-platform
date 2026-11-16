"""L-CONVO: an idea's one conversation (lane F; SHIP_PLAN_1PC §5a).

`post` is the cross-lane entry point: every lane that puts a line in an idea's conversation calls it, inside its own
transaction, so the line exists exactly when the change that caused it does. The arguments are those of lane B's
`desk/adapters.say`, so lane B and builder F1 switch to it by one line.

What goes in is a code and IDs: `event` is a dotted code (`desk.opened`, `crew.joined`), `payload` holds IDs, enums,
numbers and booleans only (non-negotiable 3). Lane F turns the code into the words of
`1pc-handoff/reference/copy/Messages.md` when the conversation is read (`convo.render`), with names resolved then, so
a renamed or erased person reads right everywhere. A new code needs a line in `convo.render`: send it to lane F.

People's messages do not come through here: they are written by `convo.messages.send`, which masks and seals them.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping

from psycopg.types.json import Jsonb

from core.db import Conn

Ref = str | int | bool | None

EVENT_CODE = re.compile(r"^[a-z_]+(\.[a-z_]+)*$")  # conversation_entries.event's CHECK
ENTRY_TYPES = frozenset({"event", "message", "questions", "answers"})  # E-ENUMS conversation_type


class ConvoError(ValueError):
    """A call that breaks the entry point's contract (a caller's bug, never a person's input)."""


def post(
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
) -> str:
    """Put a line in the idea's conversation and return the entry's id (L-CONVO/3, /4).

    - `idea_uuid`: `ideas.id`.
    - `event`: the dotted code the line is rendered from at read time.
    - `author_user_id` (staff, a `users.id`) or `author_code` (a contributor code, `CTR-…`): who did it; both
      optional for a system line.
    - `payload`: IDs, enums, numbers and booleans only, never text.
    - `question_set_id`, `entry_type`: a question set (`"questions"`) or its answers (`"answers"`) appear by
      reference to the set.
    - `at`: when it happened; now by default.
    """
    if not EVENT_CODE.match(event):
        raise ConvoError("event must be a dotted lower-case code")
    if entry_type not in ENTRY_TYPES or entry_type == "message":
        raise ConvoError("entry_type is event, questions or answers; messages go through convo.messages")
    if entry_type in ("questions", "answers") and not question_set_id:
        raise ConvoError("questions and answers entries need question_set_id")
    body = dict(payload or {})
    for key, value in body.items():
        if not isinstance(value, str | int | bool) and value is not None:
            raise ConvoError(f"payload {key!r} must be an ID, enum, number or boolean")
    row = conn.execute(
        "INSERT INTO conversation_entries (idea_uuid, type, event, payload, author_user_id, author_code, "
        "question_set_id, at) VALUES (%s, %s, %s, %s, %s, %s, %s, coalesce(%s, now())) RETURNING id",
        (idea_uuid, entry_type, event, Jsonb(body), author_user_id, author_code, question_set_id, at),
    ).fetchone()
    assert row is not None
    return str(row["id"])


__all__ = ["ConvoError", "Ref", "post"]
