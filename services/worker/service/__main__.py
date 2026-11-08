"""Worker entry point: `python -m service`. Runs the roles listed in WORKER_ROLES as threads.

If any role stops unexpectedly the whole process exits, so the container restarts in a clean state.
"""

from __future__ import annotations

import os
import threading

import uvicorn

from attachments.store import ensure_buckets
from core.config import get_settings
from core.logging import get_logger
from index.indexer import Indexer
from jobs import runner as jobs
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
        _guard("jobs", jobs.run_forever)
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
