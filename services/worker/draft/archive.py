"""Drafts untouched for `kept_days` (P-PRODUCT.promises, 30) are archived, never deleted (L-DRAFT.autosave/8,
R28). BLD-C074. The person restores one from My ideas → Drafts. Daily job `drafts.archive`, which replaces
`drafts.purge` for the schedule; the purge handler stays only for a row already queued (retired, DEC-106)."""

from __future__ import annotations

from core.db import Conn
from core.logging import get_logger
from draft.config import rules

log = get_logger("draft.archive")


def archive_untouched(conn: Conn) -> int:
    rows = conn.execute(
        "UPDATE ideas SET archived_at = now() WHERE status = 'draft' AND archived_at IS NULL "
        "AND coalesce(saved_at, updated_at, created_at) < now() - make_interval(days => %s) RETURNING id",
        (rules().kept_days,),
    ).fetchall()
    log.info("drafts.archived", archived_count=len(rows))
    return len(rows)
