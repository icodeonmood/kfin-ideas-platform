"""The gatekeeper's re-check (L-HIDE.detect, BLD-C067).

When the gateway fails while a message, answer, conversation message or edit is hidden, the text goes on with the
patterns and names only (the person never waits on the model), `hide.gatekeeper_skipped` is audited and a
`hide.recheck` job is queued with IDs only. The job runs the gatekeeper again on the person's sealed words once the
gateway is back: what it finds is stored like any find, the text's masked copy is rebuilt (messages, answers and
conversation messages), and each new value is masked in every other copy of the idea (`desk._sweep`), which covers
an edit's masked copies in the fix, the parts and the idea's lines. While the gateway is still down the job fails
with `GatekeeperUnavailable` and the runner tries again with its backoff. While the assistant (`ai.all`) or the
gatekeeper (`agent.gatekeeper`) is switched off it waits (`JobWaits`: the try is given back, as a file's check does,
BLD-C225), so a switch-off never uses up its tries. When its last attempt fails, `gave_up` audits
`hide.recheck_gave_up` with IDs and the code only; the text stays hidden by the patterns and names.

Texts written while the assistant was off (DEC-131 (3), BLD-C231): their sealed row keeps `gatekeeper_done_at` NULL
(nothing is queued while off). Once both switches are on, the ticker's watch calls `queue_unchecked`, which keeps a
few re-checks going at a time until every sealed text has had the gatekeeper's check or given up.
"""

from __future__ import annotations

from typing import Any

from core.db import Conn
from core.logging import get_logger
from hide import core
from hide.core import (
    RECHECK_JOB,
    SEALED_SOURCES,
    _hide,
    audit,
    caller_id,
    details_for,
    is_uuid,
    own_words,
    sealed_key,
)

log = get_logger("hide")

# The job's `last_error` while it waits for the switches (a reason, not a failure), and the fallback step:
# `queue_unchecked` makes waiting re-checks due within a tick of the switch-on.
WAITING = "waiting_gatekeeper"
WAIT_S = 300
# At most this many re-checks running or due at once (BLD-C231). The jobs table has no priority, so the backlog after a
# switch-on yields to live work by size: one top-up per watch tick (about 60 s) is about 5 model calls a minute.
RECHECK_OUTSTANDING = 5
# Words still being typed (an answer's autosave) settle before the sweep asks about them.
SETTLE = "10 minutes"
# Lane B's job for the review desk's own texts (BLD-B278): queued once per tick while both switches are on, deduped,
# and only in a build that registers lane B's handler.
DESK_TEXT_RECHECK = "desk.text_recheck"


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
        from jobs.runner import JobWaits

        raise JobWaits(WAIT_S, WAITING)  # waits for the switches, its try given back (BLD-C231, as BLD-C225)
    # The model call before any lock (BLD-C234), then every hide lock this text's copies need, in uuid order and
    # before any row lock (BLD-C228): a draft's ask is also swept by the desk under its other idea's lock, so a
    # re-check holding only the draft's could write its copy over the desk's mask (BLD-C239).
    asked = core.gate(conn, idea_uuid, words, source=source)
    keys = sorted({idea_uuid.lower(), *_also_locked(conn, idea_uuid, source, source_id)})
    with conn.transaction():
        for key in keys:
            core.lock(conn, key)
        before = {str(d["vault_tag"]) for d in details_for(conn, idea_uuid, source, source_id)}
        done, kept = _hide(
            conn, idea_uuid, words, by=by, source=source, source_id=source_id, gatekeeper=True, recheck=True,
            gate=asked,
        )  # fmt: skip
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


def _also_locked(conn: Conn, idea_uuid: str, source: str, source_id: str) -> list[str]:
    """The other ideas whose hide lock guards a copy of this text (BLD-C239). A draft's ask ("<merge request id>:ask",
    lane F's `ask_id`) is kept under the draft but read, and swept by the desk's "Hide this", on the idea it was sent
    to (`desk.load_teamup`). Every other sealed text lives under its own idea only."""
    request_id, _, part = source_id.partition(":")
    if source != "teamup" or part != "ask" or not is_uuid(request_id):
        return []
    row = conn.execute(
        "SELECT other_idea_uuid FROM merge_requests WHERE id = %s AND draft_uuid = %s",
        (request_id, idea_uuid),
    ).fetchone()
    return [str(row["other_idea_uuid"]).lower()] if row and row["other_idea_uuid"] else []


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
    # The audit row is the record (BLD-C067): the sweep does not ask again about these words (BLD-C231).
    conn.execute(
        "UPDATE idea_words_sealed SET gatekeeper_done_at = now() "
        "WHERE idea_uuid = %s AND source = %s AND source_id = %s AND gatekeeper_done_at IS NULL",
        (idea_uuid, source, sealed_key(idea_uuid, source_id)),
    )
    log.info("hide.recheck_gave_up", idea_id=idea_uuid, source_code=source, error_code=code)


