"""Daily scheduled jobs (§3.5). The scheduler enqueues each job once per IST day, at or after its time; the
runner executes it. Idempotent across restarts and across several workers (the dedupe key holds per day).
"""

from __future__ import annotations

import time
from datetime import datetime
from datetime import time as clock
from typing import Any
from zoneinfo import ZoneInfo

from core.db import Conn, connect
from core.logging import get_logger

log = get_logger("jobs.schedule")
IST = ZoneInfo("Asia/Kolkata")

# job type -> time of day (IST). §3.5 times where given; drafts.purge is ours.
DAILY: dict[str, clock] = {
    "reconcile": clock(2, 0),  # §3.5
    "drafts.purge": clock(3, 30),
    "comms.nudges": clock(10, 0),  # quick captures still weak on day 2 and day 7 (§3.7)
    "comms.digest": clock(10, 30),  # the weekly digest goes out on Mondays (the handler checks the day)
    "learning.run": clock(5, 30),  # §5: the handler decides which loops are due today
    "delivery.tick": clock(9, 30),  # §4.9 to §4.11: reminders and escalations
}

# job type -> (ISO weekday, time of day IST). Enqueued once per ISO week, on that day at or after that time.
WEEKLY: dict[str, tuple[int, clock]] = {
    "cluster.batch": (
        7,
        clock(22, 0),
    ),  # §3.5: Sunday 22:00; the job skips itself while `clusters.batch` is off
    "lenses.build": (1, clock(5, 0)),  # §4.14 and the §6 job table: Monday 05:00, counts only
}


# job type -> minutes. Enqueued once per slot of that many minutes.
EVERY: dict[str, int] = {
    "attachments.recheck": 15,  # files held for OCR or the gatekeeper (week 3, `attachments.deep_check`)
    "points.sync": 60,  # private points, each award once (DEC-078, BLD-130)
    "voice.sweep": 15,  # voice notes held past 24 hours or for an idea already shared (DEC-096)
    "qualify.backfill": 60,  # approved groups waiting for qualify (the job does nothing while `committee.flow` is off)
}


def enqueue_due(conn: Conn, now: datetime | None = None) -> list[str]:
    """Enqueue every daily job whose time has passed today and that has not been enqueued today, and every weekly
    job whose day and time have come this week."""
    local = (now or datetime.now(tz=IST)).astimezone(IST)
    queued = []
    for job_type, minutes in EVERY.items():
        key = f"{job_type}:{int(local.timestamp()) // (minutes * 60)}"
        row = conn.execute(
            "INSERT INTO jobs (type, dedupe_key) SELECT %s, %s "
            "WHERE NOT EXISTS (SELECT 1 FROM jobs WHERE dedupe_key = %s) RETURNING id",
            (job_type, key, key),
        ).fetchone()
        if row:
            queued.append(job_type)
    year, week, weekday = local.isocalendar()
    for job_type, (day, at) in WEEKLY.items():
        if weekday != day or local.time() < at:
            continue
        key = f"{job_type}:{year}-W{week:02d}"
        row = conn.execute(
            "INSERT INTO jobs (type, dedupe_key) SELECT %s, %s "
            "WHERE NOT EXISTS (SELECT 1 FROM jobs WHERE dedupe_key = %s) RETURNING id",
            (job_type, key, key),
        ).fetchone()
        if row:
            queued.append(job_type)
            log.info("schedule.enqueued", job_type=job_type, job_id=row["id"])
    for job_type, at in DAILY.items():
        if local.time() < at:
            continue
        key = f"{job_type}:{local.date().isoformat()}"
        row = conn.execute(
            "INSERT INTO jobs (type, dedupe_key) SELECT %s, %s "
            "WHERE NOT EXISTS (SELECT 1 FROM jobs WHERE dedupe_key = %s) RETURNING id",
            (job_type, key, key),
        ).fetchone()
        if row:
            queued.append(job_type)
            log.info("schedule.enqueued", job_type=job_type, job_id=row["id"])
    return queued


def run_forever(stop: Any = None, poll_seconds: float = 60.0) -> None:
    log.info("schedule.started", job_types=sorted([*DAILY, *WEEKLY, *EVERY]))
    with connect(autocommit=True) as conn:
        while stop is None or not stop.is_set():
            enqueue_due(conn)
            time.sleep(poll_seconds)
