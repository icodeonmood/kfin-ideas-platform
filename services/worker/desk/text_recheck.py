"""The review desk's own texts get the gatekeeper's check once the assistant is back (BLD-B278; L-HIDE.detect,
DEC-131 (3), non-negotiable 4; on lane C's BLD-C231).

The texts are the ones the desk writes and others read: a sent question, a decision reason, the committee's reversal
note, a desk merge's note and the reviewer's worth note. Each is hidden when it is written (the patterns and names,
then the gatekeeper when it is on: `adapters.hide_checked`) and only its masked copy is kept; the desk's words are not
sealed. A text whose gatekeeper check was not complete (the assistant or the gatekeeper switched off, or the gateway
failed) keeps `gatekeeper_done_at` NULL.

`run` is the job `desk.text_recheck`. Lane C's watch queues it about once a minute while `ai.all` and
`agent.gatekeeper` are both on, deduped, so at most one is queued or running. Each run asks the gatekeeper about up to
`BATCH` texts from the oldest waiting, so the backlog after a switch-on yields to live work by size:

- the gatekeeper is asked with no lock held (`hide.gate`), about the masked copy everyone else reads;
- each value it finds is hidden as the desk's "Hide this" hides one, without the Inbox notice (as `hide.recheck`
  sends none): under hide's lock on the idea, taken first (BLD-C228), in every copy of the idea (`hide.desk._sweep`,
  whose step 10 calls `sweep_value` below for the desk texts its step 5 does not reach), audited `hide.rechecked`
  with IDs and counts only;
- the text is marked done only when the gatekeeper's check of it is complete (`Gate.checked`).

While either switch is off the job waits (`JobWaits`, its try given back, as `hide.recheck` waits). A gateway failure
leaves that text NULL, counts one failed ask against it (`gatekeeper_failures`) and the run goes on with the next; the
run then fails, so the runner's backoff tries again. Nothing is marked done after a failure, except a give-up: after
`GIVE_UP_AFTER` failed asks about one text the re-check stops asking about it, marks it done and audits
`hide.recheck_gave_up` with the table, the row id and the code only, as lane C's sealed texts give up (BLD-C067), so a
text the gateway can never check costs no more model calls. The text stays hidden by the patterns and names.

`sweep_value` is lane C's step 10 of `_sweep`: one value masked, as whole words in any case, in the desk's reasons and
notes on the idea (decision reasons, reversal notes, desk merge notes with the idea on either side, the reviewer's
worth notes), each changed text with a `hidden_details` row (source "desk"). Questions are step 5's. It runs under the
lock `_sweep`'s caller took and never calls `_sweep`. Logs carry IDs and counts only (non-negotiable 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.db import Conn
from core.logging import get_logger
from desk.store import seal, unseal

log = get_logger("desk")

JOB = "desk.text_recheck"  # lane C's hide/recheck.py DESK_TEXT_RECHECK
BATCH = 5  # texts asked about per run: about five model calls a minute, as lane C's re-checks (RECHECK_OUTSTANDING)
WAITING = "waiting_gatekeeper"  # the job's reason code while a switch is off (lane C's recheck.WAITING)
WAIT_S = 300
GIVE_UP_AFTER = 5  # failed asks about one text before the re-check gives up on it (lane E, BLD-B278)


@dataclass(frozen=True)
class Text:
    """One desk text waiting for the gatekeeper: where it is kept, the idea it was hidden under, and who wrote it."""

    table: str
    row_id: str
    idea_uuid: str
    by: str


# Where each desk text is kept: (table, its sealed column). The order is the one `_unchecked` reads them in.
COLUMNS: dict[str, str] = {
    "questions": "text_encrypted",
    "idea_decisions": "reason_encrypted",
    "decision_reversals": "note_encrypted",
    "merges": "note_encrypted",
    "idea_worth": "note_encrypted",
}

# The texts still waiting: a run takes `BATCH` of the `HEAD` oldest, at random, so a text the gateway can never check
# does not hold back the ones behind it (it stays waiting; it is never marked done). A queued question is not one:
# nobody else reads it, and Send hides it again. A reversal note is hidden under the decision's idea, or a merge's
# joining idea (desk.committee); a merge note under its lead. Only the desk's merges and the reviewer's worth notes are
# the desk's words.
_UNCHECKED = (
    "SELECT 'questions' AS t, q.id::text AS id, s.idea_uuid::text AS idea, s.by_user_id::text AS writer, "
    "q.created_at AS at FROM questions q JOIN question_sets s ON s.id = q.set_id "
    "WHERE q.gatekeeper_done_at IS NULL AND s.state <> 'queued' "
    "UNION ALL SELECT 'idea_decisions', id::text, idea_uuid::text, by_user_id::text, at FROM idea_decisions "
    "WHERE gatekeeper_done_at IS NULL "
    "UNION ALL SELECT 'decision_reversals', r.id::text, coalesce(d.idea_uuid, m.merged_idea_uuid)::text, "
    "r.by_user_id::text, r.at FROM decision_reversals r JOIN decision_windows w ON w.id = r.window_id "
    "LEFT JOIN idea_decisions d ON d.id = w.decision_id LEFT JOIN merges m ON m.id = w.merge_id "
    "WHERE r.gatekeeper_done_at IS NULL "
    "UNION ALL SELECT 'merges', id::text, lead_idea_uuid::text, by_user_id::text, at FROM merges "
    "WHERE gatekeeper_done_at IS NULL AND via = 'review_desk' AND note_encrypted IS NOT NULL "
    "UNION ALL SELECT 'idea_worth', id::text, idea_uuid::text, by_user_id::text, at FROM idea_worth "
    "WHERE gatekeeper_done_at IS NULL AND by_side = 'reviewer' AND note_encrypted IS NOT NULL "
    "ORDER BY at, id LIMIT %s"
)
HEAD = 10 * BATCH


def unchecked(conn: Conn, limit: int = BATCH, head: int = HEAD) -> list[Text]:
    """Up to `limit` desk texts still waiting for the gatekeeper's check, taken at random from the `head` oldest."""
    pick = f"SELECT * FROM ({_UNCHECKED}) oldest ORDER BY random() LIMIT %s"  # noqa: S608 (fixed text)
    rows = conn.execute(pick, (head, limit)).fetchall()
    return [
        Text(str(r["t"]), str(r["id"]), str(r["idea"]), str(r["writer"] or "system"))
        for r in rows
        if r["idea"] is not None
    ]


