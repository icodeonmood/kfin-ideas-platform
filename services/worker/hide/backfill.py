"""The names backfill (BLD-C252; DEC-142, the product lead's choice of 27 Nov, option B): a one-off pass, with no model
call, that hides in texts written before r7 the names r7's rules now find, a known given name and surname typed in
lower case (BLD-C251) and a name written in Devanagari (BLD-C247), each beside another hidden detail in its sentence
(L-HIDE.detect, DEC-103).

- Queued once when the worker starts (`queue_once`, from `service/__main__.py`), under the dedupe key
  `hide.names_backfill`, and never again once a full run has finished: its audit row `hide.names_backfilled` on
  `job:hide.names_backfill`. A run limited to some ideas (`payload["ideas"]`, for tests) audits on
  `job:hide.names_backfill:ideas` and does not count.
- Runs `core._hide` on every sealed text (`idea_words_sealed`, the person's own words, worker only) with the
  gatekeeper left out and without sealing again: no model call, whatever `ai.all` says, and `gatekeeper_done_at` stays
  as it was, so the gatekeeper's re-check of the texts written while the assistant was off (BLD-C231) still runs once
  it is on. It only adds (`add_only`): a detail not found again (the gatekeeper's, which it does not ask; one the
  person chose to show) stays as it was.
- Then, as that re-check does (`recheck.settle`), the text's masked copy is rebuilt and each new detail is masked in
  every other copy of the idea.
- One text at a time, each in its own transaction: the same hide locks as the re-check, then the words read again
  under them, so an edit made meanwhile is the one hidden. A text or idea removed since is skipped, and so is an
  idea hiding refuses (`HideError`, which rolls that text back).
- A sealed row's key is turned back into its caller's source id (`caller_id`) before anything reads by it, as the
  re-check sweep does: a team-up decline reason or a draft's ask is kept under the idea's uuid.
- Logs and audits counts only: texts read, new details, other copies changed. Safe to run again: a detail hidden
  before is found again with its own vault tag and is not new, so a second run changes nothing.
"""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from core.db import Conn
from core.logging import get_logger
from hide import core, recheck
from hide.core import SEALED_SOURCES, HideError, _hide, caller_id, details_for, is_uuid, own_words

log = get_logger("hide")

JOB = "hide.names_backfill"
DONE = "hide.names_backfilled"  # the audit row that says it has finished
ACTOR = "system:hide"
ENTITY = f"job:{JOB}"  # a full run's audit row; a run limited to some ideas audits on SOME
SOME = f"{ENTITY}:ideas"


def queue_once(conn: Conn) -> int | None:
    """Queue the backfill unless a full run has finished before, or it is queued or running already (the jobs'
    dedupe index). Returns the job's id, or None when nothing was queued."""
    if conn.execute(
        "SELECT 1 FROM audit_log WHERE action = %s AND entity = %s LIMIT 1", (DONE, ENTITY)
    ).fetchone():
        return None
    from jobs.runner import enqueue

    return enqueue(conn, JOB, {}, dedupe_key=JOB)


def run(conn: Conn, payload: dict[str, Any]) -> dict[str, int]:
    """Every sealed text, oldest first; `payload["ideas"]`, when given, limits it to those ideas (the worker queues
    `{}`: all of them). Returns the counts it audits."""
    only = [str(i) for i in payload.get("ideas") or [] if is_uuid(str(i))]
    rows = conn.execute(
        "SELECT idea_uuid, source, source_id, owner_user_id FROM idea_words_sealed "
        "WHERE source = ANY(%s) AND (cardinality(%s::uuid[]) = 0 OR idea_uuid = ANY(%s::uuid[])) "
        "ORDER BY created_at, idea_uuid, source, source_id",
        (list(SEALED_SOURCES), only, only),
    ).fetchall()
    texts = details = copies = 0
    for r in rows:
        idea_uuid, source = str(r["idea_uuid"]), str(r["source"])
        source_id = caller_id(idea_uuid, source, str(r["source_id"])) if is_uuid(idea_uuid) else ""
        done = _one(conn, idea_uuid, source, source_id, str(r["owner_user_id"]))
        if done is None:
            continue
        texts += 1
        details += done[0]
        copies += done[1]
    counts = {"texts": texts, "details": details, "other_copies": copies}
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, %s, %s, %s)",
        (ACTOR, DONE, SOME if only else ENTITY, Jsonb(counts)),
    )
    log.info("hide.names_backfilled", text_count=texts, hidden_count=details, other_copies=copies)
    return counts


def _one(conn: Conn, idea_uuid: str, source: str, source_id: str, owner: str) -> tuple[int, int] | None:
    """One sealed text, as `recheck.run` handles it but with the gatekeeper left out, adding only. `source_id` is the
    caller's (`caller_id`). None when it was skipped."""
    if (
        not is_uuid(idea_uuid)
        or not source_id
        or conn.execute("SELECT 1 FROM ideas WHERE id = %s", (idea_uuid,)).fetchone() is None
    ):
        return None
    keys = sorted({idea_uuid.lower(), *recheck._also_locked(conn, idea_uuid, source, source_id)})
    try:
        with conn.transaction():
            for key in keys:
                core.lock(conn, key)
            # Read under the locks: `_hide` here does not seal again, so the words it places details on must be the
            # ones stored now, not the ones before an edit that took the lock first.
            words = own_words(conn, source, source_id, idea_uuid=idea_uuid)
            if words is None:
                return None  # the text was removed since
            before = {str(d["vault_tag"]) for d in details_for(conn, idea_uuid, source, source_id)}
            done, kept = _hide(
                conn,
                idea_uuid,
                words,
                by=owner,
                source=source,
                source_id=source_id,
                gatekeeper=False,
                seal=False,
                add_only=True,
            )
            return recheck.settle(conn, idea_uuid, source, source_id, words, done.masked, kept, before)
    except HideError:
        return None  # an idea hiding refuses now (gone or closed): nothing to do for it
