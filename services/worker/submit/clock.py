"""The two clocks an idea starts when it is shared (L-SUBMIT.send/4, L-SUBMIT.edit/1).

- Decide-by: 5 working days after sharing (`rules/promises.md` review.decide_by_working_days), at the deadline hour
  (6 pm India time) on the last of them, with the share day counted as day 1 when it is a working day and the
  share is before the deadline hour. That is the boards' reading, and the review side's (lane B, BLD-B231): shared
  Saturday 14 November, decided by Friday 20 November. Working days follow `rules/calendar.md`.
- The edit window: until the review desk opens the idea, at the latest `edit_window.max_days` days after sharing
  (shared Saturday 14 November, open to changes until Tuesday 17 November).

The review clock runs on lane A's timer engine as kind `decide_by` (registered in `rules/sla.md`): one running
`sla_timers` row per shared idea, keyed by its reference. A restore stops the old row and starts a new one.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from core.config import get_settings
from core.db import Conn
from rules import load_rule
from sla import engine

TIMER_KIND = "decide_by"
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _calendar() -> tuple[ZoneInfo, set[int], set[dt.date]]:
    cal = load_rule(get_settings().company_repo_path, "calendar").data
    tz = ZoneInfo(str(cal.get("timezone", "Asia/Kolkata")))
    weekend = {WEEKDAYS.index(d) for d in cal.get("weekend", ["sat", "sun"])}
    holidays = {dt.date.fromisoformat(str(h["date"])) for h in cal.get("holidays") or []}
    return tz, weekend, holidays


def working_day_deadline(start: dt.datetime, n: int, hour: int) -> dt.datetime:
    """The deadline hour on the `n`th working day, counting the start day as day 1 when it is a working day and the
    start is before the deadline hour."""
    tz, weekend, holidays = _calendar()

    def working(d: dt.date) -> bool:
        return d.weekday() not in weekend and d not in holidays

    local = start.astimezone(tz)
    day = local.date()
    if not working(day) or local >= dt.datetime.combine(day, dt.time(hour), tzinfo=tz):
        day += dt.timedelta(days=1)
    counted = 0
    while True:
        if working(day):
            counted += 1
            if counted == n:
                return dt.datetime.combine(day, dt.time(hour), tzinfo=tz)
        day += dt.timedelta(days=1)


def decide_by(shared_at: dt.datetime, promises: dict[str, object]) -> dt.datetime:
    review = promises["review"]
    questions = promises["questions"]
    assert isinstance(review, dict) and isinstance(questions, dict)
    return working_day_deadline(
        shared_at, int(review["decide_by_working_days"]), int(questions["deadline_hour"])
    )


def edit_closes(shared_at: dt.datetime, promises: dict[str, object]) -> dt.datetime:
    window = promises["edit_window"]
    assert isinstance(window, dict)
    return shared_at + dt.timedelta(days=int(window["max_days"]))


def start_review_clock(conn: Conn, ref: str, started: dt.datetime, due: dt.datetime) -> None:
    """Stop any running review clock for this idea, then start one due at `due` (inside the caller's transaction)."""
    engine.stop(conn, "idea", ref, TIMER_KIND)
    conn.execute(
        "INSERT INTO sla_timers (entity_type, entity_id, stage, started_at, due_at) VALUES ('idea', %s, %s, %s, %s)",
        (ref, TIMER_KIND, started, due),
    )
