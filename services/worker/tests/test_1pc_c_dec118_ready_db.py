"""DEC-118 against a freshly migrated database (lane C, BLD-C195 to BLD-C197): "Move to Review" turns on once the
words reach the minimum to check and no run is still building, whatever the title, summary and area hold; a run that
failed or timed out counts as finished. The sorting suggests "A new business idea" for an area of New business while
the person has not set the kind. Synthetic text only; the fake model route."""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from psycopg.types.json import Jsonb

from core import killswitch
from core.config import get_settings
from core.db import connect
from draft import runs, store
from draft.config import rules
from draft.store import Device, Owner
from gateway import AgentFailed, limits
from gateway.fakes import NO_AREA_SENTENCE
from gateway.routes import FAKE_SCRIPT
from submit import sorting
from tests import helpers

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
LAPTOP = Device("laptop", "laptop-device-0118")
WORDS = "The shared printer on the third floor jams every morning, so people walk to the fourth floor."
SHORT = "The printer jams."  # below the minimum to check (V-FIELDS.tellit/1)
READY_LINE = "Your draft is ready. Add a detail, or check it."


@pytest.fixture
def drafting(db: Any, test_database: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Any, Owner]]:
    monkeypatch.setenv("COMPANY_REPO_PATH", str(SEED))
    get_settings.cache_clear()
    killswitch.clear_cache()
    limits.reset()
    FAKE_SCRIPT.clear()
    monkeypatch.setattr(runs, "_open", lambda: connect(helpers.db_url(test_database), autocommit=True))
    runs._means_cache.update(at=0.0, means=None)
    run = uuid.uuid4().hex[:6]
    uid = db.execute(
        "INSERT INTO users (emp_id_hash, name, email, first_name) VALUES (%s, 'Synthetic Sharer', %s, 'Synthetic') "
        "RETURNING id",
        (f"h-dec118-{run}", f"sharer.{run}@kfintech.example"),
    ).fetchone()["id"]
    code = f"CTR-{run}"
    db.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, uid))
    yield db, Owner(str(uid), code)
    killswitch.clear_cache()
    get_settings.cache_clear()


def _switch(db: Any, name: str, state: str) -> None:
    db.execute("UPDATE kill_switches SET state = %s WHERE name = %s", (state, name))
    killswitch.clear_cache()


def _states(db: Any, idea: str) -> dict[str, str]:
    rows = db.execute("SELECT key, state FROM idea_parts WHERE idea_uuid = %s", (idea,)).fetchall()
    return {str(r["key"]): str(r["state"]) for r in rows}


def _run_row(db: Any, run_id: str) -> dict[str, Any]:
    return dict(
        db.execute("SELECT state, ready, receipt FROM draft_runs WHERE id = %s", (run_id,)).fetchone()
    )


# ---- the rule: the minimum, and nothing building -----------------------------------------------------------------


def test_v_acc_s04_dec118_below_the_minimum_is_not_ready(drafting: Any) -> None:
    db, owner = drafting
    assert len(SHORT) < rules().min_chars_to_check
    idea, run_id = store.create(db, owner, LAPTOP, text=SHORT)
    assert run_id is None  # below where parts form: nothing builds, and still not ready
    assert runs.ready(db, idea) is False
    assert store.view(db, owner, idea, LAPTOP)["ready"] is False


def test_v_acc_s04_dec118_at_the_minimum_with_a_run_building_is_not_ready(drafting: Any) -> None:
    db, owner = drafting
    idea, run_id = store.create(db, owner, LAPTOP, text=WORDS)
    assert run_id is not None and "updating" in _states(db, idea).values()
    assert runs.ready(db, idea) is False
    assert store.view(db, owner, idea, LAPTOP)["ready"] is False


