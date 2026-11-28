"""Suggestion outcomes against a freshly migrated database (lane C, DEC-122, BLD-C207 to BLD-C209), on the fake model
route: the switch starts off, audited; with it on, a part the person sets in their own words or asks to have suggested
again, and a sorting field confirmed or changed, keep the assistant's suggestion beside what became of it; nothing
is kept with the switch off, in Capture first (ai.all off, DEC-125, the r7 launch state, DEC-141), or for a value
that was never the assistant's. Synthetic text only."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core import killswitch
from core.config import get_settings
from core.db import connect
from draft import outcomes, runs, store
from draft.store import Device, Owner
from gateway import limits
from gateway.fakes import BUSINESS_SENTENCE
from gateway.routes import FAKE_SCRIPT
from gateway.spec import load
from submit import sorting
from tests import helpers

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
MIGRATION = (
    Path(__file__).resolve().parents[3] / "db" / "migrations" / "20261122300900_suggestion_outcomes.sql"
)
LAPTOP = Device("laptop", "laptop-device-0207")


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
        (f"h-c207-{run}", f"sharer.{run}@kfintech.example"),
    ).fetchone()["id"]
    code = f"CTR-{run}"
    db.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, uid))
    yield db, Owner(str(uid), code)
    FAKE_SCRIPT.clear()
    killswitch.clear_cache()
    get_settings.cache_clear()


def _switch(db: Any, name: str, state: str) -> None:
    db.execute("UPDATE kill_switches SET state = %s WHERE name = %s", (state, name))
    killswitch.clear_cache()


def _told(db: Any, owner: Owner, text: str) -> str:
    idea, run_id = store.create(db, owner, LAPTOP, text=text)
    assert run_id is not None
    runs.execute(run_id)
    return idea


def _patch(db: Any, owner: Owner, idea: str, body: dict[str, Any]) -> dict[str, Any]:
    now = db.execute("SELECT now() AS t").fetchone()["t"]
    return sorting.update_draft(db, idea, owner.user_id, body, now=now)


def _rows(db: Any, idea: str) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in db.execute(
            "SELECT field, suggested, final, outcome, agent, agent_version, run_id, side FROM suggestion_outcomes "
            "WHERE idea_uuid = %s ORDER BY id",
            (idea,),
        ).fetchall()
    ]


def _title(db: Any, idea: str) -> dict[str, Any]:
    row = db.execute(
        "SELECT value, run_id FROM idea_parts WHERE idea_uuid = %s AND key = 'title'", (idea,)
    ).fetchone()
    return dict(row)


# ---- BLD-C207: the table and its switch ------------------------------------------------------------------------------


def test_dec122_bld_c207_the_switch_starts_off_and_its_start_is_audited(drafting: Any) -> None:
    db, _owner = drafting
    sql = MIGRATION.read_text("utf-8")
    assert "VALUES ('learning.outcomes', 'off'," in sql
    audit = db.execute(
        "SELECT actor, after, reason FROM audit_log WHERE action = 'kill_switch.set' "
        "AND entity = 'kill_switch:learning.outcomes' ORDER BY id LIMIT 1"
    ).fetchone()
    assert audit["actor"] == "migration" and audit["after"] == {"state": "off"}
    assert audit["reason"] == "Off until the privacy notice names this purpose (DEC-122)"


def test_dec122_bld_c207_rows_go_with_the_idea(drafting: Any) -> None:
    db, owner = drafting
    idea = _told(db, owner, BUSINESS_SENTENCE)
    store.set_part(db, owner, idea, "title", LAPTOP, {"value": "Factsheet checks for small AMCs"})
    assert len(_rows(db, idea)) == 1
    db.execute("DELETE FROM ideas WHERE id = %s", (idea,))
    assert _rows(db, idea) == []


# ---- BLD-C208: draft parts ---------------------------------------------------------------------------------------


def test_dec122_bld_c208_a_part_set_in_the_persons_words_keeps_the_assistants_suggestion(
    drafting: Any,
) -> None:
    db, owner = drafting
    idea = _told(db, owner, BUSINESS_SENTENCE)
    before = _title(db, idea)
    suggested_title = before["value"]["title"]
    assert suggested_title and before["run_id"]
    store.set_part(db, owner, idea, "title", LAPTOP, {"value": "Factsheet checks for small AMCs"})
    (row,) = _rows(db, idea)
    assert row["field"] == "title" and row["outcome"] == "pinned" and row["side"] == "sharer"
    assert row["suggested"] == suggested_title and row["final"] == "Factsheet checks for small AMCs"
    assert row["agent"] == "draft-part" and row["agent_version"] == load("draft-part").version
    assert str(row["run_id"]) == str(before["run_id"])
    # The title is the person's now: setting it again keeps nothing more (it was never the assistant's).
    store.set_part(db, owner, idea, "title", LAPTOP, {"value": "Factsheet checks for AMCs"})
    assert len(_rows(db, idea)) == 1


def test_dec122_bld_c208_suggest_again_keeps_the_suggestion_with_nothing_chosen(drafting: Any) -> None:
    db, owner = drafting
    idea = _told(db, owner, BUSINESS_SENTENCE)
    suggested_title = _title(db, idea)["value"]["title"]
    run_id = store.set_part(db, owner, idea, "title", LAPTOP, {"pinned": False})
    assert run_id is not None
    (row,) = _rows(db, idea)
    assert row["field"] == "title" and row["outcome"] == "suggested_again"
    assert row["suggested"] == suggested_title and row["final"] is None


# ---- BLD-C209: the sorting -----------------------------------------------------------------------------------------


def test_dec122_bld_c209_confirming_keeps_each_suggestion_as_accepted(drafting: Any) -> None:
    db, owner = drafting
    idea = _told(db, owner, BUSINESS_SENTENCE)
    shown = sorting.read_draft(db, idea, owner.user_id)
    _patch(db, owner, idea, {"confirm": True})
    rows = {r["field"]: r for r in _rows(db, idea)}
    assert {"sorting.affects", "sorting.area", "sorting.kind"} <= set(rows)
    for field, row in rows.items():
        assert row["outcome"] == "accepted" and row["suggested"] == row["final"], field
    assert rows["sorting.kind"]["suggested"] == "business_idea" == shown["kind"]["value"]
    assert rows["sorting.area"]["suggested"] == "New business"
    # Confirmed once: confirming again keeps nothing more.
    _patch(db, owner, idea, {"confirm": True})
    assert len(_rows(db, idea)) == len(rows)


def test_dec122_bld_c209_a_change_keeps_the_suggestion_and_what_the_person_chose(drafting: Any) -> None:
    db, owner = drafting
    idea = _told(db, owner, BUSINESS_SENTENCE)
    _patch(db, owner, idea, {"area": "Operations"})
    (row,) = _rows(db, idea)
    assert row["field"] == "sorting.area" and row["outcome"] == "changed"
    assert row["suggested"] == "New business" and row["final"] == "Operations"


def test_dec122_bld_c209_new_business_by_hand_is_not_the_assistants_kind(drafting: Any) -> None:
    db, owner = drafting
    _switch(db, "ai.all", "off")  # nothing built: every sorting suggestion is a rule's, not the assistant's
    idea = _told(
        db, owner, "The shared printer on the third floor jams every morning, so people walk upstairs."
    )
    _switch(db, "ai.all", "on")
    _patch(db, owner, idea, {"area": "New business"})
    _patch(db, owner, idea, {"affects": ["AMC clients"], "brings": ["earns_revenue"], "confirm": True})
    assert _rows(db, idea) == []


# ---- nothing kept: switched off, Capture first --------------------------------------------------------------------


def test_dec122_bld_c207_nothing_is_kept_while_the_switch_is_off(drafting: Any) -> None:
    db, owner = drafting
    _switch(db, outcomes.SWITCH, "off")
    idea = _told(db, owner, BUSINESS_SENTENCE)
    store.set_part(db, owner, idea, "title", LAPTOP, {"value": "Factsheet checks for small AMCs"})
    _patch(db, owner, idea, {"area": "Operations"})
    _patch(db, owner, idea, {"confirm": True})
    assert _rows(db, idea) == []


def test_dec141_dec125_bld_c207_capture_first_keeps_nothing_and_asks_no_model(
    drafting: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """r7 launches with the assistant off (DEC-141): with the switch on, nothing the person does is a suggestion of
    the assistant's, so nothing is kept, and no path asks the gateway."""
    db, owner = drafting
    _switch(db, "ai.all", "off")

    def no_gateway(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("a model was asked while ai.all is off")

    monkeypatch.setattr(runs, "run_agent", no_gateway)
    idea = _told(db, owner, BUSINESS_SENTENCE)
    store.set_part(db, owner, idea, "title", LAPTOP, {"value": "Factsheet checks for small AMCs"})
    _patch(db, owner, idea, {"area": "New business"})  # the only way to a business idea here (BLD-C204)
    _patch(db, owner, idea, {"affects": ["AMC clients"], "brings": ["earns_revenue"], "confirm": True})
    assert _rows(db, idea) == []
    assert db.execute("SELECT count(*) AS n FROM suggestion_outcomes").fetchone()["n"] == 0
    with pytest.raises(store.DraftError):
        store.set_part(db, owner, idea, "title", LAPTOP, {"pinned": False})  # 409 assistant_off, as before
    assert db.execute("SELECT count(*) AS n FROM suggestion_outcomes").fetchone()["n"] == 0


# ---- BLD-C250: the product lead's note of 26 Nov, item 4, and the C207-C209 review -----------------------------------


def test_bld_c250_a_pin_keeps_nothing_while_the_assistant_is_off(drafting: Any) -> None:
    """`learning.outcomes` on is not enough: with `ai.all` off, or `agent.draft-part` alone off (Capture first,
    DEC-143 (g)), a pin keeps nothing, even of a title a run filled while the assistant was on. The pin still goes."""
    db, owner = drafting
    idea = _told(db, owner, BUSINESS_SENTENCE)
    assert _title(db, idea)["run_id"] and outcomes.writing(db)
    for name in ("ai.all", "agent.draft-part"):
        _switch(db, name, "off")
        assert not outcomes.writing(db)
        store.set_part(
            db, owner, idea, "summary", LAPTOP, {"value": f"Checks before each factsheet ({name})"}
        )
        assert _title(db, idea)["value"]["summary"] == f"Checks before each factsheet ({name})"
        _switch(db, name, "on")
    assert _rows(db, idea) == []


def test_bld_c250_only_a_run_where_the_agent_answered_on_the_part_counts(drafting: Any) -> None:
    """Item 4: a row only when the suggested value came from an agent answer on that part. A run begun with the
    assistant off takes the parts over and leaves them showing what they had, with 0 in its `part_ms`: a pin or a
    sorting change after it keeps nothing, while the same on the run that answered keeps its row."""
    db, owner = drafting
    idea = _told(db, owner, BUSINESS_SENTENCE)
    first = str(_title(db, idea)["run_id"])
    assert outcomes.answered(db, first, "title")
    _switch(db, "ai.all", "off")
    later = runs.begin(db, idea, trigger="retry", only=["title", "area"])  # no similar ideas: it ends at once
    _switch(db, "ai.all", "on")
    assert later is not None and str(_title(db, idea)["run_id"]) == later
    assert not outcomes.answered(db, later, "title") and not outcomes.answered(db, later, "area")
    shown = _title(db, idea)["value"]["title"]
    assert shown  # the title still shows the first run's answer, now on a run that did not answer
    store.set_part(db, owner, idea, "title", LAPTOP, {"value": "Factsheet checks for small AMCs"})
    _patch(db, owner, idea, {"area": "Operations"})
    assert _rows(db, idea) == []


def test_bld_c250_a_write_that_fails_never_blocks_the_pin_or_the_confirm(
    drafting: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row is written in its own savepoint: one the table refuses (here an agent version its check does not
    allow) is skipped, and the person's pin and confirm go through as if nothing were kept."""
    db, owner = drafting
    monkeypatch.setattr(outcomes, "_version", lambda: "not a version!")
    idea = _told(db, owner, BUSINESS_SENTENCE)
    store.set_part(db, owner, idea, "title", LAPTOP, {"value": "Factsheet checks for small AMCs"})
    assert _title(db, idea)["value"]["title"] == "Factsheet checks for small AMCs"
    out = _patch(db, owner, idea, {"confirm": True})
    assert all(out[f]["source"] == "confirmed" for f in ("area", "kind"))
    assert _rows(db, idea) == []


def test_bld_c250_an_unknown_field_outcome_or_side_is_a_value_error() -> None:
    """A caller's mistake, raised before anything is read (it was an assert, gone under `python -O`)."""
    nothing: Any = None
    for bad in ({"field": "similar"}, {"outcome": "kept"}, {"side": "committee"}):
        args: dict[str, Any] = {"field": "title", "outcome": "pinned", "side": "sharer", **bad}
        with pytest.raises(ValueError):
            outcomes.record(
                nothing,
                str(uuid.uuid4()),
                args["field"],
                suggested="A title",
                final=None,
                outcome=args["outcome"],
                run_id=None,
                side=args["side"],
            )
