"""DEC-096: the speech golden set parses, holds synthetic scripts only, and its judge names expectations, not text."""

from __future__ import annotations

import pytest

from evalrunner import speech
from pii.patterns import scan


def test_every_case_is_well_formed_and_synthetic() -> None:
    cases = speech.cases()
    assert len({c["id"] for c in cases}) == len(cases) >= 6
    for c in cases:
        assert c["language"] and c["script"] and c["expected"]["contains"]
        # Identifiers are spoken in words, never written: the file itself holds no value a pattern blocks.
        assert not [m for m in scan(c["script"]) if m.action == "block"], c["id"]


def test_the_judge_passes_and_fails_without_quoting_the_text() -> None:
    case = {"expected": {"contains": ["keyed twice"], "left_out_at_least": 1}}
    assert speech.judge(case, "It was Keyed Twice. [PAN left out]", 1) == []
    problems = speech.judge(case, "nothing useful", 0)
    assert problems == ["missing expected phrase 1", "left out 0, expected at least 1"]


def test_it_only_runs_where_the_engine_is(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.config import get_settings

    monkeypatch.setenv("SPEECH_MODE", "fake")
    get_settings.cache_clear()
    try:
        assert speech.run() == 0
    finally:
        get_settings.cache_clear()
