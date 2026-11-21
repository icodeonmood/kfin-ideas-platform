"""L-DRAFT on the stack (BLD-C071 to BLD-C076): start, turn and save. A draft from the person's words, masked before
anything else sees them (DEC-103) with their own words sealed for them alone; parts built from those words only
through the gateway, never over a pin; everything still works by hand with the assistant off (DEC-105); offline
messages kept once; one editor; archived, never deleted. Synthetic text only; the fake model route."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from typing import Any

import pytest

from core import killswitch
from core.db import connect
from draft import runs, store
from draft.archive import archive_untouched
from draft.store import Device, DraftError, Owner
from gateway import limits
from gateway.routes import FAKE_SCRIPT
from onepc.context import open_text
from tests import helpers

LAPTOP = Device("laptop", "laptop-device-0001")
PHONE = Device("phone", "phone-device-0002")
W1 = (
    'When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 '
    "means, so they call the branch."
)
W2 = "Our branch takes about 40 calls a day like this, and each one takes 5 to 10 minutes."


@pytest.fixture
def drafting(db: Any, test_database: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Any, Owner]]:
    killswitch.clear_cache()
    limits.reset()
    FAKE_SCRIPT.clear()
    monkeypatch.setattr(runs, "_open", lambda: connect(helpers.db_url(test_database), autocommit=True))
    runs._means_cache.update(at=0.0, means=None)
    uid = db.execute(
        "INSERT INTO users (emp_id_hash, name, email) VALUES ('h-draft', 'Synthetic Sharer', "
        "'sharer@kfintech.example') RETURNING id"
    ).fetchone()["id"]
    yield db, Owner(str(uid), "CTR-0a1b2c")
    killswitch.clear_cache()


def _switch(db: Any, name: str, state: str) -> None:
    db.execute("UPDATE kill_switches SET state = %s WHERE name = %s", (state, name))
    killswitch.clear_cache()


def _run(run_id: str | None) -> None:
    assert run_id is not None
    runs.execute(run_id)


def _parts(db: Any, idea: str) -> dict[str, dict[str, Any]]:
    rows = db.execute(
        "SELECT key, state, value, why, source_quote FROM idea_parts WHERE idea_uuid = %s", (idea,)
    )
    return {r["key"]: r for r in rows.fetchall()}


# ---- start: masked, sealed, resumable (L-DRAFT.autosave/1-4, DEC-103) ---------------------------------------------


def test_l_draft_autosave_a_draft_starts_masked_and_sealed_and_resumes_on_any_device(drafting: Any) -> None:
    import generators

    db, owner = drafting
    _switch(db, "ai.all", "off")
    rng = generators.default_rng(3)
    folio, pan = generators.folio(rng), generators.pan(rng)
    own = f"{W1} One investor, folio {folio}, read out his PAN, {pan}, on the call."
    idea, run_id = store.create(db, owner, PHONE, text=own)
    _run(run_id)

    row = db.execute(
        "SELECT status, stage, char_count, saved_device FROM ideas WHERE id = %s", (idea,)
    ).fetchone()
    assert (row["status"], row["stage"], row["char_count"], row["saved_device"]) == (
        "draft",
        "draft",
        len(own),
        "phone",
    )
    msg = db.execute(
        "SELECT id, text_encrypted, spans FROM idea_messages WHERE idea_uuid = %s", (idea,)
    ).fetchone()
    masked = open_text("idea_messages", "text_encrypted", str(msg["id"]), msg["text_encrypted"])
    assert masked is not None and folio not in masked and pan not in masked
    assert "Folio ••••" in masked and "PAN ••••" in masked
    sealed = db.execute(
        "SELECT owner_user_id FROM idea_words_sealed WHERE source = 'message' AND source_id = %s",
        (str(msg["id"]),),
    ).fetchone()
    assert str(sealed["owner_user_id"]) == owner.user_id
    kinds = [r["kind"] for r in db.execute("SELECT kind FROM hidden_details WHERE idea_uuid = %s", (idea,))]
    assert sorted(kinds) == ["folio", "pan"]

    # Resumed on the laptop: the person's own words, their spans, and where it was saved.
    draft = store.view(db, owner, idea, LAPTOP)
    assert draft["messages"][0]["text"] == own
    assert [s["kind"] for s in draft["messages"][0]["spans"]] == ["folio", "pan"]
    assert draft["saved_on"] == {"device": "phone", "this_device": False}
    assert draft["saved_labels"]["sidebar"].endswith("on your phone")
    assert draft["step"] == "tell" and draft["min_chars"] == 30 and draft["assistant"] is False
    assert {h["masked"][:5] for h in draft["hidden"]} == {"Folio", "PAN •"}
    # Someone else's draft looks exactly like a missing one.
    with pytest.raises(DraftError) as err:
        store.view(db, Owner(owner.user_id, "CTR-0d0d0d"), idea, LAPTOP)
    assert err.value.status == 404


# ---- DEC-105: with the assistant off, every part is filled by hand ------------------------------------------------


def test_l_draft_dec_105_with_ai_off_parts_wait_for_the_person_and_the_draft_still_gets_ready(
    drafting: Any,
) -> None:
    db, owner = drafting
    _switch(db, "ai.all", "off")
    idea, run_id = store.create(db, owner, LAPTOP, text=f"{W1} {W2}")
    _run(run_id)
    parts = _parts(db, idea)
    assert {k: parts[k]["state"] for k in ("title", "often", "who", "value", "area")} == dict.fromkeys(
        ("title", "often", "who", "value", "area"), "failed"
    )  # C-DRAFT-LOADER.failure: "Couldn't work this out. Add it yourself."
    assert db.execute("SELECT count(*) AS n FROM llm_calls").fetchone()["n"] == 0  # no model at all
    draft = store.view(db, owner, idea, LAPTOP)
    # DEC-118 (BLD-C195): the words are at the minimum and nothing builds, so it can move on; Check it fills the rest.
    assert draft["ready"] is True and draft["run"]["state"] == "done"

    for key, value in (("title", "Rejection SMS codes confuse investors"), ("summary", "Investors call the branch."),
                       ("area", "Investor service"), ("who", ["Investors"]), ("value", ["saves_time"])):  # fmt: skip
        assert store.set_part(db, owner, idea, key, LAPTOP, {"value": value}) is None
    draft = store.view(db, owner, idea, LAPTOP)
    assert draft["ready"] is True
    assert draft["parts"]["title"] == {"state": "pinned", "value": "Rejection SMS codes confuse investors",
                                       "mean_ms": 1800}  # fmt: skip
    assert draft["parts"]["who"]["state"] == "pinned" and draft["sorting"]["affects"]["value"] == [
        "Investors"
    ]
    with pytest.raises(DraftError) as err:  # "Suggest again" needs the assistant
        store.set_part(db, owner, idea, "title", LAPTOP, {"pinned": False})
    assert err.value.code == "assistant_off"


# ---- turn: parts from the person's own words, never over a pin (L-DRAFT.parts, L-DRAFT.pins) ----------------------


def test_l_draft_parts_runs_fill_every_part_from_the_words_through_the_gateway(drafting: Any) -> None:
    db, owner = drafting
    idea, run_id = store.create(db, owner, LAPTOP, text=W1)
    _, second = store.add_message(db, owner, idea, LAPTOP, text=W2)
    for r in (run_id, second):
        _run(r)
    parts = _parts(db, idea)
    assert parts["title"]["state"] == "filled" and parts["title"]["value"]["title"]
    assert parts["often"]["value"] == "About 40 calls a day"
    assert parts["often"]["why"] == "From your words: “about 40 calls a day”"
    assert parts["often"]["source_quote"] == "about 40 calls a day"
    assert "Investors" in parts["who"]["value"] and parts["area"]["value"] == "Investor service"
    assert parts["who"]["why"].startswith("Suggested because ")
    assert "saves_time" in parts["value"]["value"]
    assert parts["similar"]["state"] == "failed"  # L-SIMILAR is not on main yet: never "none found"
    calls = db.execute("SELECT agent, outcome, ref_id FROM llm_calls").fetchall()
    # The parts, and L-HIDE's gatekeeper on every message before anything else sees it (main, BLD-C151).
    assert calls and "draft-part" in {c["agent"] for c in calls}
    assert {c["agent"] for c in calls} <= {"draft-part", "gatekeeper"}
    assert all(c["ref_id"] == f"DRAFT-{idea}" for c in calls)
    done = db.execute("SELECT receipt, ready, part_ms FROM draft_runs WHERE id = %s", (second,)).fetchone()
    assert "often" in done["part_ms"] and any(line.startswith("Noted how often:") for line in done["receipt"])
    draft = store.view(db, owner, idea, LAPTOP)
    assert draft["ready"] is True and draft["receipt"] == list(done["receipt"])
    assert draft["parts"]["summary"]["state"] == "filled"


def test_s04b_layout_2_each_message_keeps_its_own_receipt_masked(drafting: Any) -> None:
    """S-04B.layout/2, Compose.md "Follow-ups queued" (BLD-C184; lane G's walk, J-SHARE/5, J-RECOVER/5): after a
    second message the first keeps its receipt, with the hidden PAN as its masked tail only, and the draft read keeps
    both, so a reload draws both. A run with no message of its own (try again) belongs to the newest message."""
    import generators

    db, owner = drafting
    rng = generators.default_rng(11)
    pan = generators.pan(rng)
    idea, first = store.create(
        db, owner, LAPTOP, text=f"{W1} One investor read out his PAN, {pan}, on the call."
    )
    _run(first)
    _, second = store.add_message(db, owner, idea, LAPTOP, text=W2)
    _run(second)
    draft = store.view(db, owner, idea, LAPTOP)
    one, two = draft["messages"]
    tail = f"PAN ••••{pan[-2:]}"
    assert f"Hid 1 personal detail from everyone but you: {tail}." in one["receipt"]
    assert any(line.startswith("Noted how often:") for line in two["receipt"])
    assert not any(line.startswith("Hid ") for line in two["receipt"])
    runs_by_message = {
        str(r["message_id"]): list(r["receipt"])
        for r in db.execute(
            "SELECT message_id, receipt FROM draft_runs WHERE idea_uuid = %s", (idea,)
        ).fetchall()
    }
    assert one["receipt"] == runs_by_message[one["id"]] and two["receipt"] == runs_by_message[two["id"]]
    assert draft["receipt"] == two["receipt"]  # the latest, as before
    assert pan not in str(one["receipt"]) + str(two["receipt"])  # non-negotiables 4 and 7
    # S-04B.layout/1: each message also carries its day, time and device for when it is picked up (BLD-C185)
    assert one["at_label_earlier"].startswith("Today, ") and one["at_label_earlier"].endswith(
        ", on your laptop"
    )
    # Try again (no message of its own) belongs to the newest message; the first keeps its own, and an empty
    # receipt from it leaves the second's in place (the deterministic cases are in test_l_draft_unit.py)
    again = store.build(db, owner, idea, LAPTOP)
    _run(again)
    db.execute("UPDATE draft_runs SET receipt = '[]'::jsonb WHERE id = %s", (again,))
    later = store.view(db, owner, idea, LAPTOP)
    assert later["messages"][0]["receipt"] == one["receipt"]
    assert later["messages"][1]["receipt"] == two["receipt"]
    assert later["receipt"] == []  # the top-level receipt is still the latest run's, as other readers expect


def test_l_draft_pins_a_pinned_part_is_never_overwritten_and_unpinning_suggests_again(drafting: Any) -> None:
    db, owner = drafting
    idea, run_id = store.create(db, owner, LAPTOP, text=f"{W1} {W2}")
    _run(run_id)
    store.set_part(db, owner, idea, "often", LAPTOP, {"value": "Twice a day at our branch"})
    _, again = store.add_message(db, owner, idea, LAPTOP, text="Investors now call 60 times a day about it.")
    built = db.execute("SELECT parts FROM draft_runs WHERE id = %s", (again,)).fetchone()["parts"]
    assert (
        "often" not in built and "title" in built
    )  # L-DRAFT.parts/4: only what it could change, never a pin
    _run(again)
    often = _parts(db, idea)["often"]
    assert (often["state"], often["value"]) == ("pinned", "Twice a day at our branch")
    unpin = store.set_part(db, owner, idea, "often", LAPTOP, {"pinned": False})
    assert db.execute("SELECT parts FROM draft_runs WHERE id = %s", (unpin,)).fetchone()["parts"] == ["often"]
    _run(unpin)
    assert _parts(db, idea)["often"]["state"] == "filled"


def test_l_draft_parts_4_a_dropped_answer_keeps_the_filled_part_until_its_words_go_bld_c033(
    drafting: Any,
) -> None:
    """The planted "a lot of money" makes the fake quote a figure nobody gave, on both asks: the gateway drops it
    (`ungrounded_dropped`) and the part keeps what it showed, while its own quote still stands in the words."""
    db, owner = drafting
    idea, run_id = store.create(db, owner, LAPTOP, text=f"{W1} {W2}")
    _run(run_id)
    assert _parts(db, idea)["often"]["value"] == "About 40 calls a day"
    _, again = store.add_message(db, owner, idea, LAPTOP, text="It costs us a lot of money every month.")
    assert "often" in db.execute("SELECT parts FROM draft_runs WHERE id = %s", (again,)).fetchone()["parts"]
    _run(again)
    often = _parts(db, idea)["often"]
    assert (often["state"], often["value"], often["source_quote"]) == (
        "filled",
        "About 40 calls a day",
        "about 40 calls a day",
    )
    dropped = db.execute(
        "SELECT outcome FROM llm_calls WHERE agent = 'draft-part' AND error_code = 'ungrounded_dropped'"
    ).fetchall()
    assert [r["outcome"] for r in dropped] == ["ok_after_retry"]  # one part, re-asked once, then dropped
    run = db.execute("SELECT part_ms, receipt FROM draft_runs WHERE id = %s", (again,)).fetchone()
    assert run["part_ms"]["often"] == 0  # not a sample for the loader's means
    assert not any(line.startswith("Noted how often:") for line in run["receipt"])  # nothing changed
    # An edit takes the quoted words out: the part is emptied, never left showing words that are gone.
    first = db.execute(
        "SELECT id FROM idea_messages WHERE idea_uuid = %s ORDER BY seq LIMIT 1", (idea,)
    ).fetchone()["id"]
    _, edited = store.edit_message(db, owner, idea, str(first), LAPTOP, text=W1)
    _run(edited)
    often = _parts(db, idea)["often"]
    assert (often["state"], often["value"], often["source_quote"]) == ("failed", None, None)


def test_l_draft_parts_4_a_message_without_new_facts_rebuilds_only_the_title(drafting: Any) -> None:
    db, owner = drafting
    idea, run_id = store.create(db, owner, LAPTOP, text=f"{W1} {W2}")
    _run(run_id)
    _, again = store.add_message(db, owner, idea, LAPTOP, text="It started after the new layout went live.")
    built = db.execute("SELECT parts FROM draft_runs WHERE id = %s", (again,)).fetchone()["parts"]
    assert built == ["title", "similar"]


def test_l_draft_parts_3_below_25_characters_nothing_is_built(drafting: Any) -> None:
    db, owner = drafting
    idea, run_id = store.create(db, owner, LAPTOP, text="The SMS is unclear.")
    assert run_id is None
    assert store.view(db, owner, idea, LAPTOP)["parts"]["title"]["state"] == "waiting"


# ---- save: offline, one editor, archive (L-DRAFT.autosave/5, /7, /8) ----------------------------------------------


def test_l_draft_autosave_7_an_offline_message_sent_twice_is_kept_once_in_time_order(drafting: Any) -> None:
    db, owner = drafting
    idea, _ = store.create(db, owner, LAPTOP, text=W1, idempotency_key="create-key-0001")
    again, run = store.create(db, owner, LAPTOP, text=W1, idempotency_key="create-key-0001")
    assert again == idea and run is None  # A-API.conventions/3
    earlier = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=5)
    first, _ = store.add_message(db, owner, idea, LAPTOP, text=W2, client_id="offline-msg-0001", at=earlier)
    twice, none = store.add_message(
        db, owner, idea, LAPTOP, text=W2, client_id="offline-msg-0001", at=earlier
    )
    assert twice == first and none is None
    texts = [m["text"] for m in store.view(db, owner, idea, LAPTOP)["messages"]]
    assert texts == [W2, W1]  # in time order: the offline one was typed first


def test_l_draft_autosave_5_opening_on_another_device_takes_over(drafting: Any) -> None:
    db, owner = drafting
    idea, _ = store.create(db, owner, LAPTOP, text=W1)
    draft = store.view(db, owner, idea, PHONE, open_=True)
    assert draft["editor"] == {"device": "phone", "this_device": True}
    with pytest.raises(DraftError) as err:
        store.add_message(db, owner, idea, LAPTOP, text=W2)
    assert (err.value.code, err.value.extra) == ("open_elsewhere", {"device": "phone"})
    store.view(db, owner, idea, LAPTOP, open_=True)  # "Carry on here?"
    store.add_message(db, owner, idea, LAPTOP, text=W2)


def test_l_draft_autosave_7_an_offline_replay_is_kept_while_another_device_edits_bld_c036(
    drafting: Any,
) -> None:
    """L-DRAFT.autosave/7 over /5: nothing typed is discarded. The phone typed offline while the laptop carried on;
    on reconnect its messages are kept in time order, it does not take over, and a retry is kept once."""
    db, owner = drafting
    _switch(db, "ai.all", "off")
    idea, _ = store.create(db, owner, PHONE, text=W1)
    db.execute(
        "UPDATE idea_messages SET created_at = now() - interval '10 minutes' WHERE idea_uuid = %s", (idea,)
    )
    store.view(db, owner, idea, LAPTOP, open_=True)  # the laptop is the editor now
    typed = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=2)  # on the phone, offline, after its first words
    mid, _ = store.add_message(db, owner, idea, PHONE, text=W2, client_id="offline-phone-0001", at=typed)
    again, run = store.add_message(db, owner, idea, PHONE, text=W2, client_id="offline-phone-0001", at=typed)
    assert again == mid and run is None
    online_retry, _ = store.add_message(db, owner, idea, PHONE, text=W2, client_id="offline-phone-0001")
    assert online_retry == mid  # a retry of what was already kept, whoever edits now
    draft = store.view(db, owner, idea, LAPTOP)
    assert [m["text"] for m in draft["messages"]] == [W1, W2]
    assert draft["editor"] == {"device": "laptop", "this_device": True}
    with pytest.raises(DraftError) as err:  # a new live message from the phone still needs "Carry on here?"
        store.add_message(db, owner, idea, PHONE, text="One more thing.", client_id="live-phone-0002")
    assert err.value.code == "open_elsewhere"


def test_l_draft_autosave_5_a_message_stamped_now_from_another_device_is_live_bld_c036(drafting: Any) -> None:
    """A stale second tab cannot write past "Carry on here?" by naming the time: only a message typed before the
    editor's last save (or over a minute ago) is an offline replay. A stored client_id still answers first."""
    db, owner = drafting
    _switch(db, "ai.all", "off")
    idea, _ = store.create(db, owner, PHONE, text=W1)
    db.execute(
        "UPDATE idea_messages SET created_at = now() - interval '10 minutes' WHERE idea_uuid = %s", (idea,)
    )
    store.view(db, owner, idea, LAPTOP, open_=True)  # the laptop is the editor now
    editor_at = db.execute("SELECT editor_at FROM ideas WHERE id = %s", (idea,)).fetchone()["editor_at"]
    with pytest.raises(DraftError) as err:
        store.add_message(
            db, owner, idea, PHONE, text=W2, client_id="stale-phone-0001", at=dt.datetime.now(dt.UTC)
        )
    assert (err.value.code, err.value.extra) == ("open_elsewhere", {"device": "laptop"})
    assert err.value.status == 409
    typed = editor_at - dt.timedelta(seconds=30)  # typed on the phone, offline, before the laptop carried on
    mid, _ = store.add_message(db, owner, idea, PHONE, text=W2, client_id="offline-phone-0003", at=typed)
    again, run = store.add_message(
        db, owner, idea, PHONE, text=W2, client_id="offline-phone-0003", at=dt.datetime.now(dt.UTC)
    )
    assert again == mid and run is None  # the stored message, before any check
    draft = store.view(db, owner, idea, LAPTOP)
    assert [m["text"] for m in draft["messages"]] == [W1, W2]
    assert draft["editor"] == {"device": "laptop", "this_device": True}  # the replay did not take over


STREAM = "5f0c2d3e-8a41-4c6b-9f7e-2b1d0c9a8e71"


def test_l_draft_voice_4_a_voice_note_is_hidden_and_kept_with_its_english_copy_bld_c038(
    drafting: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /drafts/:id/messages with via voice and a stream id: the message is c/sarvam's voice_to_message (here a
    stand-in), then hidden, sealed and kept like typed words, with the English copy labelled and masked."""
    import generators

    from draft import adapters

    db, owner = drafting
    _switch(db, "ai.all", "off")
    idea, _ = store.create(db, owner, PHONE, text=W1)
    pan = generators.pan(generators.default_rng(11))
    heard = f"R07 ka matlab kisi ko nahi pata, isliye sab branch ko call karte hain. Ek investor ne PAN {pan} bola."
    english = f"Nobody knows what R07 means, so everyone calls the branch. An investor read out PAN {pan}."
    handed: list[tuple[Any, ...]] = []

    def voice_message(
        conn: Any, stream_id: str, *, idea_uuid: str, by_code: str, consume: bool = True
    ) -> Any:
        handed.append((stream_id, idea_uuid, by_code, consume))
        return adapters.VoiceNote(text=heard, text_en=english, lang="hi")

    monkeypatch.setattr(adapters, "voice_message", voice_message)
    mid, _ = store.add_message(db, owner, idea, PHONE, text=heard, via="voice", stream_id=STREAM)
    assert handed == [(STREAM, idea, owner.code, True)]
    msg = next(m for m in store.view(db, owner, idea, PHONE)["messages"] if m["id"] == mid)
    assert (msg["via"], msg["lang"], msg["text"]) == ("voice", "hi", heard)  # their own words, to them
    assert msg["text_en_label"] == "Typed up in English"
    assert msg["text_en"].startswith("Nobody knows what R07 means") and pan not in msg["text_en"]
    row = db.execute("SELECT text_encrypted FROM idea_messages WHERE id = %s", (mid,)).fetchone()
    assert pan not in (open_text("idea_messages", "text_encrypted", mid, row["text_encrypted"]) or pan)
    assert msg["spans"] and msg["spans"][0]["kind"] == "pan"  # hidden first, like typed words

    def unavailable(*_: Any, **__: Any) -> Any:
        raise adapters.VoiceUnavailable

    monkeypatch.setattr(adapters, "voice_message", unavailable)
    with pytest.raises(DraftError) as err:
        store.add_message(db, owner, idea, PHONE, text=heard, via="voice", stream_id=STREAM)
    assert (err.value.status, err.value.code) == (503, "voice_unavailable")
    assert len(store.view(db, owner, idea, PHONE)["messages"]) == 2  # nothing kept


def test_l_draft_autosave_8_untouched_drafts_are_archived_never_deleted(drafting: Any) -> None:
    db, owner = drafting
    old, _ = store.create(db, owner, LAPTOP, text=W1)
    fresh, _ = store.create(db, owner, LAPTOP, text=W2)
    db.execute("UPDATE ideas SET saved_at = now() - interval '31 days' WHERE id = %s", (old,))
    assert archive_untouched(db) == 1
    assert (
        db.execute("SELECT count(*) AS n FROM ideas WHERE id = ANY(%s::uuid[])", ([old, fresh],)).fetchone()[
            "n"
        ]
        == 2
    )
    assert [d["id"] for d in store.recent(db, owner, LAPTOP, archived=True)["items"]] == [old]
    with pytest.raises(DraftError) as err:
        store.add_message(db, owner, idea_uuid=old, device=LAPTOP, text=W2)
    assert err.value.code == "archived"
    store.restore_draft(db, owner, old, PHONE)
    restored = store.view(db, owner, old, PHONE)
    assert restored["archived"] is False
    assert restored["editor"] == {"device": "phone", "this_device": True}  # BLD-C036: the restoring tab edits
    store.archive(db, owner, fresh)  # DELETE /drafts/:id archives too
    assert db.execute("SELECT archived_at IS NOT NULL AS a FROM ideas WHERE id = %s", (fresh,)).fetchone()[
        "a"
    ]


def test_l_draft_stream_live_view_and_a_stale_run_is_settled(drafting: Any) -> None:
    db, owner = drafting
    _switch(db, "ai.all", "off")
    idea, run_id = store.create(db, owner, LAPTOP, text=W1)
    _run(run_id)
    live = store.live(db, owner, idea, run_id)
    assert live["run"]["state"] == "done" and live["run"]["parts"][0]["key"] == "title"
    assert set(live["run"]["part_ms"]) >= {"title"} and live["parts"]["title"]["state"] == "failed"
    # A run left going by a worker that stopped is settled on the next read.
    db.execute(
        "INSERT INTO draft_runs (idea_uuid, state, parts, started_at) VALUES (%s, 'running', '{often}', "
        "now() - interval '5 minutes')",
        (idea,),
    )
    db.execute("UPDATE idea_parts SET state = 'updating', run_id = (SELECT id FROM draft_runs WHERE state = "
               "'running') WHERE idea_uuid = %s AND key = 'often'", (idea,))  # fmt: skip
    stranger = Owner(owner.user_id, "CTR-0d0d0d")
    with pytest.raises(DraftError) as err:  # ownership first: someone else's read changes nothing
        store.view(db, stranger, idea, LAPTOP)
    assert err.value.status == 404
    with pytest.raises(DraftError) as err:
        store.live(db, stranger, idea)
    assert err.value.status == 404
    assert db.execute("SELECT count(*) AS n FROM draft_runs WHERE state = 'running'").fetchone()["n"] == 1
    assert store.view(db, owner, idea, LAPTOP)["parts"]["often"]["state"] == "failed"
    assert db.execute("SELECT count(*) AS n FROM draft_runs WHERE state = 'running'").fetchone()["n"] == 0


def test_l_draft_hide_what_an_edit_or_a_shorter_list_takes_out_leaves_the_vault_bld_c038(
    drafting: Any,
) -> None:
    import generators

    db, owner = drafting
    _switch(db, "ai.all", "off")
    rng = generators.default_rng(7)
    pan, phone = generators.pan(rng), generators.mobile(rng)
    idea, _ = store.create(db, owner, LAPTOP, text=f"{W1} The caller read out his PAN, {pan}.")
    store.add_message(db, owner, idea, LAPTOP, text=f"He called again with the same PAN, {pan}.")

    def vault_types() -> list[str]:
        rows = db.execute(
            "SELECT type FROM pseudonym_vault WHERE scope_id = %s ORDER BY type", (f"DRAFT-{idea}",)
        )
        return [r["type"] for r in rows.fetchall()]

    def edit_rows() -> list[str]:
        rows = db.execute(
            "SELECT source_id FROM idea_words_sealed WHERE idea_uuid = %s AND source = 'edit' ORDER BY source_id",
            (idea,),
        )
        return [r["source_id"].rsplit(":", 1)[1] for r in rows.fetchall()]

    assert vault_types() == ["PAN"]  # one value, one tag, held by two hidden details
    first = db.execute(
        "SELECT id FROM idea_messages WHERE idea_uuid = %s ORDER BY seq LIMIT 1", (idea,)
    ).fetchone()["id"]
    store.edit_message(db, owner, idea, str(first), LAPTOP, text=W1)
    assert vault_types() == ["PAN"]  # the other message still holds it
    second = db.execute(
        "SELECT id FROM idea_messages WHERE idea_uuid = %s ORDER BY seq DESC LIMIT 1", (idea,)
    ).fetchone()["id"]
    store.edit_message(db, owner, idea, str(second), LAPTOP, text="He called again about the same code.")
    assert vault_types() == []  # nothing holds it now: the value leaves the vault

    who = ["Investors", f"Caller on {phone}", "Branch staff"]
    store.set_part(db, owner, idea, "who", LAPTOP, {"value": who})
    assert edit_rows() == ["0", "1", "2"] and vault_types() == ["PHONE"]
    store.set_part(db, owner, idea, "who", LAPTOP, {"value": ["Investors"]})
    assert edit_rows() == ["0"] and vault_types() == []
    assert (
        db.execute(
            "SELECT count(*) AS n FROM hidden_details WHERE idea_uuid = %s AND source = 'edit'", (idea,)
        ).fetchone()["n"]
        == 0
    )


def test_l_draft_recent_lists_titles_and_where_they_were_saved(drafting: Any) -> None:
    db, owner = drafting
    _switch(db, "ai.all", "off")
    idea, _ = store.create(db, owner, PHONE, text=W1)
    store.set_part(db, owner, idea, "title", PHONE, {"value": "Rejection SMS codes confuse investors"})
    untitled, _ = store.create(db, owner, LAPTOP, text=W2)
    items = store.recent(db, owner, LAPTOP)["items"]
    assert [i["id"] for i in items] == [untitled, idea]
    assert items[1]["title"] == "Rejection SMS codes confuse investors"
    assert items[0]["title"].startswith("Our branch takes about 40 calls")  # no title yet: their first words
    assert items[1]["saved_labels"]["sidebar"] == "Today, on your phone"


def test_l_draft_c_simgrid_grid_4_the_draft_says_it_was_kept_separate_bld_c152(drafting: Any) -> None:
    # "Keep mine separate" sets ideas.kept_separate (lane F, BLD-F020); GET /drafts/:id carries it, so S-05's
    # similar grid stays folded to its note after a reload (C-SIMGRID.grid/4).
    db, owner = drafting
    _switch(db, "ai.all", "off")
    idea, _ = store.create(db, owner, PHONE, text=W1)
    assert store.view(db, owner, idea, LAPTOP)["kept_separate"] is False
    db.execute("UPDATE ideas SET kept_separate = true WHERE id = %s", (idea,))
    assert store.view(db, owner, idea, LAPTOP)["kept_separate"] is True


# ---- L-DRAFT.channels: built and off (DEC-105) ---------------------------------------------------------------------


def test_l_draft_channels_an_email_lands_as_a_masked_draft_only_while_its_switch_is_on(drafting: Any) -> None:
    """BLD-C077; BLD-C037: `submissions` holds too, and a note with no words bounces with its name."""
    import generators

    from draft.channels import Arrival, ChannelOff, intake

    db, owner = drafting
    _switch(db, "ai.all", "off")
    db.execute(
        "INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (owner.code, owner.user_id)
    )
    pan = generators.pan(generators.default_rng(5))
    arrival = Arrival(
        channel="email",
        sender="Sharer@KFINTECH.example",
        note=f"{W1} The caller read out a PAN, {pan}.",
        received_at=dt.datetime.now(dt.UTC),
        subject="Fwd: R07 rejections again",
        thread="From the branch: three more calls today about R07.",
    )
    _switch(db, "intake.email", "off")
    with pytest.raises(ChannelOff):
        intake(db, arrival)
    _switch(db, "intake.email", "on")
    _switch(db, "submissions", "off")  # BLD-C037: paused like every other way to start a draft
    with pytest.raises(ChannelOff) as off:
        intake(db, arrival)
    assert str(off.value) == "submissions"
    _switch(db, "submissions", "on")
    assert intake(db, Arrival("email", "someone@elsewhere.example", W1, arrival.received_at)) == {
        "bounced": True,
        "reason_code": "unknown_sender",
    }
    drafts_before = db.execute("SELECT count(*) AS n FROM ideas").fetchone()["n"]
    for note in ("", "   \n "):  # a forward with nothing on top: told, never a silent refusal
        bare = Arrival("email", arrival.sender, note, arrival.received_at, subject=arrival.subject)
        assert intake(db, bare) == {"bounced": True, "reason_code": "empty_message"}
    assert db.execute("SELECT count(*) AS n FROM ideas").fetchone()["n"] == drafts_before  # nothing stored
    out = intake(db, arrival)
    if out["run_id"]:
        _run(out["run_id"])
    draft = store.view(db, owner, out["draft_id"], LAPTOP)
    assert draft["channel"] == "email" and draft["messages"][0]["via"] == "email"
    assert draft["messages"][0]["text"] == arrival.note  # their own words, to them
    assert draft["origin"]["label"].startswith("From your email, today at ")
    assert draft["origin"]["label"].endswith(": “Fwd: R07 rejections again”")
    assert draft["origin"]["thread"].startswith("From the branch")
    assert draft["receipt"][0] == "Turned your email into a draft. Nothing has been sent."
    stored = db.execute(
        "SELECT text_encrypted, id FROM idea_messages WHERE idea_uuid = %s", (out["draft_id"],)
    )
    row = stored.fetchone()
    assert pan not in (
        open_text("idea_messages", "text_encrypted", str(row["id"]), row["text_encrypted"]) or pan
    )


def test_l_draft_autosave_2_files_added_with_a_message_resume_with_it(drafting: Any) -> None:
    db, owner = drafting
    _switch(db, "ai.all", "off")
    idea, _ = store.create(db, owner, LAPTOP, text=W1)
    db.execute(
        "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, name, mime, bytes, store_key, kind, file_state) "
        "VALUES ('ATT-2026-000901', %s, %s, 'sip-pending-screen.jpg', 'image/jpeg', 2048, 'quarantine/syn-901', "
        "'file', 'checked')",
        (idea, owner.code),
    )
    mid, _ = store.add_message(db, owner, idea, LAPTOP, text=W2, files=["ATT-2026-000901", "ATT-2026-999999"])
    draft = store.view(db, owner, idea, PHONE)
    second = next(m for m in draft["messages"] if m["id"] == mid)
    assert [f["id"] for f in second["files"]] == ["ATT-2026-000901"]
    assert second["files"][0]["name"] == "sip-pending-screen.jpg" and second["files"][0]["state"] == "checked"
    assert [f["id"] for f in draft["files"]] == ["ATT-2026-000901"]


def test_l_draft_autosave_2_C_FILE_row_the_found_line_and_view_stay_after_a_reload(drafting: Any) -> None:
    """BLD-E076: the draft read gives the owner the same FileItem lines as `POST /files` (E-ENTITIES FileItem), so
    Check it and the prompt box show the whole found line, and View, after a reload (C-FILE.row, L-HIDE.files).
    DEC-107: the sharer always opens their own checked file, one with a customer detail included."""
    db, owner = drafting
    _switch(db, "ai.all", "off")
    idea, _ = store.create(db, owner, LAPTOP, text=W1)
    a_phone = '{"found": [{"kind": "phone", "page": 1}]}'  # codes only, as the check stores them: no value
    for att, name, state, checks in (
        ("ATT-2026-000902", "branch-call-log.pdf", "personal_data_found", a_phone),
        ("ATT-2026-000903", "r07-reasons.pdf", "checked", '{"found": []}'),
        ("ATT-2026-000904", "r07-screen.pdf", "checking", None),
    ):
        db.execute(
            "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, name, mime, bytes, pages, store_key, kind, "
            "file_state, checks) VALUES (%s, %s, %s, %s, 'application/pdf', 4096, 1, %s, 'file', %s, %s::jsonb)",
            (att, idea, owner.code, name, f"clean/syn-{att[-3:]}", state, checks),
        )
    files = {f["id"]: f for f in store.view(db, owner, idea, PHONE)["files"]}
    found = files["ATT-2026-000902"]
    assert found["state"] == "personal_data_found" and found["added_by"] == {"id": owner.user_id}
    assert found["problem"] == (
        "Found a phone number on page 1. Only you, the review desk and the Ones Committee can open it."
    )
    assert "problem" not in files["ATT-2026-000903"] and "problem" not in files["ATT-2026-000904"]
    assert found["view_url"] == "/api/files/ATT-2026-000902/view"
    assert files["ATT-2026-000903"]["view_url"] == "/api/files/ATT-2026-000903/view"
    assert "view_url" not in files["ATT-2026-000904"]  # nobody opens a file before its checks finish
