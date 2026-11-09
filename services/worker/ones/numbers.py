"""Jersey numbers (DEC-037, DEC-039, DEC-040, DEC-041, DEC-067).

- Numbers run 1 to 999. On induction a One gets the next number after the last one the system allocated; after
  999, the lowest free number.
- For 30 days after induction a One may swap to any free number, first come first served.
- A freed number rests for 6 months before anyone else may claim it.
- A legend number is retired for good: only the One it honours may wear it.

A number is free when no other One wears it, it is not resting for someone else, and it is no one else's legend.
The unique index on `ones.number` settles any race between two people claiming the same number at once.
"""

from __future__ import annotations

import datetime as dt

from core.db import Conn
from ones.text import OnesRefused

REST = dt.timedelta(days=183)  # six months
SWAP_WINDOW = dt.timedelta(days=30)
LOW, HIGH = 1, 999

_FREE = (
    "SELECT g FROM generate_series(%(start)s::int, %(end)s::int) AS g "
    "WHERE g NOT IN (SELECT number FROM ones WHERE number IS NOT NULL AND id <> %(one)s) "
    "AND g NOT IN (SELECT number FROM one_number_history WHERE rests_until > %(now)s AND one_id <> %(one)s) "
    "AND g NOT IN (SELECT number FROM one_legend_numbers WHERE one_id <> %(one)s) "
    "ORDER BY g LIMIT 1"
)


def is_free(conn: Conn, number: int, one_id: int, now: dt.datetime) -> bool:
    if not LOW <= number <= HIGH:
        return False
    row = conn.execute(_FREE, {"start": number, "end": number, "one": one_id, "now": now}).fetchone()
    return row is not None


def resting(conn: Conn, now: dt.datetime) -> list[dict[str, object]]:
    """Numbers resting now, with the date each one is free again (not ones a One has since taken back)."""
    rows = conn.execute(
        "SELECT h.number, max(h.rests_until) AS until FROM one_number_history h WHERE h.rests_until > %s "
        "AND h.number NOT IN (SELECT number FROM ones WHERE number IS NOT NULL) GROUP BY h.number ORDER BY h.number",
        (now,),
    ).fetchall()
    return [{"number": int(r["number"]), "until": r["until"].isoformat()} for r in rows]


def next_number(conn: Conn, one_id: int, now: dt.datetime) -> int:
    """The number the system gives on induction. Call inside the induction's transaction: it locks the counter."""
    legend = conn.execute("SELECT number FROM one_legend_numbers WHERE one_id = %s", (one_id,)).fetchone()
    if legend:
        return int(legend["number"])  # a legend's number is theirs for good
    conn.execute(
        "INSERT INTO id_counters (kind, period, last_value) VALUES ('ONE-NO', '', 0) ON CONFLICT DO NOTHING"
    )
    counter = conn.execute(
        "SELECT last_value FROM id_counters WHERE kind = 'ONE-NO' AND period = '' FOR UPDATE"
    ).fetchone()
    assert counter is not None
    start = int(counter["last_value"]) + 1
    row = None
    if start <= HIGH:
        row = conn.execute(_FREE, {"start": start, "end": HIGH, "one": one_id, "now": now}).fetchone()
        if row:
            conn.execute(
                "UPDATE id_counters SET last_value = %s WHERE kind = 'ONE-NO' AND period = ''", (row["g"],)
            )
            return int(row["g"])
    row = conn.execute(
        _FREE, {"start": LOW, "end": HIGH, "one": one_id, "now": now}
    ).fetchone()  # past 999: lowest free
    if row is None:
        raise OnesRefused(409, "no_free_numbers")
    return int(row["g"])


def wear(conn: Conn, one_id: int, number: int, how: str, now: dt.datetime) -> None:
    """Record that a One wears a number from now on (their previous number, if any, starts resting)."""
    release(conn, one_id, now)
    conn.execute(
        "INSERT INTO one_number_history (one_id, number, how, from_at) VALUES (%s, %s, %s, %s)",
        (one_id, number, how, now),
    )


def release(conn: Conn, one_id: int, now: dt.datetime) -> None:
    """The One stops wearing their number: it rests for six months (a legend number never comes free anyway)."""
    conn.execute(
        "UPDATE one_number_history SET to_at = %s, rests_until = %s WHERE one_id = %s AND to_at IS NULL",
        (now, now + REST, one_id),
    )
