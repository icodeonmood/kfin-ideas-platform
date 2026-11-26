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

Writing is switched off (`learning.outcomes`, migration 20261122300900) until the privacy notice names this purpose
and the product lead switches it on. Masked text only, as stored: never the sharer's sealed words or restored tags
(non-negotiable 4). Logs carry IDs, the field and the outcome only (non-negotiable 3).
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
PART_FIELDS = ("title", "summary", "often", "who", "value", "area")
SORTING_FIELDS = {
    "affects": "who",
    "area": "area",
    "brings": "value",
    "kind": "title",
}  # field: the part behind it
OUTCOMES = ("accepted", "changed", "pinned", "suggested_again")
SIDES = ("sharer", "reviewer")


def writing(conn: Conn) -> bool:
    """Whether outcomes are kept now: `learning.outcomes` on (it starts off, DEC-122)."""
    return killswitch.is_on(SWITCH, conn)


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
    """Keep one suggestion and what became of it. Does nothing (False) while the switch is off or when there is no
    suggestion of the assistant's to keep."""
    if _empty(suggested) or not writing(conn):
        return False
    assert outcome in OUTCOMES and side in SIDES
    conn.execute(
        "INSERT INTO suggestion_outcomes (idea_uuid, field, suggested, final, outcome, agent, agent_version, run_id, "
        "side) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
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
    log.info("draft.outcome_kept", idea_id=idea_uuid, field=field, outcome=outcome)
    return True
