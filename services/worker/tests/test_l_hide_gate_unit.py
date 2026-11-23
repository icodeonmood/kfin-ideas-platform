"""BLD-C234, L-HIDE: the gate a caller asks before hide's lock (`hide.gate`) belongs to one exact text, the draft's
adapter passes it on only when one was asked, and the draft store knows which words it will hide. No database and
no model. Synthetic text only (non-negotiable 11)."""

from __future__ import annotations

import sys
import types
from typing import Any, cast

import pytest

from draft import adapters, store
from hide import detect
from hide.core import gate


def test_l_hide_bld_c234_a_gates_hash_is_of_the_exact_text() -> None:
    a, b = detect.text_hash("Investors call the branch"), detect.text_hash("Investors call the branch.")
    assert a == detect.text_hash("Investors call the branch") and a != b
    assert len(a) == 64 and set(a) <= set("0123456789abcdef")


def test_l_hide_bld_c234_hide_uses_a_gate_only_for_its_own_text() -> None:
    words = "Investors call the branch about the SMS"
    asked = detect.Gate([], text_hash=detect.text_hash(words))
    assert detect.usable(asked, words) is asked
    assert detect.usable(asked, words + " again") is None  # other words: hide asks the gatekeeper itself
    pieces = detect.Gate([])  # a file's pieces carry no hash and are used as given (hide/files.py)
    assert detect.usable(pieces, "any text") is pieces
    assert detect.usable(None, words) is None


def test_l_hide_bld_c234_a_gate_is_asked_only_for_a_known_source() -> None:
    with pytest.raises(ValueError):
        gate(cast(Any, None), "00000000-0000-4000-8000-000000000000", "words", source="nowhere")


def test_l_hide_bld_c234_l_draft_the_adapter_passes_a_gate_only_when_one_was_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[dict[str, Any]] = []

    def hide_message(*args: Any, **kw: Any) -> Any:
        seen.append(kw)
        return adapters.Hidden("Investors call the branch")

    hide = types.ModuleType("hide")
    hide.hide_message = hide_message
    monkeypatch.setitem(sys.modules, "hide", hide)

    class _Conn:  # no hidden details held yet: nothing for the vault to drop
        def execute(self, *_: Any) -> Any:
            return types.SimpleNamespace(fetchall=lambda: [])

    conn, asked = cast(Any, _Conn()), detect.Gate([])
    adapters.hide_message(conn, "idea-1", "words", by="user-1", source="message", source_id="m-1")
    adapters.hide_message(conn, "idea-1", "words", by="user-1", source="message", source_id="m-1", gate=asked)
    assert "gate" not in seen[0] and seen[1]["gate"] is asked
    # This stand-in hide has no `gate`, so nothing is asked.
    assert adapters.gate(conn, "idea-1", "words") is None


def test_l_draft_bld_c234_the_store_asks_about_the_words_it_will_hide() -> None:
    # The words `_check_text` keeps: trimmed.
    assert store._gateable("  Investors call the branch  ") == "Investors call the branch"
    assert store._gateable("   ") is None and store._gateable(None) is None
    assert store._part_texts("who", ["Investors", " ", 7]) == ["Investors", None, None]
    assert store._part_texts("often", "Every day") == ["Every day"]
    assert store._part_texts("value", ["a", "b"]) == []  # a value list is not hidden item by item


# ---- BLD-C231: the re-check sweep's pieces ------------------------------------------------------------------------


def test_l_hide_bld_c231_caller_id_undoes_sealed_key_for_every_source() -> None:
    """The sweep queues each re-check under the caller's own id, which hidden details and lane F's writer use."""
    from hide.core import caller_id, sealed_key

    idea = "11111111-2222-4333-8444-555555555555"
    rid = "66666666-7777-4888-9999-000000000000"
    for source, raw in (
        ("message", rid),
        ("answer", rid),
        ("conversation", rid),
        ("edit", f"{idea}:part:who:0"),
        ("edit", f"{idea}:3:title"),
        ("teamup", rid),
        ("teamup", f"{rid}:decline"),
        ("teamup", f"{rid}:ask"),
    ):
        key = sealed_key(idea, raw)
        assert caller_id(idea, source, key) == raw, (source, raw)
        assert sealed_key(idea, caller_id(idea, source, key)) == key


def test_l_hide_bld_c231_blank_words_are_checked_with_nothing_to_ask() -> None:
    gate = detect.gatekeeper_finds(cast(Any, None), "   ", "DRAFT-x")
    assert gate.checked and gate.finds == []
    assert not detect.Gate([]).checked  # a gate is unchecked unless the gatekeeper answered


def test_l_hide_bld_c231_the_watch_asks_the_sweep_and_survives_it_failing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core import watch
    from hide import recheck

    asked: list[Any] = []
    monkeypatch.setattr(recheck, "queue_unchecked", lambda conn: asked.append(conn) or 3)
    assert watch.Watch.unchecked_texts(cast(Any, "conn")) is True and asked == ["conn"]

    def broken(conn: Any) -> int:
        raise RuntimeError("down")

    monkeypatch.setattr(recheck, "queue_unchecked", broken)
    w = cast(Any, object.__new__(watch.Watch))
    for name in ("scanner", "bounces", "speech_route", "waiting_files"):
        monkeypatch.setattr(w, name, lambda conn: False, raising=False)
    w.run(cast(Any, "conn"))  # one check failing never stops the others or the ticker


def test_l_hide_bld_c231_the_desk_texts_sweep_is_nothing_until_lane_bs_module_is_there(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BLD-B278's hook in `_sweep`: lane B's `sweep_value`, called with the value under hide's lock; 0 without it."""
    from hide import desk

    monkeypatch.setattr(desk, "DESK_TEXTS", ("desk.no_such_module_c231", "sweep_value"))
    assert desk._sweep_desk_texts(cast(Any, None), "idea", "value", "name", "reviewer") == 0
    called: list[Any] = []
    fake = types.ModuleType("c231_fake_desk_texts")
    fake.sweep_value = lambda conn, idea, value, kind, *, found_by: called.append((idea, kind, found_by)) or 2
    monkeypatch.setitem(sys.modules, "c231_fake_desk_texts", fake)
    monkeypatch.setattr(desk, "DESK_TEXTS", ("c231_fake_desk_texts", "sweep_value"))
    assert desk._sweep_desk_texts(cast(Any, None), "idea", "value", "name", "reviewer") == 2
    assert called == [("idea", "name", "reviewer")]


def test_l_hide_bld_c231_lane_bs_desk_text_job_is_queued_only_where_its_handler_is(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BLD-B278: the switch-on queues `desk.text_recheck` only in a build that registers lane B's handler, so a build
    without it never holds a row no worker will run."""
    from hide import recheck
    from jobs import runner

    queued: list[tuple[str, Any]] = []
    monkeypatch.setattr(
        runner, "enqueue", lambda conn, kind, payload, dedupe_key=None: queued.append((kind, dedupe_key)) or 9
    )
    monkeypatch.delitem(runner.HANDLERS, recheck.DESK_TEXT_RECHECK, raising=False)
    assert recheck._start_desk_texts(cast(Any, None)) is False and queued == []
    monkeypatch.setitem(runner.HANDLERS, recheck.DESK_TEXT_RECHECK, lambda conn, payload: None)
    assert recheck._start_desk_texts(cast(Any, None)) is True
    assert queued == [(recheck.DESK_TEXT_RECHECK, recheck.DESK_TEXT_RECHECK)]
