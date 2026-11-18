"""J-SIMILAR/6a, L-MERGE.request/5 (BLD-C155): a draft its lead merged in is read, never written. The owner's
`GET /drafts/:id` answers it read-only with the IDEA- reference it is now part of, writes nothing even with
`open=1`, and every write to it is still refused as before; anyone else still finds nothing. Synthetic people only."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from core.db import Conn
from draft import runs, store
from draft.store import Device, DraftError, Owner
from teamup import drafts, requests
from tests import f_teamup_fixtures as f

LAPTOP = Device("laptop", "laptop-merged-0001")
PHONE = Device("phone", "phone-merged-0002")
NOTE = "Mine is the same failed SIP debit with no reason. Please take my words and the calls into yours."


@pytest.fixture
def db(db: Conn) -> Iterator[Conn]:
    yield db
    f.clean(db)


@pytest.fixture
def merged(db: Conn, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Tanvi's draft, merged into Rekha's idea by Rekha (L-MERGE.request/5), last opened on Tanvi's phone, with a
    run left going long ago: everything a read could settle or take over, if it wrote."""
    f.record_inbox(monkeypatch)
    rekha, tanvi = f.person(db, "Rekha Iyer"), f.person(db, "Tanvi Deshmukh")
    lead = f.idea(db, rekha, title="Failed SIP debits with no reason")
    draft = f.draft(db, tanvi, title="SIP debit failed and the SMS gives no reason")
    f.similar(db, draft, lead)
    db.execute(
        "UPDATE ideas SET step = 'check:3', saved_at = now() - interval '1 hour', saved_device = 'phone', "
        "saved_device_id = %s, editor_device_id = %s, editor_device = 'phone', editor_at = now() - interval '1 hour' "
        "WHERE id = %s",
        (PHONE.id, PHONE.id, draft["id"]),
    )
    asked = drafts.ask(db, str(draft["id"]), tanvi["id"], {"other_idea_id": lead["idea_id"], "note": NOTE})
    requests.answer(db, asked["id"], rekha["id"], {"answer": "merge"})
    db.execute(
        "INSERT INTO draft_runs (idea_uuid, state, started_at) VALUES (%s, 'running', now() - interval '1 day')",
        (draft["id"],),
    )
    return {
        "lead": lead,
        "draft": draft,
        "tanvi": tanvi,
        "rekha": rekha,
        "owner": Owner(tanvi["id"], tanvi["code"]),
    }


def _state(db: Conn, idea_uuid: Any) -> dict[str, Any]:
    row = db.execute(
        "SELECT status, merged_into, step, saved_at, saved_device_id, editor_device_id, editor_device, editor_at, "
        "archived_at, (SELECT array_agg(state ORDER BY started_at) FROM draft_runs WHERE idea_uuid = ideas.id) AS runs "
        "FROM ideas WHERE id = %s",
        (idea_uuid,),
    ).fetchone()
    assert row is not None
    return dict(row)


def _refused(fn: Any, *args: Any, **kw: Any) -> DraftError:
    with pytest.raises(DraftError) as exc:
        fn(*args, **kw)
    return exc.value


