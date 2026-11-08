"""Claim and run jobs. Handlers register by type; failures retry with backoff, then go `dead`.

Payloads hold IDs only, and `last_error` holds an error code (the column enforces it).
"""

from __future__ import annotations

import socket
import time
from collections.abc import Callable
from typing import Any

from psycopg.types.json import Jsonb

from core.db import Conn, connect
from core.logging import get_logger

log = get_logger("jobs")

Handler = Callable[[Conn, dict[str, Any]], None]
HANDLERS: dict[str, Handler] = {}
DEAD_HANDLERS: dict[str, Handler] = {}  # run once when a job of that type goes dead, to tell people
BACKOFF_MINUTES = (1, 5, 15, 60)


def handler(job_type: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        HANDLERS[job_type] = fn
        return fn

    return register


def on_dead(job_type: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        DEAD_HANDLERS[job_type] = fn
        return fn

    return register


def enqueue(
    conn: Conn, job_type: str, payload: dict[str, Any], *, dedupe_key: str | None = None
) -> int | None:
    row = conn.execute(
        "INSERT INTO jobs (type, payload, dedupe_key) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING RETURNING id",
        (job_type, Jsonb(payload), dedupe_key),
    ).fetchone()
    return int(row["id"]) if row else None


def run_one(conn: Conn, worker_id: str) -> bool:
    """Claim the next due job and run it. Returns False when nothing is due."""
    with conn.transaction():
        # Only types this worker can run: a job for a later block waits instead of failing.
        job = conn.execute(
            "SELECT id, type, payload, attempts, max_attempts FROM jobs WHERE state = 'queued' AND run_at <= now() "
            "AND type = ANY(%s) ORDER BY run_at, id LIMIT 1 FOR UPDATE SKIP LOCKED",
            (sorted(HANDLERS),),
        ).fetchone()
        if job is None:
            return False
        conn.execute(
            "UPDATE jobs SET state = 'running', locked_by = %s, locked_at = now(), attempts = attempts + 1 WHERE id = %s",
            (worker_id, job["id"]),
        )
    fn = HANDLERS.get(job["type"])
    try:
        if fn is None:
            raise LookupError("no_handler")
        fn(conn, job["payload"])
    except Exception as exc:
        attempts = job["attempts"] + 1
        dead = attempts >= job["max_attempts"]
        delay = BACKOFF_MINUTES[min(attempts - 1, len(BACKOFF_MINUTES) - 1)]
        code = str(exc) if isinstance(exc, LookupError) else type(exc).__name__
        conn.execute(
            "UPDATE jobs SET state = %s, run_at = now() + make_interval(mins => %s), last_error = %s, locked_by = NULL "
            "WHERE id = %s",
            ("dead" if dead else "queued", delay, code[:120], job["id"]),
        )
        log.error("jobs.failed", job_id=job["id"], job_type=job["type"], error_code=code[:120], dead=dead)
        if dead and job["type"] in DEAD_HANDLERS:
            try:
                DEAD_HANDLERS[job["type"]](conn, job["payload"])
            except Exception as dead_exc:
                log.error("jobs.dead_handler_failed", job_id=job["id"], error_type=type(dead_exc).__name__)
        return True
    conn.execute(
        "UPDATE jobs SET state = 'done', locked_by = NULL, last_error = NULL WHERE id = %s", (job["id"],)
    )
    return True


STALE_AFTER = "10 minutes"


def reap_stale(conn: Conn) -> int:
    """Jobs left `running` by a worker that died mid-job go back to the queue (attempts are kept)."""
    n = conn.execute(
        "UPDATE jobs SET state = 'queued', locked_by = NULL WHERE state = 'running' "
        "AND locked_at < now() - %s::interval",
        (STALE_AFTER,),
    ).rowcount
    if n:
        log.warning("jobs.reaped", job_count=n)
    return n


def run_forever(stop: Any = None, poll_seconds: float = 1.0) -> None:
    worker_id = f"{socket.gethostname()}:{id(stop)}"
    log.info("jobs.started", job_types=sorted(HANDLERS))
    with connect(autocommit=True) as conn:
        last_reap = 0.0
        while stop is None or not stop.is_set():
            if time.monotonic() - last_reap > 60:
                reap_stale(conn)
                last_reap = time.monotonic()
            if not run_one(conn, worker_id):
                time.sleep(poll_seconds)
