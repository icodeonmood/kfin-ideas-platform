"""The names backfill (BLD-C252; DEC-142, the product lead's choice of 27 Nov) against a migrated test database: a text
written under r6, whose lower-case customer name stayed visible beside a hidden PAN, gets the name hidden with no
model call; a second copy of the idea holding the name is swept; `gatekeeper_done_at` stays NULL so the gatekeeper's
re-check still runs later; and a second run changes nothing. Synthetic values only (non-negotiable 11)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from hide import backfill
from hide import detect as hide_detect
from hide.core import scope_for
from tests.test_hide_store import count, hdb, idea, made_up, masked_message, message, person, sealed_done

pytestmark = pytest.mark.stack

__all__ = ["hdb"]  # the fixture, used by name


def _details(db: Any, idea_uuid: str) -> list[tuple[str, str, str]]:
    return [
        (str(r["source_id"]), str(r["kind"]), str(r["vault_tag"]))
        for r in db.execute(
            "SELECT source_id, kind, vault_tag FROM hidden_details WHERE idea_uuid = %s ORDER BY source_id, span_start",
            (idea_uuid,),
        ).fetchall()
    ]


def test_bld_c252_dec142_the_backfill_hides_a_name_r6_left_visible_with_no_model_call(
    hdb: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from core import killswitch

    db = hdb
    pan = made_up()[1]
    uid, code = person(db)
    iid = idea(db, code)
    # Capture first, as r6 and r7 run until the assistant goes on.
    db.execute("UPDATE kill_switches SET state = 'off' WHERE name = 'ai.all'")
    killswitch.clear_cache()
    try:
        # r6: hiding read no name in lower case, so the PAN hid and the name beside it did not.
        with monkeypatch.context() as r6:
            r6.setattr(hide_detect, "people_in", lambda *_a, **_k: [])
            first, _ = message(db, iid, uid, f"ravi kumar ka PAN {pan} hai. form do baar aaya.")
            second, _ = message(db, iid, uid, "ravi kumar ne phir se call kiya", seq=2)
        assert "ravi kumar" in masked_message(db, first) and "ravi kumar" in masked_message(db, second)
        assert sealed_done(db, first) is None and sealed_done(db, second) is None
        calls = count(db, "SELECT count(*) AS n FROM llm_calls WHERE ref_id = %s", scope_for(iid))

        out = backfill.run(db, {"ideas": [iid]})

        # The name hides beside the PAN, and in the idea's other copy too (BLD-C252's sweep, L-HIDE rule 1).
        # (The English NER model may find more in mixed text; the name is what must hide.)
        assert out["texts"] == 2 and out["details"] >= 1 and out["other_copies"] >= 1
        assert "ravi kumar" not in masked_message(db, first) and pan not in masked_message(db, first)
        assert "ravi kumar" not in masked_message(db, second)
        kinds = [k for s, k, _ in _details(db, iid) if s == first]
        assert "name" in kinds and "pan" in kinds
        # No model call, and the gatekeeper's re-check of these texts still waits for it (BLD-C231).
        assert count(db, "SELECT count(*) AS n FROM llm_calls WHERE ref_id = %s", scope_for(iid)) == calls
        assert sealed_done(db, first) is None and sealed_done(db, second) is None
        audit = db.execute(
            "SELECT actor, entity, after FROM audit_log WHERE action = %s ORDER BY id DESC LIMIT 1",
            (backfill.DONE,),
        ).fetchone()
        assert audit["actor"] == "system:hide" and audit["entity"] == "job:hide.names_backfill"
        assert set(audit["after"]) == {"texts", "details", "other_copies"}  # counts only, never a value

        # Safe to run again: the same details, the same masked copies.
        details, masked = _details(db, iid), (masked_message(db, first), masked_message(db, second))
        again = backfill.run(db, {"ideas": [iid]})
        assert again == {"texts": 2, "details": 0, "other_copies": 0}
        assert (
            _details(db, iid) == details and (masked_message(db, first), masked_message(db, second)) == masked
        )
    finally:
        db.execute("UPDATE kill_switches SET state = 'on' WHERE name = 'ai.all'")
        killswitch.clear_cache()


def test_bld_c252_queued_once_until_it_has_finished(hdb: Any) -> None:
    """Queued at worker start under one dedupe key; never again once its audit row says it finished."""
    db = hdb
    db.execute("DELETE FROM jobs WHERE type = %s AND state IN ('queued', 'running')", (backfill.JOB,))
    finished = (
        db.execute("SELECT 1 FROM audit_log WHERE action = %s", (backfill.DONE,)).fetchone() is not None
    )
    if not finished:
        assert backfill.queue_once(db) is not None
        assert backfill.queue_once(db) is None  # one queued at a time
        db.execute("DELETE FROM jobs WHERE type = %s AND state = 'queued'", (backfill.JOB,))
        backfill.run(db, {"ideas": [str(uuid.uuid4())]})  # a run with nothing to do: it finishes, and says so
    assert backfill.queue_once(db) is None
    assert count(db, "SELECT count(*) AS n FROM jobs WHERE type = %s AND state = 'queued'", backfill.JOB) == 0