def _read(conn: Conn, t: Text) -> str | None:
    column = COLUMNS[t.table]
    row = conn.execute(f"SELECT {column} AS blob FROM {t.table} WHERE id::text = %s", (t.row_id,)).fetchone()  # noqa: S608 (fixed names)
    return (
        unseal(row["blob"], t.table, column, t.row_id)
        if row is not None and row["blob"] is not None
        else None
    )


def _done(conn: Conn, t: Text) -> None:
    conn.execute(f"UPDATE {t.table} SET gatekeeper_done_at = now() WHERE id::text = %s", (t.row_id,))  # noqa: S608 (fixed names)


def _gatekeeper_on(conn: Conn) -> bool:
    from core import killswitch

    return killswitch.is_on("ai.all", conn) and killswitch.is_on("agent.gatekeeper", conn)


def _waits() -> Exception:
    from jobs.runner import JobWaits

    return JobWaits(WAIT_S, WAITING)


def _failed(conn: Conn, t: Text, code: str) -> bool:
    """One failed ask about this text, counted. True when that was the last one: the text is then marked done and
    `hide.recheck_gave_up` is audited with the table, the row id and the code only (never its words)."""
    from hide.core import audit

    with conn.transaction():
        row = conn.execute(
            f"UPDATE {t.table} SET gatekeeper_failures = gatekeeper_failures + 1 WHERE id::text = %s "  # noqa: S608 (fixed names)
            "RETURNING gatekeeper_failures",
            (t.row_id,),
        ).fetchone()
        if row is None or int(row["gatekeeper_failures"]) < GIVE_UP_AFTER:
            return False
        _done(conn, t)
        audit(
            conn,
            "system",
            "hide.recheck_gave_up",
            t.idea_uuid,
            {"source": "desk", "text": t.table, "source_id": t.row_id, "code": code},
        )
    log.info("desk.text_recheck_gave_up", idea_id=t.idea_uuid, text_code=t.table, error_code=code)
    return True


class RecheckFailed(Exception):
    """The gateway could not check a desk text (its texts stay waiting); the runner's backoff tries again."""