def test_v_acc_s04_dec118_a_failed_run_counts_as_finished(
    drafting: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run that crashed is marked failed and its parts settle; one whose settling never happened (the parts left
    `updating` under a failed run) holds nothing either."""
    db, owner = drafting
    idea, run_id = store.create(db, owner, LAPTOP, text=WORDS)
    assert run_id is not None
    db.execute("UPDATE draft_runs SET state = 'failed', finished_at = now() WHERE id = %s", (run_id,))
    assert "updating" in _states(db, idea).values()
    assert runs.ready(db, idea) is True
    live = store.live(db, owner, idea, run_id)
    assert live["run"]["state"] == "failed" and live["run"]["ready"] is True

    other, second = store.create(db, owner, LAPTOP, text=WORDS)

    def crash(_run_id: str) -> None:
        raise RuntimeError("synthetic crash")

    monkeypatch.setattr(runs, "execute", crash)
    runs._safe_execute(str(second))
    assert _run_row(db, str(second))["state"] == "failed"
    assert "updating" not in _states(db, other).values()
    assert runs.ready(db, other) is True
    assert store.view(db, owner, other, LAPTOP)["ready"] is True


def test_v_acc_s04_dec118_a_timed_out_run_counts_as_finished(
    drafting: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Past `run_stale_seconds` a run still marked running holds nothing, even before a read settles it; and a run
    whose parts never answer inside its own time limit settles them and finishes ready."""
    db, owner = drafting
    idea, run_id = store.create(db, owner, LAPTOP, text=WORDS)
    db.execute(
        "UPDATE draft_runs SET started_at = now() - make_interval(secs => %s) WHERE id = %s",
        (rules().run_stale_seconds + 5, run_id),
    )
    assert "updating" in _states(db, idea).values()
    assert runs.ready(db, idea) is True
    assert store.view(db, owner, idea, LAPTOP)["ready"] is True  # the read settles it
    assert "updating" not in _states(db, idea).values()

    other, second = store.create(db, owner, LAPTOP, text=WORDS)
    monkeypatch.setattr(runs, "RUN_TIMEOUT_S", 0.05)
    monkeypatch.setattr(runs, "_run_part", lambda *_a: time.sleep(0.4))
    runs.execute(str(second))
    row = _run_row(db, str(second))
    assert row["state"] == "done" and row["ready"] is True
    assert "updating" not in _states(db, other).values()
    assert store.view(db, owner, other, LAPTOP)["ready"] is True


def test_v_acc_s04_dec118_the_streams_ready_follows_the_rule_for_a_done_run_too(drafting: Any) -> None:
    """A done run whose stored `ready` is false (written before DEC-118, or while a newer run was building) reads as
    the rule stands now: the words at the minimum and nothing building."""
    db, owner = drafting
    _switch(db, "ai.all", "off")
    idea, run_id = store.create(db, owner, LAPTOP, text=WORDS)
    assert run_id is not None
    runs.execute(run_id)
    db.execute("UPDATE draft_runs SET ready = false WHERE id = %s", (run_id,))
    row = _run_row(db, run_id)
    assert row["state"] == "done" and row["ready"] is False
    live = store.live(db, owner, idea, run_id)
    assert live["run"]["state"] == "done" and live["run"]["ready"] is True


def test_v_acc_s04_dec118_title_summary_and_area_all_empty_is_ready(drafting: Any) -> None:
    db, owner = drafting
    _switch(db, "ai.all", "off")  # DEC-105: nothing is built, every part waits for the person
    idea, run_id = store.create(db, owner, LAPTOP, text=WORDS)
    assert run_id is not None
    runs.execute(run_id)  # similar ideas still look; the agent parts settled at once
    assert _run_row(db, run_id)["state"] == "done"
    draft = store.view(db, owner, idea, LAPTOP)
    assert draft["parts"]["title"]["value"] in (None, "")
    assert draft["parts"]["summary"]["value"] in (None, "")
    assert draft["parts"]["area"]["value"] in (None, "")
    assert draft["ready"] is True and runs.ready(db, idea) is True


def test_v_acc_s04_dec118_all_parts_failing_never_says_ready_beside_couldnt_build(
    drafting: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, owner = drafting

    def refuse(*_a: Any, **_k: Any) -> Any:
        raise AgentFailed("synthetic_failure")

    monkeypatch.setattr(runs, "run_agent", refuse)
    _idea, run_id = store.create(db, owner, LAPTOP, text=WORDS)
    assert run_id is not None
    runs.execute(run_id)
    row = _run_row(db, run_id)
    assert row["ready"] is True  # Move to Review is on: Check it fills the parts
    assert "We couldn't build the draft just now. Your words are saved. Try again." in row["receipt"]
    assert READY_LINE not in row["receipt"]


# ---- BLD-C197: the fake route's sentence that leaves the area waiting (J-SHARE/v3) --------------------------------


def test_v_acc_s04_dec118_bld_c197_the_fake_sentence_fills_title_and_summary_and_leaves_the_area_waiting(
    drafting: Any,
) -> None:
    db, owner = drafting
    assert get_settings().llm_mode == "fake"
    idea, run_id = store.create(db, owner, LAPTOP, text=NO_AREA_SENTENCE)
    assert run_id is not None
    runs.execute(run_id)
    draft = store.view(db, owner, idea, LAPTOP)
    assert draft["parts"]["title"]["state"] == "filled" and draft["parts"]["title"]["value"]
    assert draft["parts"]["summary"]["state"] == "filled" and draft["parts"]["summary"]["value"]
    assert draft["parts"]["area"]["state"] == "waiting" and not draft["parts"]["area"]["value"]
    assert draft["hidden"] == []  # nothing personal in it
    assert draft["ready"] is True and _run_row(db, run_id)["ready"] is True
    assert READY_LINE in _run_row(db, run_id)["receipt"]
    v = sorting.read_draft(db, idea, owner.user_id)
    assert v["area"] == {"value": None, "source": "suggested", "why": None, "why_line": None}
    assert v["complete"] is False


# ---- BLD-C196: New business suggests "A new business idea" ---------------------------------------------------------


def _draft_with_area(db: Any, owner: Owner, area: str | None) -> str:
    row = db.execute(
        "INSERT INTO ideas (contributor_code, status, channel, char_count) VALUES (%s, 'draft', 'web', 120) "
        "RETURNING id",
        (owner.code,),
    ).fetchone()
    idea = str(row["id"])
    parts: dict[str, tuple[Any, str | None]] = {
        "title": (
            {"title": "A desk booking service for visiting partners", "summary": "Sell it as a service."},
            None,
        ),
        "who": (["KFin teams"], "because you mentioned the team"),
        "value": (["earns_revenue"], "because you said sell it"),
    }
    if area is not None:
        parts["area"] = (area, "because it’s about a new offering")
    for key, (value, why) in parts.items():
        db.execute(
            "INSERT INTO idea_parts (idea_uuid, key, state, value, why) VALUES (%s, %s, 'filled', %s, %s)",
            (idea, key, Jsonb(value), why),
        )
    return idea


def test_l_sort_dec118_bld_c196_new_business_with_no_kind_suggests_a_new_business_idea(drafting: Any) -> None:
    db, owner = drafting
    idea = _draft_with_area(db, owner, "New business")
    v = sorting.read_draft(db, idea, owner.user_id)
    assert v["kind"] == {
        "value": "business_idea",
        "source": "suggested",
        "why": sorting.KIND_WHY["business_idea"],
        "why_line": "Suggested because you described something new KFintech could offer.",
    }
    confirmed = sorting.update_draft(db, idea, owner.user_id, {"confirm": True}, now=_now(db))
    assert confirmed["kind"]["value"] == "business_idea" and confirmed["kind"]["source"] == "confirmed"


def test_l_sort_dec118_bld_c196_a_kind_the_person_set_is_untouched(drafting: Any) -> None:
    db, owner = drafting
    idea = _draft_with_area(db, owner, "New business")
    v = sorting.update_draft(db, idea, owner.user_id, {"kind": "problem"}, now=_now(db))
    assert v["kind"] == {"value": "problem", "source": "changed", "why": None, "why_line": None}
    # Confirmed as a problem while the area said something else, then the area becomes New business: still a problem.
    other = _draft_with_area(db, owner, "Operations")
    sorting.update_draft(db, other, owner.user_id, {"confirm": True}, now=_now(db))
    db.execute(
        "UPDATE idea_parts SET value = %s WHERE idea_uuid = %s AND key = 'area'",
        (Jsonb("New business"), other),
    )
    v = sorting.read_draft(db, other, owner.user_id)
    assert v["kind"]["value"] == "problem" and v["kind"]["source"] == "confirmed"


@pytest.mark.parametrize("area", ["Operations", "Sales", None])
def test_l_sort_dec118_bld_c196_any_other_area_keeps_a_problem_to_fix(
    drafting: Any, area: str | None
) -> None:
    db, owner = drafting
    idea = _draft_with_area(db, owner, area)
    v = sorting.read_draft(db, idea, owner.user_id)
    assert v["kind"]["value"] == "problem"
    assert v["kind"]["why_line"] == "Suggested because you described something that goes wrong today."


def _now(db: Any) -> Any:
    return db.execute("SELECT now() AS t").fetchone()["t"]
