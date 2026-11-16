"""Every clock on the review side that changes something when it runs out, as one idempotent sweep.

Lane A's engine owns the schedule; it calls `run_due` every few minutes (or on each of lane B's timer kinds,
which all lead here). Running it twice, late or early changes nothing it should not:

- Not now comes back to "To review" on its return date (L-DECIDE.rules/7);
- a committee window that reached its end is recorded as expired (L-COMMITTEE.rules/6);
- the sharer is reminded 1 day and 2 hours before an answer is due (L-QUESTIONS.clock/2).

Screens never wait for it: windows and countdowns are worked out on read, and the desk runs the Not now returns
itself before it lists (`return_due`).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from core.db import Conn
from desk.store import now

SWEEP_LOCK = 0x1C1B0001  # pg advisory lock key for the review side's sweep (lane B)


def return_due(conn: Conn, at: dt.datetime | None = None) -> int:
    """Bring back every Not now whose return date has come. Returns how many came back."""
    from desk.decide import return_from_not_now

    t = at or now()
    due = conn.execute(
        "SELECT i.id FROM ideas i WHERE i.status = 'not_now' AND EXISTS ("
        "  SELECT 1 FROM idea_decisions d JOIN decision_windows w ON w.decision_id = d.id"
        "  LEFT JOIN decision_reversals r ON r.window_id = w.id"
        "  WHERE d.idea_uuid = i.id AND coalesce(r.return_at, d.return_at) <= %s)",
        (t,),
    ).fetchall()
    return sum(1 for r in due if return_from_not_now(conn, str(r["id"]), t))


def run_due(conn: Conn, at: dt.datetime | None = None) -> dict[str, Any]:
    """The sweep. Returns counts only. Two runs never overlap: a second one returns zeros at once."""
    t = at or now()
    with conn.transaction():  # one sweep at a time: a slow run and the next tick never overlap
        held = conn.execute("SELECT pg_try_advisory_xact_lock(%s) AS got", (SWEEP_LOCK,)).fetchone()
        if held is None or not held["got"]:
            return {"returned": 0, "windows_closed": 0, "reminded": 0}
        return _sweep(conn, t)


def _sweep(conn: Conn, t: dt.datetime) -> dict[str, Any]:
    from desk import asking, committee, promises

    returned = return_due(conn, t)
    closed = sum(
        1
        for r in conn.execute(
            "SELECT id FROM decision_windows WHERE state IN ('open', 'extended') AND closes_at <= %s", (t,)
        ).fetchall()
        if committee.close_window(conn, str(r["id"]), t)
    )
    lead = dt.timedelta(hours=max(promises.get().reminders_before_hours, default=24))
    reminded = sum(
        1
        for r in conn.execute(
            "SELECT id FROM question_sets WHERE state IN ('sent', 'seen', 'partly_answered') "
            "AND due_at > %s AND due_at - %s <= %s",
            (t, lead, t),
        ).fetchall()
        if asking.remind_due(conn, str(r["id"]), t)
    )
    return {"returned": returned, "windows_closed": closed, "reminded": reminded}
