"""Business ideas against a freshly migrated database (lane C, BLD-C201 to BLD-C206), on the fake model route: the
draft-part agent's kind lands with the title and is the sorting's suggestion while the person has not set or
confirmed one; New business picked by hand suggests a business idea and moving away undoes only that; a kind the
person set or confirmed is never touched; the next prompts follow the kind the sorting shows; a kind the checks drop
leaves the title landing. Synthetic text only."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core import killswitch
from core.config import get_settings
from core.db import connect
from draft import parts, runs, store
from draft.store import Device, Owner
from gateway import limits
from gateway.core import DROPPED
from gateway.fakes import BUSINESS_SENTENCE
from gateway.routes import FAKE_SCRIPT
from submit import sorting
from tests import helpers

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
LAPTOP = Device("laptop", "laptop-device-0201")
PROBLEM = "The shared printer on the third floor jams every morning, so people walk to the fourth floor."
QUOTE_LINE = "Suggested because you said “KFintech could offer small AMCs”."
PROBLEM_LINE = "Suggested because you described something that goes wrong today."
BUSINESS_LINE = "Suggested because you described something new KFintech could offer."


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
        (f"h-c201-{run}", f"sharer.{run}@kfintech.example"),
    ).fetchone()["id"]
    code = f"CTR-{run}"
    db.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, uid))
    yield db, Owner(str(uid), code)
    FAKE_SCRIPT.clear()
    killswitch.clear_cache()
    get_settings.cache_clear()


def _told(db: Any, owner: Owner, text: str) -> str:
    """A draft told in one message, its run built on the fake route."""
    assert get_settings().llm_mode == "fake"
    idea, run_id = store.create(db, owner, LAPTOP, text=text)
    assert run_id is not None
    runs.execute(run_id)
    return idea


def _title(db: Any, idea: str) -> dict[str, Any]:
    row = db.execute(
        "SELECT value FROM idea_parts WHERE idea_uuid = %s AND key = 'title'", (idea,)
    ).fetchone()
    value: dict[str, Any] = row["value"]
    return value


def _now(db: Any) -> Any:
    return db.execute("SELECT now() AS t").fetchone()["t"]


def _patch(db: Any, owner: Owner, idea: str, body: dict[str, Any]) -> dict[str, Any]:
    return sorting.update_draft(db, idea, owner.user_id, body, now=_now(db))


# ---- BLD-C201, BLD-C206: the agent's kind is the suggestion -------------------------------------------------------


def test_l_sort_bld_c201_c206_a_business_idea_is_suggested_with_its_quote(drafting: Any) -> None:
    db, owner = drafting
    idea = _told(db, owner, BUSINESS_SENTENCE)
    title = _title(db, idea)
    assert title["kind"] == "business_idea" and title["kind_quote"] == "KFintech could offer small AMCs"
    v = sorting.read_draft(db, idea, owner.user_id)
    assert v["kind"]["value"] == "business_idea" and v["kind"]["source"] == "suggested"
    assert v["kind"]["why_line"] == QUOTE_LINE
    assert v["area"]["value"] == "New business"
    assert v["affects"]["value"] == ["AMC clients"]
    draft = store.view(db, owner, idea, LAPTOP)
    assert draft["sorting"]["kind"] == {"value": "business_idea", "source": "suggested"}
    # Next prompts for a business idea (BLD-C203): who it is for is known, so how many would use it comes first.
    assert draft["suggestions"] == ["Say how many would use it", "Add who offers it today"]
    # The draft's wire carries no kind of its own: the title and summary are as before.
    assert set(draft["parts"]["title"]) >= {"state", "value"} and "kind" not in draft["parts"]["title"]
    confirmed = _patch(db, owner, idea, {"confirm": True})
    assert confirmed["kind"]["value"] == "business_idea" and confirmed["kind"]["source"] == "confirmed"
    assert db.execute("SELECT kind FROM ideas WHERE id = %s", (idea,)).fetchone()["kind"] == "business_idea"


def test_l_sort_bld_c201_a_problem_keeps_the_drawn_line_and_todays_prompts(drafting: Any) -> None:
    db, owner = drafting
    idea = _told(db, owner, PROBLEM)
    assert _title(db, idea)["kind"] == "problem"
    v = sorting.read_draft(db, idea, owner.user_id)
    assert v["kind"]["value"] == "problem" and v["kind"]["why_line"] == PROBLEM_LINE
    draft = store.view(db, owner, idea, LAPTOP)
    assert draft["sorting"]["kind"]["value"] == "problem"
    assert draft["suggestions"] and not set(draft["suggestions"]) & set(parts.BUSINESS_PROMPTS.values())


def test_l_sort_bld_c201_a_kind_the_person_set_or_confirmed_is_never_replaced(drafting: Any) -> None:
    db, owner = drafting
    idea = _told(db, owner, BUSINESS_SENTENCE)
    v = _patch(db, owner, idea, {"kind": "problem"})
    assert v["kind"] == {"value": "problem", "source": "changed", "why": None, "why_line": None}
    # A later message rebuilds the title (and its kind): the person's call stands, and the prompts follow it.
    _, run_id = store.add_message(
        db, owner, idea, LAPTOP, text="It would help AMCs that have no checker today."
    )
    assert run_id is not None
    runs.execute(run_id)
    assert _title(db, idea)["kind"] == "business_idea"
    assert sorting.read_draft(db, idea, owner.user_id)["kind"]["value"] == "problem"
    draft = store.view(db, owner, idea, LAPTOP)
    assert draft["sorting"]["kind"] == {"value": "problem", "source": "changed"}
    assert not set(draft["suggestions"]) & set(parts.BUSINESS_PROMPTS.values())

    other = _told(db, owner, PROBLEM)
    _patch(db, owner, other, {"confirm": True})
    _patch(db, owner, other, {"area": "New business"})
    v = sorting.read_draft(db, other, owner.user_id)
    assert v["kind"]["value"] == "problem" and v["kind"]["source"] == "confirmed"


# ---- BLD-C204: New business picked by hand -------------------------------------------------------------------------


def test_v_acc_s05_bld_c204_new_business_by_hand_suggests_a_business_idea_and_moving_away_undoes_it(
    drafting: Any,
) -> None:
    db, owner = drafting
    idea = _told(db, owner, PROBLEM)
    assert sorting.read_draft(db, idea, owner.user_id)["kind"]["value"] == "problem"
    # "Another area? Search all N" and the radios send the same change.
    v = _patch(db, owner, idea, {"area": "New business"})
    assert v["area"]["value"] == "New business" and v["area"]["source"] == "changed"
    assert v["kind"] == {
        "value": "business_idea",
        "source": "suggested",
        "why": parts.KIND_WHY["business_idea"],
        "why_line": BUSINESS_LINE,
    }
    assert store.view(db, owner, idea, LAPTOP)["sorting"]["kind"]["value"] == "business_idea"
    # Moving away undoes only what the area suggested: the agent's problem, with its drawn line.
    v = _patch(db, owner, idea, {"area": "Operations"})
    assert v["kind"]["value"] == "problem" and v["kind"]["why_line"] == PROBLEM_LINE
    assert v["kind"]["source"] == "suggested"
    # Back to New business, then confirmed: a business idea, kept when the area moves again.
    _patch(db, owner, idea, {"area": "New business"})
    v = _patch(db, owner, idea, {"confirm": True})
    assert v["kind"]["value"] == "business_idea" and v["kind"]["source"] == "confirmed"
    v = _patch(db, owner, idea, {"area": "Operations"})
    assert v["kind"]["value"] == "business_idea" and v["kind"]["source"] == "confirmed"


def test_v_acc_s05_bld_c204_the_area_and_the_kind_in_one_change(drafting: Any) -> None:
    db, owner = drafting
    idea = _told(db, owner, PROBLEM)
    # The kind's suggestion follows the area sent with it: choosing it confirms, it does not change.
    v = _patch(db, owner, idea, {"area": "New business", "kind": "business_idea"})
    assert v["kind"]["value"] == "business_idea" and v["kind"]["source"] == "confirmed"
    other = _told(db, owner, PROBLEM)
    v = _patch(db, owner, other, {"area": "New business", "confirm": True})
    assert v["kind"]["value"] == "business_idea" and v["kind"]["source"] == "confirmed"


def test_v_acc_s05_bld_c204_moving_away_keeps_the_agents_business_idea(drafting: Any) -> None:
    db, owner = drafting
    idea = _told(db, owner, BUSINESS_SENTENCE)
    v = _patch(db, owner, idea, {"area": "Operations"})
    assert v["kind"]["value"] == "business_idea" and v["kind"]["why_line"] == QUOTE_LINE


# ---- BLD-C201: the kind stays with a pinned title; a dropped kind leaves the title landing --------------------------


def test_l_draft_pins_bld_c201_pinning_the_title_keeps_the_agents_kind(drafting: Any) -> None:
    db, owner = drafting
    idea = _told(db, owner, BUSINESS_SENTENCE)
    store.set_part(db, owner, idea, "title", LAPTOP, {"value": "Factsheet checks for small AMCs"})
    store.set_part(db, owner, idea, "summary", LAPTOP, {"value": "A product that checks factsheets."})
    title = _title(db, idea)
    assert title["pinned"] == ["summary", "title"] and title["title"] == "Factsheet checks for small AMCs"
    assert title["kind"] == "business_idea" and title["kind_quote"] == "KFintech could offer small AMCs"
    assert sorting.read_draft(db, idea, owner.user_id)["kind"]["why_line"] == QUOTE_LINE


def test_l_draft_parts_bld_c201_a_kind_the_checks_drop_leaves_the_title_landing(drafting: Any) -> None:
    db, owner = drafting
    idea, run_id = store.create(db, owner, LAPTOP, text=PROBLEM)
    assert run_id is not None
    unbacked = {
        "part": "title", "title": "The shared printer jams every morning",
        "summary": "The shared printer on the third floor jams every morning.", "kind": "business_idea",
        "kind_evidence": "a printer repair service", "often": None, "who": [], "worth": [], "area": None,
        "reason": None, "evidence": ["The shared printer on the third floor jams every morning"],
    }  # fmt: skip
    FAKE_SCRIPT.extend([unbacked, unbacked])  # the first ask and the re-ask
    runs._run_part(run_id, idea, "title", runs.words(db, idea))
    assert not FAKE_SCRIPT
    row = db.execute(
        "SELECT state, value FROM idea_parts WHERE idea_uuid = %s AND key = 'title'", (idea,)
    ).fetchone()
    assert row["state"] == "filled"
    assert row["value"]["title"] == "The shared printer jams every morning"
    assert "kind" not in row["value"]
    call = db.execute(
        "SELECT outcome, error_code FROM llm_calls WHERE agent = 'draft-part' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert call["error_code"] == DROPPED
    # No kind from the agent: the area's rule, and here a problem to fix.
    assert sorting.read_draft(db, idea, owner.user_id)["kind"]["why_line"] == PROBLEM_LINE


# ---- DEC-141, DEC-125: Capture first, the r7 launch state (ai.all off until the model key) -----------------------


def _switch(db: Any, name: str, state: str) -> None:
    db.execute("UPDATE kill_switches SET state = %s WHERE name = %s", (state, name))
    killswitch.clear_cache()


def test_dec141_bld_c204_capture_first_offers_a_business_idea_only_when_picked_by_hand(
    drafting: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the assistant off (Capture first, DEC-125; r7 launches so, DEC-141) the draft-part agent never runs: no
    gateway call, no kind of its own, today's next prompts. The sorting offers "A new business idea" only when the
    person picks New business by hand (BLD-C204); moving away takes it back to a problem to fix."""
    db, owner = drafting
    _switch(db, "ai.all", "off")

    def no_gateway(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("draft-part asked the gateway while ai.all is off")

    monkeypatch.setattr(runs, "run_agent", no_gateway)
    idea = _told(db, owner, BUSINESS_SENTENCE)  # words that would be a business idea with the assistant on
    assert db.execute("SELECT count(*) AS n FROM llm_calls WHERE agent = 'draft-part'").fetchone()["n"] == 0
    row = db.execute(
        "SELECT value FROM idea_parts WHERE idea_uuid = %s AND key = 'title'", (idea,)
    ).fetchone()
    assert row is None or not (row["value"] or {}).get("kind")
    v = sorting.read_draft(db, idea, owner.user_id)
    assert v["kind"]["value"] == "problem" and v["kind"]["source"] == "suggested"
    draft = store.view(db, owner, idea, LAPTOP)
    assert draft["sorting"]["kind"]["value"] == "problem"
    assert not set(draft["suggestions"]) & set(parts.BUSINESS_PROMPTS.values())

    v = _patch(db, owner, idea, {"area": "New business"})
    assert v["kind"]["value"] == "business_idea" and v["kind"]["source"] == "suggested"
    assert v["kind"]["why_line"] == BUSINESS_LINE
    assert store.view(db, owner, idea, LAPTOP)["sorting"]["kind"]["value"] == "business_idea"
    v = _patch(db, owner, idea, {"area": "Operations"})
    assert v["kind"]["value"] == "problem" and v["kind"]["source"] == "suggested"
    v = _patch(db, owner, idea, {"area": "New business", "confirm": True})
    assert v["kind"]["value"] == "business_idea" and v["kind"]["source"] == "confirmed"
    assert db.execute("SELECT count(*) AS n FROM llm_calls WHERE agent = 'draft-part'").fetchone()["n"] == 0
