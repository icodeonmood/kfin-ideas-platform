"""The gatekeeper's re-check (L-HIDE.detect, BLD-C067).

When the gateway fails while a message, answer, conversation message or edit is hidden, the text goes on with the
patterns and names only (the person never waits on the model), `hide.gatekeeper_skipped` is audited and a
`hide.recheck` job is queued with IDs only. The job runs the gatekeeper again on the person's sealed words once the
gateway is back: what it finds is stored like any find, the text's masked copy is rebuilt (messages, answers and
conversation messages), and each new value is masked in every other copy of the idea (`desk._sweep`), which covers
an edit's masked copies in the fix, the parts and the idea's lines. While the gateway is still down the job fails
and the runner tries again with its backoff.
"""

from __future__ import annotations

from typing import Any

from core.db import Conn
from core.logging import get_logger
from hide.core import SEALED_SOURCES, _hide, details_for, is_uuid, own_words

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
    with conn.transaction():
        before = {str(d["vault_tag"]) for d in details_for(conn, idea_uuid, source, source_id)}
        _, kept = _hide(
            conn, idea_uuid, words, by=by, source=source, source_id=source_id, gatekeeper=True, recheck=True
        )
        if source in ("message", "answer", "conversation"):
            found = desk.load_sealed(conn, idea_uuid, source, source_id)
            if found:
                desk._write_sealed(conn, idea_uuid, found[0], details_for(conn, idea_uuid, source, source_id))
        fresh = [d for d in kept if d["found_by"] == "gatekeeper" and str(d["vault_tag"]) not in before]
        copies = 0
        for d in fresh:
            value = words[int(d["span_start"]) : int(d["span_end"])]
            copies += desk._sweep(conn, idea_uuid, value, str(d["kind"]), found_by="gatekeeper").copies
    log.info(
        "hide.rechecked", idea_id=idea_uuid, source_code=source, hidden_count=len(fresh), other_copies=copies
    )
