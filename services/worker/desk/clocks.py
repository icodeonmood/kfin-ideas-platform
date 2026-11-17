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
from collections.abc import Callable, Iterable
from typing import Any

from core.db import Conn
from core.logging import get_logger
from desk.store import now

SWEEP_LOCK = 0x1C1B0001  # pg advisory lock key for the review side's sweep (lane B)
log = get_logger("desk.clocks")


def _each(kind: str, ids: Iterable[Any], fn: Callable[[str], bool]) -> tuple[int, int]:
    """Run `fn` on every row, each in its own transaction (the handlers open one). A row that fails is logged by
    kind and ID only (non-negotiable 3) and the rest carry on. Returns (done, failed)."""
    done = failed = 0
    for row_id in ids:
        try:
            done += 1 if fn(str(row_id)) else 0
        except Exception as exc:  # one bad row never holds up the others
            failed += 1
            log.warning("desk.sweep.item_failed", kind=kind, target_id=str(row_id), error=type(exc).__name__)
    return done, failed


def _returns(conn: Conn, t: dt.datetime) -> tuple[int, int]:
    from desk.decide import return_from_not_now

    due = conn.execute(
        "SELECT i.id FROM ideas i WHERE i.status = 'not_now' AND EXISTS ("
        "  SELECT 1 FROM idea_decisions d JOIN decision_windows w ON w.decision_id = d.id"
        "  LEFT JOIN decision_reversals r ON r.window_id = w.id"
        "  WHERE d.idea_uuid = i.id AND coalesce(r.return_at, d.return_at) <= %s)",
        (t,),
    ).fetchall()
    return _each("not_now_return", (r["id"] for r in due), lambda i: return_from_not_now(conn, i, t))


def return_due(conn: Conn, at: dt.datetime | None = None) -> int:
    """Bring back every Not now whose return date has come, each in its own transaction. Returns how many came
    back; one that fails is logged and left for the next run."""
    return _returns(conn, at or now())[0]


def run_due(conn: Conn, at: dt.datetime | None = None) -> dict[str, Any]:
    """The sweep. Returns counts only. Two runs never overlap: a second one returns zeros at once.

    One sweep at a time is a session advisory lock, released in `finally`; every item then runs in its own
    transaction, so a failing item rolls back only itself and no idea lock is held while a window is locked (the
    committee's reversal takes the window, then the idea). Call it on an autocommit connection, as lane A's job
    runner and the routes do; inside an open transaction each item becomes a savepoint instead."""
    t = at or now()
    held = conn.execute("SELECT pg_try_advisory_lock(%s) AS got", (SWEEP_LOCK,)).fetchone()
    if held is None or not held["got"]:
        log.info("desk.sweep.busy")
        return {"returned": 0, "windows_closed": 0, "reminded": 0}
    try:
        return _sweep(conn, t)
    finally:
        try:
            conn.execute("SELECT pg_advisory_unlock(%s)", (SWEEP_LOCK,))
        except Exception as exc:  # the session ends the lock anyway; never hide the sweep's own outcome
            log.warning("desk.sweep.unlock_failed", error=type(exc).__name__)


def _sweep(conn: Conn, t: dt.datetime) -> dict[str, Any]:
    from desk import asking, committee, promises

    returned, failed_returns = _returns(conn, t)
    windows = conn.execute(
        "SELECT id FROM decision_windows WHERE state IN ('open', 'extended') AND closes_at <= %s", (t,)
    ).fetchall()
    closed, failed_windows = _each(
        "window_close", (r["id"] for r in windows), lambda i: committee.close_window(conn, i, t)
    )
    lead = dt.timedelta(hours=max(promises.get().reminders_before_hours, default=24))
    sets = conn.execute(
        "SELECT id FROM question_sets WHERE state IN ('sent', 'seen', 'partly_answered') "
        "AND due_at > %s AND due_at - %s <= %s",
        (t, lead, t),
    ).fetchall()
    reminded, failed_reminders = _each(
        "answer_reminder", (r["id"] for r in sets), lambda i: asking.remind_due(conn, i, t)
    )
    failed = failed_returns + failed_windows + failed_reminders
    log.info("desk.sweep", returned=returned, windows_closed=closed, reminded=reminded, failed=failed)
    return {"returned": returned, "windows_closed": closed, "reminded": reminded}
