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
