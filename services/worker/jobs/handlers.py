"""Job handlers. Importing this module registers them with the runner."""

from __future__ import annotations

from typing import Any

from core.db import Conn
from core.logging import get_logger
from jobs.runner import handler

log = get_logger("jobs.handlers")


@handler("drafts.purge")
def purge_drafts(conn: Conn, payload: dict[str, Any]) -> None:
    """Delete drafts past their retention date (§4.1 step 2, AT-B3-04). Their attachment rows cascade; the
    files in the store are removed by attachments.purge (B3 part 4)."""
    deleted = conn.execute("DELETE FROM ideas WHERE stage = 'draft' AND draft_expires_at < now()").rowcount
    log.info("drafts.purged", deleted_count=deleted)