def _start_desk_texts(conn: Conn) -> bool:
    """Lane B's re-check of the review desk's own texts (BLD-B278), one at a time, started by the same switch-on.
    Only when this build registers its handler (the service imports `jobs.handlers` before the watch runs), so a
    build without BLD-B278 queues nothing for it. Returns whether a job was queued."""
    from jobs.runner import HANDLERS, enqueue

    if DESK_TEXT_RECHECK not in HANDLERS:
        return False
    return enqueue(conn, DESK_TEXT_RECHECK, {}, dedupe_key=DESK_TEXT_RECHECK) is not None


def queue_unchecked(conn: Conn, limit: int = RECHECK_OUTSTANDING) -> int:
    """Texts written while the assistant was off get the gatekeeper's check once it is back (DEC-131 (3), BLD-C231).
    Called on every tick of the ticker's watch; does nothing unless `ai.all` and `agent.gatekeeper` are both on.

    It tops up to `limit` re-checks running or due now: first the ones waiting for the switches (made due now), then
    new ones for sealed words with `gatekeeper_done_at` NULL that settled at least `SETTLE` ago and have no re-check
    queued, oldest first, under the same dedupe key `_gatekeeper_skipped` uses. Each re-check is one model call
    through the gateway, run by the job runner like any job. Nothing is checked here. Logs counts only. Returns how
    many it made due or queued."""
    if not _gatekeeper_on(conn):
        return 0
    from jobs.runner import enqueue

    _start_desk_texts(conn)
    busy = conn.execute(
        "SELECT count(*) AS n FROM jobs WHERE type = %s AND (state = 'running' OR (state = 'queued' AND run_at <= now()))",
        (RECHECK_JOB,),
    ).fetchone()  # fmt: skip
    room = limit - int(busy["n"] if busy else 0)
    if room <= 0:
        return 0
    with conn.transaction():  # the batch picked once (a MATERIALIZED CTE, BLD-C238)
        requeued = conn.execute(
            "WITH due AS MATERIALIZED (SELECT id FROM jobs WHERE type = %s AND state = 'queued' AND last_error = %s "
            "AND run_at > now() ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED) "
            "UPDATE jobs SET run_at = now() FROM due WHERE jobs.id = due.id",
            (RECHECK_JOB, WAITING, room),
        ).rowcount
    room -= requeued
    queued = 0
    if room > 0:
        rows = conn.execute(
            "SELECT w.idea_uuid, w.source, w.source_id, w.owner_user_id FROM idea_words_sealed w "
            "WHERE w.gatekeeper_done_at IS NULL AND w.updated_at < now() - %s::interval "
            "AND NOT EXISTS (SELECT 1 FROM jobs j WHERE j.dedupe_key = %s || w.idea_uuid::text || ':' || w.source "
            "|| ':' || w.source_id AND j.state IN ('queued', 'running')) ORDER BY w.id LIMIT %s",
            (SETTLE, f"{RECHECK_JOB}:", room),
        ).fetchall()
        for r in rows:
            idea_uuid, source, key = str(r["idea_uuid"]), str(r["source"]), str(r["source_id"])
            payload = {
                "idea_uuid": idea_uuid,
                "source": source,
                "source_id": caller_id(idea_uuid, source, key),
                "by": str(r["owner_user_id"]),
            }
            if enqueue(conn, RECHECK_JOB, payload, dedupe_key=f"{RECHECK_JOB}:{idea_uuid}:{source}:{key}"):
                queued += 1
    if requeued or queued:
        log.info("hide.recheck_swept", requeued_count=requeued, queued_count=queued)
    return requeued + queued
