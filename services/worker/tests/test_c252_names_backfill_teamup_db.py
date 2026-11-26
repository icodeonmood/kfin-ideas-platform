"""The names backfill (BLD-C252) on a team-up text, from the C252 review: a lead's decline reason is sealed under the
idea's uuid ("<idea>:<request>:decline") while its details and lane F's writer go by "<request>:decline". The
backfill turns the sealed key back into the caller's id (`caller_id`, as the re-check sweep does), so the name r6
left visible beside a PAN hides under that id, and the copy the asker reads is written masked again. Synthetic
people and values only (non-negotiable 11)."""

from __future__ import annotations

from typing import Any

import pytest

from hide import backfill
from hide import detect as hide_detect
from hide.core import own_words, scope_for
from teamup import adapters, requests
from tests.test_c235_desk_hide_teamup_db import _stored, _teamup_rows, cast, db
from tests.test_hide_store import count, made_up

pytestmark = pytest.mark.stack

__all__ = ["cast", "db"]  # the fixtures, used by name


def test_bld_c252_the_backfill_hides_a_name_in_a_decline_reason_under_its_callers_id(
    db: Any, cast: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    c = cast
    lead = str(c["lead"]["id"])
    pan = made_up()[1]
    rid = requests.send(
        db, c["lead"]["idea_id"], c["kavya"]["id"], {"note": "Our branch sees the same SMS code every week."}
    )["id"]
    reason = f"ravi kumar ka PAN {pan} hai, us par hum pehle se kaam kar rahe hain."
    # r6: hiding read no name in lower case, so the PAN hid and the name beside it did not.
    with monkeypatch.context() as r6:
        r6.setattr(hide_detect, "people_in", lambda *_a, **_k: [])
        requests.answer(db, rid, c["ravi"]["id"], {"answer": "decline", "reason": reason})
    decline = adapters.decline_id(rid)
    assert own_words(db, "teamup", decline, idea_uuid=lead) == reason
    stored = str(_stored(db, "teamup_requests", "lead_reason_encrypted", rid))
    assert "ravi kumar" in stored and pan not in stored
    calls = count(db, "SELECT count(*) AS n FROM llm_calls WHERE ref_id = %s", scope_for(lead))

    out = backfill.run(db, {"ideas": [lead]})

    assert out["details"] >= 1
    stored = str(_stored(db, "teamup_requests", "lead_reason_encrypted", rid))
    assert "ravi kumar" not in stored and pan not in stored
    assert "ravi kumar" not in str(requests.read(db, rid, c["kavya"]["id"])["lead_reason"])
    rows = [r for r in _teamup_rows(db, lead) if r["source_id"] != rid]  # the note holds no detail
    assert {r["source_id"] for r in rows} == {decline}  # the caller's id, never the sealed row's key
    assert {"name", "pan"} <= {r["kind"] for r in rows}
    assert count(db, "SELECT count(*) AS n FROM llm_calls WHERE ref_id = %s", scope_for(lead)) == calls
    assert backfill.run(db, {"ideas": [lead]})["details"] == 0
