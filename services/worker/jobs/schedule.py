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
    "drafts.purge": clock(3, 30),
}


def enqueue_due(conn: Conn, now: datetime | None = None) -> list[str]:
    """Enqueue every daily job whose time has passed today and that has not been enqueued today."""
    local = (now or datetime.now(tz=IST)).astimezone(IST)
    queued = []
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
    log.info("schedule.started", job_types=sorted(DAILY))
    with connect(autocommit=True) as conn:
        while stop is None or not stop.is_set():
            enqueue_due(conn)
            time.sleep(poll_seconds)
