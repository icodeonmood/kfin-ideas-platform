"""The gatekeeper's re-check (L-HIDE.detect, BLD-C067).

When the gateway fails while a message, answer, conversation message or edit is hidden, the text goes on with the
patterns and names only (the person never waits on the model), `hide.gatekeeper_skipped` is audited and a
`hide.recheck` job is queued with IDs only. The job runs the gatekeeper again on the person's sealed words once the
gateway is back: what it finds is stored like any find, the text's masked copy is rebuilt (messages, answers and
conversation messages), and each new value is masked in every other copy of the idea (`desk._sweep`), which covers
an edit's masked copies in the fix, the parts and the idea's lines. While the gateway is still down, or the assistant
(`ai.all`) or the gatekeeper (`agent.gatekeeper`) is switched off, the job fails with `GatekeeperUnavailable` and the
runner tries again with its backoff, so a job queued while the assistant was on never finishes with nothing found.
When its last attempt fails, `gave_up` audits `hide.recheck_gave_up` with IDs and the code only; the text stays
hidden by the patterns and names.
"""

from __future__ import annotations

from typing import Any

from core.db import Conn
from core.logging import get_logger
from hide.core import (
    RECHECK_JOB,
    SEALED_SOURCES,
    GatekeeperUnavailable,
    _hide,
    audit,
    details_for,
    is_uuid,
    own_words,
    sealed_key,
)

log = get_logger("hide")


def run(conn: Conn, payload: dict[str, Any]) -> None:
    from hide import desk

    idea_uuid, source = str(payload.get("idea_uuid") or ""), str(payload.get("source") or "")
    source_id, by = str(payload.get("source_id") or ""), str(payload.get("by") or "")
    if source not in SEALED_SOURCES or not is_uuid(idea_uuid) or not source_id:
        return
    if conn.execute("SELECT 1 FROM ideas WHERE id = %s", (idea_uuid,)).fetchone() is None:
        return  # the idea is gone
    words = own_words(conn, source, source_id, idea_uuid=idea_uuid)
    if words is None:
        return  # the text was removed since
    if not _gatekeeper_on(conn):
        raise GatekeeperUnavailable("ai_off")  # tried again later, never finished with nothing found
    with conn.transaction():
        before = {str(d["vault_tag"]) for d in details_for(conn, idea_uuid, source, source_id)}
        done, kept = _hide(
            conn, idea_uuid, words, by=by, source=source, source_id=source_id, gatekeeper=True, recheck=True
        )
        if source in ("message", "answer", "conversation"):
            found = desk.load_sealed(conn, idea_uuid, source, source_id)
            if found:
                desk._write_sealed(conn, idea_uuid, found[0], details_for(conn, idea_uuid, source, source_id))
        elif source == "teamup":  # a team-up note, reason or ask: lane F's writer (BLD-F097)
            from teamup.adapters import write_masked

            write_masked(conn, source_id, done.masked)
        fresh = [d for d in kept if d["found_by"] == "gatekeeper" and str(d["vault_tag"]) not in before]
        copies = 0
        for d in fresh:
            value = words[int(d["span_start"]) : int(d["span_end"])]
            copies += desk._sweep(conn, idea_uuid, value, str(d["kind"]), found_by="gatekeeper").copies
    log.info(
        "hide.rechecked", idea_id=idea_uuid, source_code=source, hidden_count=len(fresh), other_copies=copies
    )


def _gatekeeper_on(conn: Conn) -> bool:
    from core import killswitch

    return killswitch.is_on("ai.all", conn) and killswitch.is_on("agent.gatekeeper", conn)


def gave_up(conn: Conn, payload: dict[str, Any]) -> None:
    """The re-check's last attempt failed (the runner's `on_dead`): audit it with IDs and the code only. The code is
    `ai_off` while a switch is off, else the job's last error code."""
    idea_uuid, source = str(payload.get("idea_uuid") or ""), str(payload.get("source") or "")
    source_id = str(payload.get("source_id") or "")
    if source not in SEALED_SOURCES or not is_uuid(idea_uuid) or not source_id:
        return
    job = conn.execute(
        "SELECT id, attempts, last_error FROM jobs WHERE type = %s AND dedupe_key = %s ORDER BY id DESC LIMIT 1",
        (RECHECK_JOB, f"{RECHECK_JOB}:{idea_uuid}:{source}:{sealed_key(idea_uuid, source_id)}"),
    ).fetchone()
    code = "ai_off" if not _gatekeeper_on(conn) else str(job["last_error"] if job else "") or "gave_up"
    audit(
        conn,
        "system",
        "hide.recheck_gave_up",
        idea_uuid,
        {
            "source": source,
            "source_id": source_id,
            "code": code,
            "recheck_job": int(job["id"]) if job else None,
            "attempts": int(job["attempts"]) if job else None,
        },
    )
    log.info("hide.recheck_gave_up", idea_id=idea_uuid, source_code=source, error_code=code)
