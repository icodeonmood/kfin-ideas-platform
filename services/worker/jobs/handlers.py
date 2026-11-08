"""Job handlers. Importing this module registers them with the runner."""

from __future__ import annotations

import time
from typing import Any

from psycopg.types.json import Jsonb

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


@handler("scan.run")
def scan_run(conn: Conn, payload: dict[str, Any]) -> None:
    """The scan straight after submit (§4.2); falls back to `scan.async` on any failure."""
    from scan import pipeline

    pipeline.run(conn, str(payload["idea_uuid"]), mode="sync")


@handler("scan.async")
def scan_async(conn: Conn, payload: dict[str, Any]) -> None:
    """Retry a scan (1, 5, 15, 60 minutes). While `ai.all` or the agent is off, wait without using a retry."""
    from gateway import AgentSwitchedOff
    from scan import pipeline

    idea_uuid = str(payload["idea_uuid"])
    try:
        pipeline.run(conn, idea_uuid, mode="async")
    except AgentSwitchedOff:
        conn.execute(
            "INSERT INTO jobs (type, payload, run_at, dedupe_key) VALUES ('scan.async', %s, "
            "now() + interval '5 minutes', %s) ON CONFLICT DO NOTHING",
            (Jsonb({"idea_uuid": idea_uuid}), f"scan-async:{idea_uuid}:switched-off:{int(time.time())}"),
        )


@on_dead("scan.async")
def scan_gave_up(conn: Conn, payload: dict[str, Any]) -> None:
    from scan import pipeline

    pipeline.give_up(conn, str(payload["idea_uuid"]))


@on_dead("scan.run")
def scan_run_gave_up(conn: Conn, payload: dict[str, Any]) -> None:
    """The sync scan job itself kept failing: hand the idea to the async schedule (then the desk)."""
    from scan import pipeline

    idea_uuid = str(payload["idea_uuid"])
    row = conn.execute("SELECT state FROM scans WHERE idea_uuid = %s", (idea_uuid,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO scans (idea_uuid) VALUES (%s) ON CONFLICT DO NOTHING", (idea_uuid,))
    if row is None or row["state"] in ("queued", "running"):
        pipeline.go_async(conn, idea_uuid, "scan_job_dead")


@handler("vault.purge_scope")
def vault_purge_scope(conn: Conn, payload: dict[str, Any]) -> None:
    """An idea went back to edit after a block: drop the values held for it (re-tagged on the next submit)."""
    from pii import vault

    vault.purge_scope(conn, str(payload["scope_id"]))
