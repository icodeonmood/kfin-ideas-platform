"""Suggestion outcomes (DEC-122; lane C, BLD-C207 to BLD-C209): the assistant's suggestions kept beside what people
did with them, so they can be tuned or trained on later.

One row in `suggestion_outcomes`, in the caller's transaction, just before the suggestion is overwritten:

- a draft part the person sets in their own words: `pinned`, with what they kept (`draft.store.set_part`);
- a draft part the person asks the assistant to suggest again: `suggested_again`, nothing kept (`set_part`);
- a sorting field that leaves "suggested": `accepted` when confirmed as suggested, `changed` otherwise
  (`submit.sorting.apply`).

Only the assistant's own suggestions are kept: a part filled by a draft run (state `filled`, a run on it, a value)
and not pinned, and a sorting suggestion made from such a part (the kind only when the agent said it, with its quote,
BLD-C201). A value the person typed, a fallback rule (the area's kind, New business picked by hand) and anything
while the assistant is off (Capture first, DEC-125: no run fills a part) are not suggestions, so nothing is written.

The run the part points to must be one where the agent answered on that part (BLD-C250, the product lead's note of
26 Nov, item 4): its `part_ms` holds a time above 0 for it. A run that skipped the part with the assistant off, whose
answer failed or was dropped, or that never got to it, leaves 0 or nothing there while the part keeps a value from
before, so nothing is written for it.

Writing is switched off (`learning.outcomes`, migration 20261122300900) until the privacy notice names this purpose
and the product lead switches it on, and it also needs the assistant on (`ai.all` and `agent.draft-part`, BLD-C250).
The write never blocks the confirm or pin it rides on: it runs in its own savepoint, and a failure is logged and
skipped (BLD-C250). Masked text only, as stored: never the sharer's sealed words or restored tags (non-negotiable 4).
Logs carry IDs, the field and the outcome only (non-negotiable 3).
"""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from core import killswitch
from core.db import Conn
from core.logging import get_logger

log = get_logger("draft.outcomes")

SWITCH = "learning.outcomes"
AGENT = "draft-part"
ASSISTANT = ("ai.all", f"agent.{AGENT}")  # the assistant is on for drafting (as `draft.runs.ai_on` reads it)
PART_FIELDS = ("title", "summary", "often", "who", "value", "area")
SORTING_FIELDS = {
    "affects": "who",
    "area": "area",
    "brings": "value",
    "kind": "title",
}  # field: the part behind it
FIELDS = (*PART_FIELDS, *(f"sorting.{f}" for f in SORTING_FIELDS))  # the table's own check
OUTCOMES = ("accepted", "changed", "pinned", "suggested_again")
SIDES = ("sharer", "reviewer")


def writing(conn: Conn) -> bool:
    """Whether outcomes are kept now: `learning.outcomes` on (it starts off, DEC-122) and the assistant on
    (BLD-C250): nothing is kept in Capture first."""
    return killswitch.is_on(SWITCH, conn) and all(killswitch.is_on(name, conn) for name in ASSISTANT)


def part_of(field: str) -> str:
    """The `idea_parts` key behind a field: a sorting field's part, and the title row for the summary."""
    if field.startswith("sorting."):
        return SORTING_FIELDS[field.removeprefix("sorting.")]
    return "title" if field == "summary" else field


def answered(conn: Conn, run_id: str, part: str) -> bool:
    """Whether the agent answered on this part in this run (BLD-C250): the run's `part_ms` holds a time above 0 for
    it, as `draft.runs._write` records an answer that was used. 0 is a part skipped with the assistant off, failed or
    dropped; no entry is one the run never got to."""
    row = conn.execute(
        "SELECT coalesce((part_ms ->> %s)::int, 0) > 0 AS answered FROM draft_runs WHERE id = %s",
        (part, run_id),
    ).fetchone()
    return bool(row and row["answered"])


def _empty(value: Any) -> bool:
    return value is None or value in ("", [], {})


def model_part_value(row: dict[str, Any] | None, field: str) -> Any:
    """What the assistant suggested for one part field, from its `idea_parts` row before the change, or None when
    the field holds no suggestion of the assistant's (nothing built, the person's own words, a pinned field)."""
    if not row or row.get("state") != "filled" or not row.get("run_id"):
        return None
    value = row.get("value")
    if field in ("title", "summary"):
        if not isinstance(value, dict) or field in (value.get("pinned") or []):
            return None
        value = value.get(field)
    return None if _empty(value) else value


def _version() -> str:
    from gateway.spec import load

    return load(AGENT).version


def record(
    conn: Conn,
    idea_uuid: str,
    field: str,
    *,
    suggested: Any,
    final: Any,
    outcome: str,
    run_id: str | None,
    side: str = "sharer",
) -> bool:
    """Keep one suggestion and what became of it. Does nothing (False) while it is not `writing`, when there is no
    suggestion of the assistant's to keep, or when the run behind it is not one where the agent answered on that
    part. A field, outcome or side the table does not know is a caller's mistake: ValueError, before anything is
    read. Anything that fails while writing is logged and skipped, never raised, so the confirm or pin goes on."""
    if field not in FIELDS or outcome not in OUTCOMES or side not in SIDES:
        raise ValueError("unknown field, outcome or side for a suggestion outcome")
    if _empty(suggested) or not run_id or not writing(conn):
        return False
    try:
        with conn.transaction():  # a savepoint inside the caller's transaction
            if not answered(conn, run_id, part_of(field)):
                return False
            conn.execute(
                "INSERT INTO suggestion_outcomes (idea_uuid, field, suggested, final, outcome, agent, agent_version, "
                "run_id, side) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    idea_uuid,
                    field,
                    Jsonb(suggested),
                    Jsonb(final) if final is not None else None,
                    outcome,
                    AGENT,
                    _version(),
                    run_id,
                    side,
                ),
            )
    except Exception as exc:  # never blocks the person's confirm or pin (BLD-C250)
        log.warning("draft.outcome_skipped", idea_id=idea_uuid, field=field, error_code=type(exc).__name__)
        return False
    log.info("draft.outcome_kept", idea_id=idea_uuid, field=field, outcome=outcome)
    return True
