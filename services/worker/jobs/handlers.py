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
    from voice import service as voice_service

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
            voice_service.drop_for_ideas(
                conn, [str(c["id"])], "draft_purged"
            )  # first: the FK restricts (BLD-C006)
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


@handler("comms.route")
def comms_route(conn: Conn, payload: dict[str, Any]) -> None:
    """Turn an event into notifications (§3.7 steps 2–3, 6)."""
    from comms.route import route

    route(conn, str(payload["event"]), dict(payload.get("refs") or {}))


@handler("comms.nudges")
def comms_nudges(conn: Conn, payload: dict[str, Any]) -> None:
    """Quick captures still below strength 3 on day 2 and day 7 after submit get the most useful additions. An
    idea the assistant has no addition for gets no nudge: there would be nothing to ask for (BLD-157)."""
    from comms.route import emit

    rows = conn.execute(
        "SELECT idea_id FROM ideas WHERE capture_mode = 'quick' AND coalesce(strength, 0) < 3 "
        "AND stage NOT IN ('draft', 'withdrawn', 'blocked', 'redirected') "
        "AND canvas #> '{strength,next_best,0}' IS NOT NULL "
        "AND ((now() AT TIME ZONE 'Asia/Kolkata')::date - (submitted_at AT TIME ZONE 'Asia/Kolkata')::date) IN (2, 7)"
    ).fetchall()
    for r in rows:
        emit(conn, "canvas.nudge", {"idea_id": r["idea_id"]})
    log.info("comms.nudges_queued", idea_count=len(rows))


@handler("comms.digest")
def comms_digest(conn: Conn, payload: dict[str, Any]) -> None:
    import datetime as dt
    from zoneinfo import ZoneInfo

    from comms.send import send_digests

    if dt.datetime.now(ZoneInfo("Asia/Kolkata")).weekday() == 0 or payload.get("force"):
        send_digests(conn)


@handler("reconcile")
def reconcile_job(conn: Conn, payload: dict[str, Any]) -> None:
    """Nightly: compare the company repo with the read model, fix the index, log the drift (§3.5)."""
    from reconcile import run

    run()


@handler("cluster.batch")
def cluster_batch(conn: Conn, payload: dict[str, Any]) -> None:
    """The weekly clustering run (§4.4 B); proposals only. Skips itself while `clusters.batch` is off."""
    from cluster.batch import run_batch

    run_batch(conn, manual_by=payload.get("manual_by"))


@handler("attachment.digest")
def attachment_digest(conn: Conn, payload: dict[str, Any]) -> None:
    """attachment-digest and the file text in the index, once the idea is submitted (§4.2 attachments step 6)."""
    from attachments import service

    service.digest(conn, str(payload["attachment_id"]))


@handler("attachments.recheck")
def attachments_recheck(conn: Conn, payload: dict[str, Any]) -> None:
    """Files held for OCR or the gatekeeper go back through the checks while `attachments.deep_check` is on."""
    from attachments import service

    log.info("attachments.recheck_queued", file_count=service.recheck(conn))


@handler("delivery.tick")
def delivery_tick(conn: Conn, payload: dict[str, Any]) -> None:
    """Daily: measurement reminders, fix-track check-ins, overdue milestones and blocked work (§4.9 to §4.11)."""
    from delivery.jobs import tick

    tick(conn)


@handler("points.sync")
def points_sync(conn: Conn, payload: dict[str, Any]) -> None:
    """Hourly: turn what has happened into private points, each award once (DEC-078, BLD-130)."""
    from points.ledger import sync

    sync(conn)


@handler("lenses.build")
def lenses_build(conn: Conn, payload: dict[str, Any]) -> None:
    """Weekly on Mondays (or on request): the LOB and role lenses, counts only (§4.14)."""
    from lenses import build

    build(conn)


@handler("learning.run")
def learning_run(conn: Conn, payload: dict[str, Any]) -> None:
    """Daily: whichever learning loops are due today (§5); nothing while `learning.jobs` is off."""
    from learning.run import run

    run(conn)


@handler("qualify.start")
def qualify_start(conn: Conn, payload: dict[str, Any]) -> None:
    """The qualify item for a newly approved group (§4.5 trigger), after the approval has committed."""
    from committee import qualify

    qualify.start_job(conn, str(payload["cluster_id"]))


@handler("qualify.backfill")
def qualify_backfill(conn: Conn, payload: dict[str, Any]) -> None:
    """Approved groups still waiting for qualify, once `committee.flow` is on."""
    from committee import qualify

    log.info("qualify.backfill_done", cluster_count=qualify.backfill(conn))


@handler("round.prescore")
def round_prescore(conn: Conn, payload: dict[str, Any]) -> None:
    """`prescore` for a newly opened round, outside the cycle's transaction."""
    from committee import rounds

    rounds.prescore_round(conn, str(payload["round_id"]))


@handler("presentation.outline")
def presentation_outline(conn: Conn, payload: dict[str, Any]) -> None:
    """The `pitch-prep` outline for a new invitation, outside the shortlist's transaction."""
    from committee import decide

    decide.write_outline(conn, str(payload["presentation_id"]))


@handler("voice.transcribe")
def voice_transcribe(conn: Conn, payload: dict[str, Any]) -> None:
    """Virus scan, then speech to text, spoken numbers to digits and blocked values left out (DEC-096)."""
    from voice import service

    service.transcribe(conn, str(payload["voice_note_id"]))


@on_dead("voice.transcribe")
def voice_gave_up(conn: Conn, payload: dict[str, Any]) -> None:
    from voice import service

    service.give_up(conn, str(payload["voice_note_id"]))


@handler("voice.purge")
def voice_purge(conn: Conn, payload: dict[str, Any]) -> None:
    """An idea was shared: delete its recordings and any text still held for it at once (DEC-096)."""
    from voice import service

    service.purge_idea(conn, str(payload["idea_uuid"]), "shared")


@handler("voice.sweep")
def voice_sweep(conn: Conn, payload: dict[str, Any]) -> None:
    """Every 15 minutes: anything held past 24 hours, or for an idea no longer a draft (DEC-096)."""
    from voice import service

    service.sweep(conn)


@handler("desk.clocks")
def desk_clocks(conn: Conn, payload: dict[str, Any]) -> None:
    """Every 5 minutes: lane B's clock sweep; idempotent under its own advisory lock."""
    from desk.clocks import run_due

    run_due(conn)


@handler("impact.sweep")
def impact_sweep(conn: Conn, payload: dict[str, Any]) -> None:
    """Hourly: a measurement that has fallen due and is not entered gets one "Needs you" item for the build team
    and the admins (L-IMPACT, J-ONE steps 2 and 6). A sweep over the table, not an sla timer."""
    from programme.impact import sweep

    log.info("impact.sweep_done", measurement_count=sweep(conn))
