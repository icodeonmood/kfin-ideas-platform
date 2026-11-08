"""Worker entry point: `python -m service`. Runs the roles listed in WORKER_ROLES as threads.

If any role stops unexpectedly the whole process exits, so the container restarts in a clean state.
"""

from __future__ import annotations

import os
import threading
import time

import uvicorn

from attachments.store import ensure_buckets
from core.config import get_settings
from core.logging import get_logger
from index.indexer import Indexer
from jobs import handlers as _handlers  # noqa: F401 - registers job handlers
from jobs import runner as jobs
from jobs import schedule
from repo_writer.writer import RepoWriter

log = get_logger("service")


def _guard(name: str, target: object) -> threading.Thread:
    def run() -> None:
        try:
            target()  # type: ignore[operator]
        except Exception:
            log.exception("service.role_crashed", role=name)
        finally:
            os._exit(1)

    t = threading.Thread(target=run, name=name, daemon=True)
    t.start()
    return t


def ticker(poll_seconds: float = 20.0) -> None:
    """Send email that has come due and, every minute, check time limits (reminders, breaches, escalations,
    §3.6) and the automatic switch-offs for the scanner and email bounces (§7.6)."""
    from comms.send import send_due
    from core.db import connect
    from core.watch import Watch
    from sla.engine import tick

    last_sla = 0.0
    watch = Watch()
    with connect(autocommit=True) as conn:
        while True:
            send_due(conn)
            if time.monotonic() - last_sla >= 60:
                tick(conn)
                watch.run(conn)  # scanner and bounce switch-offs (§7.6)
                last_sla = time.monotonic()
            time.sleep(poll_seconds)


def main() -> None:
    settings = get_settings()
    roles = settings.roles
    log.info("service.starting", roles=sorted(roles))
    if "api" in roles:
        ensure_buckets()
    if "repo_writer" in roles:
        _guard("repo_writer", RepoWriter(settings).run_forever)
    if "indexer" in roles:
        _guard("indexer", Indexer(settings).run_forever)
    if "jobs" in roles:
        # Load the name model before the first scan: a cold load can take longer than the scan's whole budget.
        from pii.detect import warm_up

        started = time.monotonic()
        warm_up()
        log.info("service.ner_ready", duration_ms=int((time.monotonic() - started) * 1000))
        _guard("jobs", jobs.run_forever)
    if "scheduler" in roles:
        _guard("scheduler", schedule.run_forever)
    if "ticker" in roles:
        _guard("ticker", ticker)
    if "api" in roles:
        uvicorn.run(
            "api.app:app",
            host="0.0.0.0",  # noqa: S104 - inside the container network
            port=settings.worker_port,
            access_log=False,  # request lines can carry IDs in paths; we log our own events
            log_config=None,
        )
    else:
        threading.Event().wait()


main()
