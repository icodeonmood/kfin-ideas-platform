"""Job handlers. Importing this module registers them with the runner."""

from __future__ import annotations

from typing import Any

from core.db import Conn
from core.logging import get_logger
from jobs.runner import handler

log = get_logger("jobs.handlers")


@handler("drafts.purge")
def purge_drafts(conn: Conn, payload: dict[str, Any]) -> None:
    """Delete drafts past their retention date (§4.1 step 2, AT-B3-04), and their files from the store."""
    from attachments import service

    files = conn.execute(
        "SELECT a.id FROM attachments a JOIN ideas i ON i.id = a.idea_uuid "
        "WHERE i.stage = 'draft' AND i.draft_expires_at < now()"
    ).fetchall()
    for f in files:
        service.remove(conn, f["id"])
    deleted = conn.execute("DELETE FROM ideas WHERE stage = 'draft' AND draft_expires_at < now()").rowcount
    log.info("drafts.purged", deleted_count=deleted, file_count=len(files))


@handler("attachment.process")
def process_attachment(conn: Conn, payload: dict[str, Any]) -> None:
    """Virus scan, text-layer extraction and the personal-data check (§4.2 attachments, day one)."""
    from attachments import service

    service.process(conn, str(payload["attachment_id"]))
