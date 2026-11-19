"""DEC-118 without a database (lane C, BLD-C195 to BLD-C197): the worker's `ready` asks only for the minimum and for
no run still building; New business suggests "A new business idea"; the fake route's sentence leaves the area
waiting. Synthetic text only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from draft import runs
from gateway import fakes
from gateway.fakes import NO_AREA_SENTENCE
from submit import sorting


@dataclass(frozen=True)
class _Rules:
    min_chars_to_check: int = 30
    run_stale_seconds: int = 120


class _Result:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self.row = row

    def fetchone(self) -> dict[str, Any] | None:
        return self.row


class _Conn:
    """The two reads `ready` makes: the idea's character count, then any part a live run is still building."""

    def __init__(self, chars: int | None, building: bool) -> None:
        self.chars, self.building = chars, building
        self.sql: list[str] = []

    def execute(self, sql: str, params: Any = None) -> _Result:
        self.sql.append(sql)
        if "FROM ideas" in sql:
            return _Result(None if self.chars is None else {"char_count": self.chars})
        assert "p.state = 'updating'" in sql and "r.state = 'running'" in sql and "started_at" in sql
        return _Result({"?column?": 1} if self.building else None)


@pytest.fixture(autouse=True)
def _rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runs, "rules", lambda: _Rules())


@pytest.mark.parametrize(
    ("chars", "building", "ready"),
    [
        (None, False, False),  # no such draft
        (0, False, False),
        (29, False, False),  # below the minimum: "Your draft needs a little more first."
        (30, True, False),  # at the minimum, a run building: "Still working through your words."
        (30, False, True),  # at the minimum, nothing building: whatever title, summary and area hold
        (480, False, True),
    ],
)
def test_v_acc_s04_dec118_ready_is_the_minimum_and_nothing_building(
    chars: int | None, building: bool, ready: bool
) -> None:
    conn = _Conn(chars, building)
    assert runs.ready(conn, "idea-1") is ready  # type: ignore[arg-type]
    # Below the minimum it never asks about runs; title, summary and area are never read.
    assert len(conn.sql) == (2 if chars is not None and chars >= 30 else 1)
    assert not any("value" in s for s in conn.sql)


def test_l_sort_dec118_bld_c196_new_business_suggests_a_new_business_idea() -> None:
    assert sorting.kind_for_area("New business") == "business_idea"
    assert sorting.kind_for_area("new business") == "business_idea"
    assert sorting.kind_for_area("Operations") == "problem"
    assert sorting.kind_for_area(None) == "problem"
    # The line is the kind's existing one; DEC-118 adds no words.
    assert sorting.KIND_WHY["business_idea"] == "because you described something new KFintech could offer."
    # A kind the person set wins over the area's suggestion.
    assert sorting.kind_on_check_it("problem") == "problem"


def _area(words: list[str]) -> dict[str, Any]:
    from draft.config import DEFAULT_DRAFTING

    spec: Any = None
    choices = [{"label": o["label"], "cues": o["cues"]} for o in DEFAULT_DRAFTING["area"]]
    said = [{"n": i + 1, "text": t} for i, t in enumerate(words)]
    return fakes.draft_part(spec, {"part": "area", "words": said, "options": {"choices": choices}})


def test_v_acc_s04_dec118_bld_c197_the_fake_sentence_leaves_the_area_waiting() -> None:
    assert len(NO_AREA_SENTENCE) >= 30  # at least the minimum to check
    assert _area([NO_AREA_SENTENCE])["area"] is None
    # Whatever else is said, the sentence keeps the area empty, in any case and spacing.
    assert _area(["Investors call the branch about the SMS.", NO_AREA_SENTENCE.upper()])["area"] is None
    assert _area(["  ".join(NO_AREA_SENTENCE.split(" "))])["area"] is None
    # Without it, the cues still pick an area as before.
    assert _area(["Investors call the branch about the SMS they get."])["area"] == "Investor service"


def test_v_acc_s04_dec118_bld_c197_the_fake_sentence_still_gives_a_title_and_summary() -> None:
    spec: Any = None
    out = fakes.draft_part(spec, {"part": "title", "words": [{"n": 1, "text": NO_AREA_SENTENCE}]})
    assert out["title"] == "Visitors wait at reception because no meeting room shows as free"
    assert out["summary"] == NO_AREA_SENTENCE
    assert out["evidence"]


def test_v_acc_s04_dec118_bld_c197_the_rule_lives_only_on_the_fake_route() -> None:
    """Only `FakeRoute` (LLM_MODE=fake) imports `gateway.fakes`; the Anthropic and Bedrock routes never reach it."""
    import inspect

    from gateway import routes

    source = inspect.getsource(routes)
    assert source.count("from gateway import fakes") == 1
    assert "from gateway import fakes" in inspect.getsource(routes.FakeRoute.call)