def check_one(conn: Conn, t: Text) -> int:
    """Ask the gatekeeper about one desk text and hide what it finds in every copy of the idea. Returns how many
    values it hid. Raises `JobWaits` while a switch is off, `RecheckFailed` when the gateway failed (and it was not
    this text's last try: then it gives up, `_failed`); the text is
    marked done only after a complete check."""
    import hide
    from hide import desk as hide_desk
    from hide import detect
    from hide.core import audit, lock

    if not _gatekeeper_on(conn):
        raise _waits()
    words = _read(conn, t)
    if words is None or not words.strip():
        with conn.transaction():
            _done(conn, t)  # nothing to check: the row has no words
        return 0
    g = hide.gate(
        conn, t.idea_uuid, words, source="desk"
    )  # no lock held: the model call comes first (BLD-C067)
    if g.switched_off or not _gatekeeper_on(conn):
        raise _waits()
    if not g.checked:
        code = (g.skipped or "gatekeeper_unavailable")[:120]
        if _failed(conn, t, code):
            return 0  # given up: done and audited, never asked about again
        raise RecheckFailed(code)
    masks = detect.mask_tokens(words)
    values = sorted(
        {
            (f.value, f.kind)
            for f in g.finds
            if f.value.strip()
            and not any(s < f.end and f.start < e for s, e in masks)  # not inside a mask already
        }
    )
    copies = 0
    with conn.transaction():
        lock(conn, t.idea_uuid)  # hide's lock on the idea first, before any row lock (BLD-C228)
        for value, kind in values:
            copies += hide_desk._sweep(conn, t.idea_uuid, value, kind, found_by="gatekeeper").copies
        _done(conn, t)
        if values:
            audit(
                conn,
                t.by,
                "hide.rechecked",
                t.idea_uuid,
                {
                    "source": "desk",
                    "text": t.table,
                    "source_id": t.row_id,
                    "hidden": len(values),
                    "copies": copies,
                },
            )
    log.info("desk.text_rechecked", idea_id=t.idea_uuid, text_code=t.table, hidden_count=len(values))
    return len(values)


def run(conn: Conn, payload: dict[str, Any]) -> None:
    """`desk.text_recheck` (lane C's watch queues it while both switches are on): up to `BATCH` desk texts, oldest
    first. A switch-off waits; a gateway failure on one text goes on to the next, then fails the run."""
    _ = payload  # {}: the job is the queue's head, not a text
    if not _gatekeeper_on(conn):
        raise _waits()
    failed: list[str] = []
    hidden = 0
    texts = unchecked(conn)
    for t in texts:
        try:
            hidden += check_one(conn, t)
        except RecheckFailed as exc:
            failed.append(str(exc))
    log.info("desk.text_recheck_run", text_count=len(texts), hidden_count=hidden, failed_count=len(failed))
    if failed:
        raise RecheckFailed(failed[0])


# ---- lane C's step 10 of `hide.desk._sweep` -------------------------------------------------------------------------


def _reasons_and_notes(conn: Conn, idea_uuid: str) -> list[tuple[str, str, Any]]:
    """(table, row id, sealed blob) for each desk reason or note that others read on this idea."""
    rows = conn.execute(
        "SELECT 'idea_decisions' AS t, id::text AS id, reason_encrypted AS blob FROM idea_decisions "
        "WHERE idea_uuid = %(i)s "
        "UNION ALL SELECT 'decision_reversals', r.id::text, r.note_encrypted FROM decision_reversals r "
        "JOIN decision_windows w ON w.id = r.window_id LEFT JOIN idea_decisions d ON d.id = w.decision_id "
        "LEFT JOIN merges m ON m.id = w.merge_id "
        "WHERE d.idea_uuid = %(i)s OR m.lead_idea_uuid = %(i)s OR m.merged_idea_uuid = %(i)s "
        "UNION ALL SELECT 'merges', id::text, note_encrypted FROM merges WHERE via = 'review_desk' "
        "AND note_encrypted IS NOT NULL AND (lead_idea_uuid = %(i)s OR merged_idea_uuid = %(i)s) "
        "UNION ALL SELECT 'idea_worth', id::text, note_encrypted FROM idea_worth WHERE idea_uuid = %(i)s "
        "AND by_side = 'reviewer' AND note_encrypted IS NOT NULL",
        {"i": idea_uuid},
    ).fetchall()
    return [(str(r["t"]), str(r["id"]), r["blob"]) for r in rows]


def sweep_value(conn: Conn, idea_uuid: str, value: str, kind: str, *, found_by: str) -> int:
    """`value` masked, as whole words in any case, in every desk reason and note others read on this idea (BLD-B278;
    lane C's `_sweep` step 10, under the lock its caller took). Each changed text gets one `hidden_details` row
    (source "desk", `<table>:<id>`), made as `_sweep` makes one for any copy with no owner's words. Returns how many
    texts changed. The sharer's words are never touched here, and this never calls `_sweep`."""
    from hide import detect
    from hide.desk import _copy_detail

    masked = detect.mask(kind, value)
    changed = 0
    for table, row_id, blob in _reasons_and_notes(conn, idea_uuid):
        column = COLUMNS[table]
        text = unseal(blob, table, column, row_id)
        if not text or not detect.value_places(text, value):
            continue
        new, n = detect.mask_in(text, value, masked)
        if not n:
            continue
        conn.execute(
            f"UPDATE {table} SET {column} = %s WHERE id::text = %s",  # noqa: S608 (fixed names)
            (seal(new, table, column, row_id), row_id),
        )
        _copy_detail(conn, idea_uuid, "desk", f"{table}:{row_id}", kind, value, found_by)
        changed += 1
    return changed
