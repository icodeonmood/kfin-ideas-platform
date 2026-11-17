"""L-CONVO: an idea's one conversation (lane F; SHIP_PLAN_1PC §5a).

`post` is the cross-lane entry point: every lane that puts a line in an idea's conversation calls it, inside its own
transaction, so the line exists exactly when the change that caused it does. The arguments are those of lane B's
`desk/adapters.say`, so lane B and builder F1 switch to it by one line.

What goes in is a code and IDs: `event` is a dotted code (`desk.opened`, `crew.joined`), `payload` holds JSON scalars
only: IDs, enums, times, numbers and booleans, each string at most 64 characters (non-negotiable 3). A payload never
refuses for its shape alone, so a caller's decision is not rolled back over a timestamp or a float (NaN or infinity
is stored as None). Lane F turns the code into the words of
`1pc-handoff/reference/copy/Messages.md` when the conversation is read (`convo.render`), with names resolved then, so
a renamed or erased person reads right everywhere. A new code needs a line in `convo.render`: send it to lane F.

Order: every line is placed just after the idea's last line whenever its time would tie with it or come before it
(BLD-F013, BLD-F057). Ids are random and one transaction has one `now()`, so without this the lines one
action writes ("Ravi Nair approved…", "Kavya joined the crew.") would read back shuffled. Messages use the same rule.
The idea's conversation lock (`LOCK`, a transaction-level advisory lock) is taken before the last line's time is
read, so two writers on one idea cannot tie; it is held until the caller's transaction ends.

People's messages do not come through here: they are written by `convo.messages.send`, which masks and seals them.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Mapping

from psycopg.types.json import Jsonb

from core.db import Conn

Ref = str | int | float | bool | None

EVENT_CODE = re.compile(r"^[a-z_]+(\.[a-z_]+)*$")  # conversation_entries.event's CHECK
REF_MAX = 64  # an ID, an enum or an ISO time; longer is free text, which never goes in a payload
# One writer at a time per idea, from before the last line's time is read until the transaction ends (BLD-F057).
LOCK = "SELECT pg_advisory_xact_lock(hashtext(%s::uuid::text))"
# The entry's time is `at` (now by default), or one microsecond after the idea's last line if that is not earlier;
# `greatest` skips the NULL of an empty conversation. `convo.messages` writes the same expression (BLD-F057).
_INSERT = (
    "INSERT INTO conversation_entries (idea_uuid, type, event, payload, author_user_id, author_code, question_set_id, "
    "at) VALUES (%(idea)s, %(type)s, %(event)s, %(payload)s, %(user)s, %(code)s, %(set)s, "
    "greatest(coalesce(%(at)s, now()), (SELECT max(e.at) FROM conversation_entries e WHERE e.idea_uuid = %(idea)s) "
    "+ interval '1 microsecond')) RETURNING id"
)
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
    - `payload`: JSON scalars only (str, int, float, bool, None): IDs, enums, ISO times, numbers and booleans.
      A string over 64 characters (free text) or a nested value is refused; NaN or infinity is stored as None.
    - `question_set_id`, `entry_type`: a question set (`"questions"`) or its answers (`"answers"`) appear by
      reference to the set.
    - `at`: when it happened; now by default. A line that would tie with or come before the idea's last line is
      placed one microsecond after it, so lines read back in the order they were written (BLD-F057).
    """
    if not EVENT_CODE.match(event):
        raise ConvoError("event must be a dotted lower-case code")
    if entry_type not in ENTRY_TYPES or entry_type == "message":
        raise ConvoError("entry_type is event, questions or answers; messages go through convo.messages")
    if entry_type in ("questions", "answers") and not question_set_id:
        raise ConvoError("questions and answers entries need question_set_id")
    body = dict(payload or {})
    for key, value in body.items():
        if value is not None and not isinstance(value, str | int | float | bool):
            raise ConvoError(f"payload {key!r} must be a JSON scalar")
        if isinstance(value, float) and not math.isfinite(value):
            body[key] = None  # JSON cannot hold it; never a reason to roll the caller's decision back
        if isinstance(value, str) and len(value) > REF_MAX:
            raise ConvoError(f"payload {key!r} must be an ID, enum or time, not text")
    # A savepoint inside the caller's transaction; its own transaction on an autocommit connection, so the lock
    # always covers the read of the last line's time and the insert.
    with conn.transaction():
        conn.execute(LOCK, (idea_uuid,))
        row = conn.execute(
            _INSERT,
            {"idea": idea_uuid, "type": entry_type, "event": event, "payload": Jsonb(body), "user": author_user_id,
             "code": author_code, "set": question_set_id, "at": at},
        ).fetchone()  # fmt: skip
    assert row is not None
    return str(row["id"])


__all__ = ["LOCK", "ConvoError", "Ref", "post"]
