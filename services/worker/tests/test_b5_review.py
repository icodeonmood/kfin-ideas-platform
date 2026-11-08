"""Regression tests from the B5 review (BLD-086): refs number only shown cards and follow live visibility;
choices respect `matching.show`, refuse your own idea and second joins; after a save or withdraw the view is
final and confirm is refused; edits and choice text that the gatekeeper blocks are refused; colleague counts are
distinct people; working days from a weekend start; unknown visibility fails closed."""

from __future__ import annotations

import datetime as dt
import random
from typing import Any
from zoneinfo import ZoneInfo

import generators as g
import pytest

from core import killswitch
from scan import pipeline, save
from scan.confirm import ConfirmRefused, confirm
from scan.matching import _colleagues, shown
from scan.view import view
from sla.calendar import add_working_days
from tests.conftest import MATCH_TEXT as TEXT
from tests.test_b4_scan import canvas, submitted

pytestmark = pytest.mark.stack
CODE = "CTR-0a1b2c"


def ready(db: Any, suffix: str, code: str = CODE) -> tuple[str, str]:
    idea = submitted(db, canvas(TEXT + suffix + "."))
    if code != CODE:
        db.execute("UPDATE ideas SET contributor_code = %s WHERE id = %s", (code, idea))
    assert pipeline.run(db, idea) == "done"
    return idea, db.execute("SELECT idea_id FROM ideas WHERE id = %s", (idea,)).fetchone()["idea_id"]


def test_refs_number_only_shown_cards_and_follow_live_visibility(world: Any) -> None:
    db = world
    idea, _ = ready(db, " (r1)")
    result = pipeline.load_result(db.execute("SELECT * FROM scans WHERE idea_uuid = %s", (idea,)).fetchone())
    items, with_desk = shown(db, result["match"])
    refs = [r for r, _c, _row in items]
    assert with_desk and len(set(refs)) == len(refs) and all(len(r) == 11 and r.startswith("m") for r in refs)
    assert "IDEA" not in "".join(refs)
    db.execute("UPDATE repo_files SET visibility = 'committee' WHERE kfin_id = 'IDEA-2026-000011'")
    items_after, _ = shown(db, result["match"])
    assert "IDEA-2026-000011" not in {
        c["cid"] for _r, c, _row in items_after
    }  # hidden at once, not at next scan


def test_choices_respect_the_switch_own_ideas_and_second_joins(world: Any) -> None:
    db = world
    idea, idea_id = ready(db, " (r2)")
    confirm(db, idea, idea_id, {})
    refs = {c["kind"]: c["ref"] for c in view(db, idea, "real")["ready"]["matches"] if c["ref"]}
    killswitch.set_switch(db, "matching.show", "off", reason="Testing the matching switch", actor="REV-0001")
    killswitch.clear_cache()
    with pytest.raises(save.SaveRefused) as hidden:
        save.save(db, idea, CODE, {"choice": "plus_one", "ref": refs["idea"]})
    assert hidden.value.code == "match_required"
    assert view(db, idea, "real")["ready"]["matches_hidden"] is True
    killswitch.set_switch(db, "matching.show", "on", reason="Testing the matching switch", actor="REV-0001")
    killswitch.clear_cache()

    db.execute(
        "INSERT INTO idea_links (idea_id, contributor_code, link_type) VALUES ('IDEA-2026-000011', %s, 'originator')",
        (CODE,),
    )
    with pytest.raises(save.SaveRefused) as own:
        save.save(db, idea, CODE, {"choice": "plus_one", "ref": refs["idea"]})
    assert own.value.code == "match_required"  # own ideas are not shown, so their ref no longer matches
    shown_now = view(db, idea, "real")
    assert shown_now is not None and all(c["kind"] != "idea" for c in shown_now["ready"]["matches"])

    other = "CTR-0d0e0f"
    idea2, idea2_id = ready(db, " (r3)", code=other)
    confirm(db, idea2, idea2_id, {})
    refs2 = {c["kind"]: c["ref"] for c in view(db, idea2, "real")["ready"]["matches"] if c["ref"]}
    db.execute(
        "INSERT INTO idea_links (idea_id, contributor_code, link_type) VALUES ('IDEA-2026-000011', %s, 'plus_one')",
        (other,),
    )
    with pytest.raises(save.SaveRefused) as again:
        save.save(db, idea2, other, {"choice": "plus_one", "ref": refs2["idea"]})
    assert again.value.code == "match_required"  # already on it: no longer offered (and refused if raced)
    assert _colleagues(db, "IDEA-2026-000011", "idea") == 2  # the originator and one distinct colleague


def test_after_withdraw_or_save_the_view_is_final_and_confirm_is_refused(world: Any) -> None:
    db = world
    idea, idea_id = ready(db, " (r4)")
    save.save(db, idea, CODE, {"choice": "withdraw"})
    shown_view = view(db, idea, "real")
    assert shown_view is not None and shown_view["final"] == "withdrawn" and "ready" not in shown_view
    with pytest.raises(ConfirmRefused):
        confirm(db, idea, idea_id, {})


def test_blocked_edits_and_choice_text_are_refused(world: Any) -> None:
    db = world
    idea, idea_id = ready(db, " (r5)")
    name = g.person_name(random.Random(201))
    with pytest.raises(ConfirmRefused) as edit:
        confirm(
            db,
            idea,
            idea_id,
            {"details": f"{TEXT}. The investor {name} has complained about this twice now."},
        )
    assert edit.value.code == "personal_data"
    confirm(db, idea, idea_id, {})
    refs = {c["kind"]: c["ref"] for c in view(db, idea, "real")["ready"]["matches"] if c["ref"]}
    with pytest.raises(save.SaveRefused) as joined:
        save.save(
            db,
            idea,
            CODE,
            {"choice": "different", "ref": refs["idea"], "text": f"Mine is about the investor {name} only"},
        )
    assert joined.value.code == "personal_data"


def test_working_days_from_a_weekend_start() -> None:
    ist = ZoneInfo("Asia/Kolkata")
    saturday = dt.datetime(2026, 11, 14, 10, 0, tzinfo=ist)
    assert add_working_days(saturday, 5).date() == dt.date(2026, 11, 23)  # counted from Monday 16th
    friday = dt.datetime(2026, 11, 20, 10, 0, tzinfo=ist)
    assert add_working_days(friday, 1).date() == dt.date(2026, 11, 23)