def test_J_SIMILAR_6a_L_MERGE_request_5_the_owner_reads_a_merged_draft_read_only_and_nothing_is_written(
    db: Conn, merged: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    draft_id, owner = str(merged["draft"]["id"]), merged["owner"]
    before = _state(db, draft_id)
    assert before["status"] == "merged" and before["runs"] == ["running"]
    settled: list[str] = []
    monkeypatch.setattr(runs, "settle_stale", lambda conn, idea_uuid: settled.append(idea_uuid))
    audits = db.execute("SELECT count(*) AS n FROM audit_log").fetchone()["n"]

    for open_ in (False, True):  # Compose and Check it both ask; `open=1` takes nothing over either
        out = store.view(db, owner, draft_id, LAPTOP, open_=open_)
        assert out["id"] == draft_id and out["merged_into"] == merged["lead"]["idea_id"]
        assert out["ready"] is False and out["step"] == "check:3"
        assert out["editor"] == {"device": "phone", "this_device": False}
        assert out["parts"]["title"]["value"] == ""  # its own parts, as it was left: nothing is rebuilt

    assert settled == []
    assert _state(db, draft_id) == before  # no run settled, no device taken over, nothing saved
    assert db.execute("SELECT count(*) AS n FROM audit_log").fetchone()["n"] == audits


def test_J_SIMILAR_6a_a_merged_draft_is_still_missing_for_anyone_else(
    db: Conn, merged: dict[str, Any]
) -> None:
    rekha = Owner(merged["rekha"]["id"], merged["rekha"]["code"])
    err = _refused(store.view, db, rekha, str(merged["draft"]["id"]), LAPTOP, open_=True)
    assert (err.status, err.code) == (404, "not_found")
    # The lead's own idea is not a draft: still not readable here, even by its owner.
    err = _refused(store.view, db, rekha, str(merged["lead"]["id"]), LAPTOP)
    assert (err.status, err.code) == (404, "not_found")


def test_J_SIMILAR_6a_every_write_to_a_merged_draft_is_refused_as_before(
    db: Conn, merged: dict[str, Any]
) -> None:
    draft_id, owner = str(merged["draft"]["id"]), merged["owner"]
    before = _state(db, draft_id)
    writes = [
        lambda: store.save_step(db, owner, draft_id, LAPTOP, "check:4"),
        lambda: store.add_message(db, owner, draft_id, LAPTOP, text="Twenty calls a day at our branch."),
        lambda: store.set_part(db, owner, draft_id, "title", LAPTOP, {"value": "A new title"}),
        lambda: store.build(db, owner, draft_id, LAPTOP),
        lambda: store.archive(db, owner, draft_id),
        lambda: store.restore_draft(db, owner, draft_id, LAPTOP),
        lambda: store.take_over(db, owner, draft_id, LAPTOP),
    ]
    for write in writes:
        err = _refused(write)
        assert (err.status, err.code) == (404, "not_found")
    assert _refused(store.live, db, owner, draft_id).status == 404  # the stream reads none either
    assert _state(db, draft_id) == before


def test_a_shared_idea_merged_by_the_desk_is_not_read_as_a_draft(db: Conn, merged: dict[str, Any]) -> None:
    """Only a draft closed as merged is read here; a shared idea that was merged keeps its own pages."""
    tanvi = merged["tanvi"]
    shared = f.idea(db, tanvi, title="Branch staff cannot see SIP pause requests", status="merged")
    err = _refused(store.view, db, merged["owner"], str(shared["id"]), LAPTOP)
    assert (err.status, err.code) == (404, "not_found")


@pytest.fixture
def merged_with_details(db: Conn, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """Tanvi's draft from her own words with a folio and a PAN hidden (patterns only: the assistant is off), the PAN
    shown before the merge; then Rekha merges it in."""
    import generators

    from core import killswitch
    from hide import show

    f.record_inbox(monkeypatch)
    db.execute("UPDATE kill_switches SET state = 'off' WHERE name = 'ai.all'")
    killswitch.clear_cache()
    rekha, tanvi = f.person(db, "Rekha Iyer"), f.person(db, "Tanvi Deshmukh")
    owner = Owner(tanvi["id"], tanvi["code"])
    lead = f.idea(db, rekha, title="Failed SIP debits with no reason")
    rng = generators.default_rng(5)
    words = (
        "The SIP debit failed and the SMS gave no reason. One investor, folio "
        f"{generators.folio(rng)}, read out his PAN, {generators.pan(rng)}, on the call."
    )
    draft_id, _run = store.create(db, owner, PHONE, text=words)
    f._made["ideas"].append(draft_id)
    db.execute(
        "UPDATE ideas SET title = 'SIP debit failed with no reason', "
        "summary = 'Investors call the branch when a SIP debit fails with no reason.' WHERE id = %s",
        (draft_id,),
    )
    details = {
        r["kind"]: str(r["id"])
        for r in db.execute(
            "SELECT id, kind FROM hidden_details WHERE idea_uuid = %s", (draft_id,)
        ).fetchall()
    }
    assert sorted(details) == ["folio", "pan"]
    show(db, draft_id, details["pan"], reason="made_up_example", by=tanvi["id"])
    f.similar(db, {"id": draft_id}, lead)
    asked = drafts.ask(db, draft_id, tanvi["id"], {"other_idea_id": lead["idea_id"], "note": NOTE})
    requests.answer(db, asked["id"], rekha["id"], {"answer": "merge"})
    yield {"draft_id": draft_id, "tanvi": tanvi, "details": details}
    killswitch.clear_cache()


def _words(db: Conn, draft_id: str) -> list[Any]:
    """Everything Show it and Hide it rewrite: the details' states, the masked and the sealed words."""
    return [
        db.execute(
            "SELECT id, state, reason, shown_at FROM hidden_details WHERE idea_uuid = %s ORDER BY id",
            (draft_id,),
        ).fetchall(),
        db.execute(
            "SELECT id, text_encrypted FROM idea_messages WHERE idea_uuid = %s", (draft_id,)
        ).fetchall(),
        db.execute(
            "SELECT source_id, text_encrypted FROM idea_words_sealed WHERE source = 'message' AND source_id IN "
            "(SELECT id::text FROM idea_messages WHERE idea_uuid = %s)",
            (draft_id,),
        ).fetchall(),
    ]


def test_J_SIMILAR_6a_L_HIDE_rules_6_show_it_and_hide_it_on_a_merged_draft_are_refused_and_the_words_stay(
    db: Conn, merged_with_details: dict[str, Any]
) -> None:
    from hide import HideError, hide_again, show

    m = merged_with_details
    draft_id, by = m["draft_id"], m["tanvi"]["id"]
    assert _state(db, draft_id)["status"] == "merged"
    before = _words(db, draft_id)
    audits = db.execute("SELECT count(*) AS n FROM audit_log").fetchone()["n"]
    with pytest.raises(HideError) as shown:
        show(db, draft_id, m["details"]["folio"], reason="internal_reference", by=by)
    with pytest.raises(HideError) as hidden:
        hide_again(db, draft_id, m["details"]["pan"], by=by)
    for exc in (shown, hidden):
        assert (exc.value.status, exc.value.code) == (404, "not_found")
    assert _words(db, draft_id) == before
    assert db.execute("SELECT count(*) AS n FROM audit_log").fetchone()["n"] == audits
