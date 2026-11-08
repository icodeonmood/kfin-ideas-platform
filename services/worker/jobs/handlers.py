"""Job handlers. Importing this module registers them with the runner."""

from __future__ import annotations

from typing import Any

from core.db import Conn
from core.logging import get_logger
from jobs.runner import handler, on_dead

log = get_logger("jobs.handlers")


@handler("drafts.purge")
def purge_drafts(conn: Conn, payload: dict[str, Any]) -> None:
    """Delete drafts past their retention date (§4.1 step 2, AT-B3-04), and their files from the store.
    Each draft is locked and its expiry re-checked, so a save that just extended it keeps its files."""
    from attachments import service

    candidates = conn.execute(
        "SELECT id FROM ideas WHERE stage = 'draft' AND draft_expires_at < now()"
    ).fetchall()
    deleted = files = 0
    for c in candidates:
        with conn.transaction():
            live = conn.execute(
                "SELECT id FROM ideas WHERE id = %s AND stage = 'draft' AND draft_expires_at < now() FOR UPDATE",
                (c["id"],),
            ).fetchone()
            if live is None:
                continue
            for f in conn.execute("SELECT id FROM attachments WHERE idea_uuid = %s", (c["id"],)).fetchall():
                service.remove(conn, f["id"])
                files += 1
            conn.execute("DELETE FROM ideas WHERE id = %s", (c["id"],))
            deleted += 1
    log.info("drafts.purged", deleted_count=deleted, file_count=files)


@handler("attachment.process")
def process_attachment(conn: Conn, payload: dict[str, Any]) -> None:
    """Virus scan, text-layer extraction and the personal-data check (§4.2 attachments, day one)."""
    from attachments import service

    service.process(conn, str(payload["attachment_id"]))


@on_dead("attachment.process")
def attachment_gave_up(conn: Conn, payload: dict[str, Any]) -> None:
    from attachments import service

    service.give_up(conn, str(payload["attachment_id"]))
