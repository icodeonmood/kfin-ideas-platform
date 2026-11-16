"""L-MERGE.desk, L-MERGE.effects and L-WORTH against the database (V-ACC.review/10, /12–14; C-SHEET-MERGE).

Needs Postgres with the handoff cut-over applied (`make up`, then the tests migrate their own database).
Every name and number here is invented (non-negotiable 11).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import committee, merging, revise
from desk.store import Refused, own_codes, unseal
from tests import desk_fixtures as f

NOTE = "You both found the same R07 calls in Hyderabad. One team, one fix, with both your names on it."


@pytest.fixture
def repo(company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    get_settings.cache_clear()
    yield company_repo
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def cast(db: Conn, repo: Path) -> dict[str, Any]:
    """Kavya's idea (Saturday 14 Nov) is under review; Ravi's (2 Nov) is the similar one, with a crew of four."""
    kavya, ravi = f.person(db, "Kavya Menon"), f.person(db, "Ravi Shankar")
    meera = f.person(db, "Meera Iyer", roles=("reviewer",))
    rohan = f.person(db, "Rohan Mehta", roles=("committee",))
    mine, theirs = f.idea(db, kavya, shared_at=f.at(14, 10)), f.idea(db, ravi, shared_at=f.at(2, 11))
    for name in ("Anil Kumar", "Divya Rao", "Suresh Pillai"):
        f.crew(db, theirs, f.person(db, name))
    return {"kavya": kavya, "ravi": ravi, "meera": meera, "rohan": rohan, "mine": mine, "theirs": theirs}


def _crew(db: Conn, idea_uuid: Any) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in db.execute(
            "SELECT contributor_code, role, via, merge_id, left_at, left_how FROM crew_members "
            "WHERE idea_uuid = %s ORDER BY id",
            (idea_uuid,),
        ).fetchall()
    ]


def _idea(db: Conn, idea_uuid: Any) -> dict[str, Any]:
    return dict(db.execute("SELECT * FROM ideas WHERE id = %s", (idea_uuid,)).fetchone() or {})


def _merge(db: Conn, c: dict[str, Any], t: dt.datetime, **body: Any) -> dict[str, Any]:
    sheet = merging.sheet_for(db, c["mine"]["idea_id"], c["theirs"]["idea_id"], c["meera"]["id"], t)
    body = {"other_idea_id": c["theirs"]["idea_id"], "lead": sheet["default_lead"], "note": NOTE, **body}
    return merging.desk_merge(db, c["mine"]["idea_id"], c["meera"]["id"], body, t)


# ---------------------------------------------------------------------------------------------------------------
# The merge sheet and the desk merge (L-MERGE.desk)
# ---------------------------------------------------------------------------------------------------------------


def test_C_SHEET_MERGE_anatomy_the_idea_shared_first_leads_by_default(db: Conn, cast: dict[str, Any]) -> None:
    ref, other = cast["mine"]["idea_id"], cast["theirs"]["idea_id"]
    s = merging.sheet_for(db, ref, other, cast["meera"]["id"], f.at(16, 10))
    assert s["default_lead"] == "other"
    assert s["title"] == f"Merge with {other}?"
    assert s["line"] == (
        "Kavya’s idea joins Ravi’s. Both stay credited, and from now on the review desk decides on one idea."
    )
    assert [(o["label"], o["meta"], o["selected"]) for o in s["options"]] == [
        (f"Kavya’s leads, {ref}", "Shared Saturday, just Kavya so far", False),
        (f"Ravi’s leads, {other}", "Shared 2 November, 4 on its crew", True),
    ]
    assert s["team_up"]["line"] == "Kavya joins Ravi’s crew without a request. Both are told why."
    assert s["by_lead"]["this"]["team_up"] == "Ravi joins Kavya’s crew without a request. Both are told why."
    assert s["small_print"] == (
        "Both get it in their Inbox. The Ones Committee sees the merge for 30 days and can reverse it."
    )
    assert (s["button"], s["note"]["min"], s["refusal"]) == (
        "Merge and tell both", 20, {"this": None, "other": None}
    )  # fmt: skip


def test_V_ACC_review_12_a_note_under_20_characters_merges_nothing(db: Conn, cast: dict[str, Any]) -> None:
    with pytest.raises(Refused) as refused:
        _merge(db, cast, f.at(16, 11), note="Same problem.")
    assert (refused.value.status, refused.value.code, refused.value.message, refused.value.field) == (
        422, "note_too_short", "Tell both why, in a line or two.", "note"
    )  # fmt: skip
    assert db.execute("SELECT count(*) AS n FROM merges").fetchone() == {"n": 0}
    assert _idea(db, cast["mine"]["id"])["status"] == "with_review_desk"
    assert len(_crew(db, cast["theirs"]["id"])) == 4


def test_V_ACC_review_13_defaults_merge_the_later_idea_into_the_earlier(
    db: Conn, cast: dict[str, Any]
) -> None:
    mine, theirs, meera = cast["mine"], cast["theirs"], cast["meera"]["id"]
    arjun = f.person(db, "Arjun Nair")
    f.crew(db, mine, arjun)
    db.execute("INSERT INTO question_sets (idea_uuid, by_user_id) VALUES (%s, %s)", (mine["id"], meera))
    db.execute(
        "INSERT INTO question_sets (idea_uuid, by_user_id, state, sent_at, due_at, time_to_answer) "
        "VALUES (%s, %s, 'sent', now(), now() + interval '3 days', '3d')",
        (mine["id"], meera),
    )
    t = f.at(16, 11, 30)
    m = _merge(db, cast, t, note=NOTE + " Folio 1234567890 shows both.")
    # the earlier idea leads; the other is merged and points to it
    assert (m["lead_idea_id"], m["merged_idea_id"], m["via"], m["team_up"]) == (
        theirs["idea_id"], mine["idea_id"], "review_desk", True
    )  # fmt: skip
    assert m["banner"] == (
        f"Merged: Kavya’s idea is now part of {theirs['idea_id']}, and both are credited. Kavya is on Ravi’s crew. "
        "Both were told in their Inbox. The Ones Committee can reverse it within 30 days."
    )
    assert "1234567890" not in m["note"] and "Folio ••••90" in m["note"]
    row = _idea(db, mine["id"])
    assert (row["status"], row["merged_into"]) == ("merged", theirs["id"])
    stored = db.execute("SELECT * FROM merges WHERE id = %s", (m["id"],)).fetchone()
    assert stored is not None and (stored["prior_status"], str(stored["by_user_id"])) == (
        "with_review_desk",
        meera,
    )
    assert unseal(stored["note_encrypted"], "merges", "note_encrypted", m["id"]) == m["note"]
    # both credited; Kavya and her crew are on Ravi's crew, by the desk's merge, with one lead still
    assert {cast["kavya"]["code"], cast["ravi"]["code"]} <= own_codes(db, _idea(db, theirs["id"]))
    joined = [r for r in _crew(db, theirs["id"]) if r["via"] == "desk_merge"]
    assert [(r["contributor_code"], r["role"], str(r["merge_id"])) for r in joined] == [
        (cast["kavya"]["code"], "crew", m["id"]), (arjun["code"], "crew", m["id"])
    ]  # fmt: skip
    assert [r["role"] for r in _crew(db, theirs["id"])].count("lead") == 1
    # the committee's window, the conversation on both, the sets closed, the audit
    w = db.execute("SELECT * FROM decision_windows WHERE merge_id = %s", (m["id"],)).fetchone()
    assert w is not None and (w["state"], w["opens_at"], w["closes_at"]) == (
        "open",
        t,
        t + dt.timedelta(days=30),
    )
    assert m["window"]["closes_at"] == (t + dt.timedelta(days=30)).isoformat()
    assert "desk.merged" in f.events(db, mine["id"]) and "desk.merged" in f.events(db, theirs["id"])
    sets = db.execute("SELECT state FROM question_sets WHERE idea_uuid = %s", (mine["id"],)).fetchall()
    assert [s["state"] for s in sets] == ["closed"]
    assert f.audit_actions(db, f"idea:{mine['idea_id']}")[-1] == "desk.merge"


def test_L_MERGE_desk_2_team_up_off_adds_no_crew(db: Conn, cast: dict[str, Any]) -> None:
    m = _merge(db, cast, f.at(16, 12), team_up=False)
    assert m["team_up"] is False and "is on Ravi’s crew" not in m["banner"]
    assert [r["via"] for r in _crew(db, cast["theirs"]["id"])].count("desk_merge") == 0
    assert _idea(db, cast["mine"]["id"])["status"] == "merged"


def test_V_ACC_review_14_a_reviewer_cannot_merge_or_revise_their_own_idea(
    db: Conn, cast: dict[str, Any]
) -> None:
    meera = cast["meera"]
    own = f.idea(db, meera, shared_at=f.at(13, 9))
    for ref, other in ((own["idea_id"], cast["mine"]["idea_id"]), (cast["mine"]["idea_id"], own["idea_id"])):
        with pytest.raises(Refused) as refused:
            merging.desk_merge(db, ref, meera["id"], {"other_idea_id": other, "lead": "other", "note": NOTE})
        assert (refused.value.status, refused.value.code) == (403, "own_idea")
        with pytest.raises(Refused):
            merging.sheet_for(db, ref, other, meera["id"])
    with pytest.raises(Refused) as refused:
        revise.revise_worth(db, own["idea_id"], meera["id"], {"hours_month": "10"})
    assert refused.value.code == "own_idea"
    assert db.execute("SELECT count(*) AS n FROM merges").fetchone() == {"n": 0}
    assert "desk.own_idea_refused" in f.audit_actions(db, f"idea:{own['idea_id']}")


def test_L_MERGE_desk_5_an_already_decided_idea_cannot_join(db: Conn, cast: dict[str, Any]) -> None:
    meera = cast["meera"]["id"]
    decided = f.idea(db, cast["ravi"], status="not_picked", shared_at=f.at(1, 9))
    for ref, other, lead, code in (
        (decided["idea_id"], cast["mine"]["idea_id"], "other", "already_decided"),
        (cast["mine"]["idea_id"], decided["idea_id"], "this", "other_not_open"),
    ):
        with pytest.raises(Refused) as refused:
            merging.desk_merge(db, ref, meera, {"other_idea_id": other, "lead": lead, "note": NOTE})
        assert (refused.value.status, refused.value.code) == (409, code)
    # a picked idea can still lead ("joined it with IDEA-… so one team builds one fix", L-MERGE.desk/5)
    picked = f.idea(db, cast["ravi"], status="picked", shared_at=f.at(3, 9))
    m = merging.desk_merge(db, cast["mine"]["idea_id"], meera,
                           {"other_idea_id": picked["idea_id"], "lead": "other", "note": NOTE})  # fmt: skip
    assert m["lead_idea_id"] == picked["idea_id"]


# ---------------------------------------------------------------------------------------------------------------
# The committee reverses a desk merge (L-MERGE.effects/7)
# ---------------------------------------------------------------------------------------------------------------


def _check_reversed(db: Conn, cast: dict[str, Any], m: dict[str, Any], t: dt.datetime) -> None:
    mine, theirs = cast["mine"], cast["theirs"]
    row = _idea(db, mine["id"])
    assert (row["status"], row["merged_into"]) == ("with_review_desk", None)
    undone = [r for r in _crew(db, theirs["id"]) if r["via"] == "desk_merge"]
    assert undone and all((r["left_at"], r["left_how"]) == (t, "merge_reversed") for r in undone)
    assert [r["role"] for r in _crew(db, mine["id"]) if r["left_at"] is None] == [
        "lead"
    ]  # her own crew stays
    stored = db.execute("SELECT reversed_at FROM merges WHERE id = %s", (m["id"],)).fetchone()
    assert stored == {"reversed_at": t}
    assert cast["kavya"]["code"] not in own_codes(db, _idea(db, theirs["id"]))
    for idea in (mine, theirs):
        assert f.events(db, idea["id"])[-1] == "committee.merge_reversed"


def test_L_MERGE_effects_7_reverse_merge_restores_the_merged_idea(db: Conn, cast: dict[str, Any]) -> None:
    m = _merge(db, cast, f.at(16, 11))
    t = f.at(18, 15)
    with db.transaction():  # the committee's transaction
        merging.reverse_merge(db, m["id"], cast["rohan"]["id"], "Two problems, not one.", t)
    _check_reversed(db, cast, m, t)


def test_L_COMMITTEE_rules_3_the_committee_reverses_a_desk_merge(db: Conn, cast: dict[str, Any]) -> None:
    m = _merge(db, cast, f.at(16, 11))
    w = db.execute("SELECT id FROM decision_windows WHERE merge_id = %s", (m["id"],)).fetchone()
    assert w is not None
    t = f.at(18, 15)
    note = "These are two problems: the SMS wording, and the calls it causes. Keep them apart."
    committee.reverse_window(db, str(w["id"]), cast["rohan"]["id"], {"note": note}, t)
    _check_reversed(db, cast, m, t)
    assert f.audit_actions(db, f"window:{w['id']}")[-1] == "committee.reverse"


# ---------------------------------------------------------------------------------------------------------------
# What it's worth (L-WORTH)
# ---------------------------------------------------------------------------------------------------------------


def _sharer_worth(db: Conn, c: dict[str, Any]) -> dict[str, Any]:
    row = db.execute(
        "INSERT INTO idea_worth (idea_uuid, by_side, by_code, hours_low, hours_high, cost_low, outside_tools, at) "
        "VALUES (%s, 'sharer', %s, 70, 150, 25000, 'partly', %s) RETURNING *",
        (c["mine"]["id"], c["kavya"]["code"], f.at(14, 10)),
    ).fetchone()
    assert row is not None
    return dict(row)


def test_V_ACC_review_10_a_revision_keeps_both_figures_and_marks_the_changed_tile(
    db: Conn, cast: dict[str, Any]
) -> None:
    sharer_row = _sharer_worth(db, cast)
    ref, t = cast["mine"]["idea_id"], f.at(16, 12)
    note = "The 40 calls are across three branches, so I scaled it up. Folio 1234567890 is one of them."
    got = revise.revise_worth(db, ref, cast["meera"]["id"], {"hours_month": "200 to 300", "note": note}, t)
    tiles = {x["measure"]: x for x in got["tiles"]}
    assert (tiles["hours_month"]["value"], tiles["hours_month"]["was"], tiles["hours_month"]["changed"]) == (
        "200 to 300 hours a month", "was 70 to 150 hours a month", True
    )  # fmt: skip
    # what was left out keeps its figure, so it is not marked changed
    assert (tiles["cost_month"]["value"], tiles["cost_month"]["changed"]) == ("₹25,000 a month", False)
    assert (tiles["outside_tools"]["value"], tiles["revenue_month"]["value"]) == (
        "Partly less reliance", "Not given"
    )  # fmt: skip
    # the note: masked, sealed under its own row
    assert "1234567890" not in got["reviewer"]["note"] and "Folio ••••90" in got["reviewer"]["note"]
    stored = db.execute("SELECT * FROM idea_worth WHERE id = %s", (got["worth_id"],)).fetchone()
    assert stored is not None and stored["by_side"] == "reviewer"
    assert str(stored["by_user_id"]) == cast["meera"]["id"]
    assert (stored["hours_low"], stored["hours_high"], stored["cost_low"]) == (200, 300, 25000)
    assert (
        unseal(stored["note_encrypted"], "idea_worth", "note_encrypted", got["worth_id"])
        == (got["reviewer"]["note"])
    )
    # the sharer's row is untouched (L-WORTH/3)
    again = db.execute("SELECT * FROM idea_worth WHERE id = %s", (sharer_row["id"],)).fetchone()
    assert dict(again or {}) == sharer_row
    sharer, reviewer, meta = revise.current(db, cast["mine"]["id"])
    assert sharer.hours_month is not None and sharer.hours_month.text == "70 to 150 hours a month"
    assert reviewer is not None and reviewer.hours_month is not None
    assert reviewer.hours_month.as_json() == {"low": 200.0, "high": 300.0, "text": "200 to 300 hours a month"}
    assert meta is not None and (meta["note"], meta["by"]["first_name"], dt.datetime.fromisoformat(meta["at"])) == (
        got["reviewer"]["note"], "Meera", t
    )  # fmt: skip
    assert f.events(db, cast["mine"]["id"])[-1] == "desk.worth_revised"
    assert f.audit_actions(db, f"idea:{ref}")[-1] == "desk.revise_worth"


def test_L_WORTH_2_kind_and_area_changes_are_applied_and_audited(db: Conn, cast: dict[str, Any]) -> None:
    ref = cast["mine"]["idea_id"]
    got = revise.revise_worth(
        db,
        ref,
        cast["meera"]["id"],
        {"kind": "business_idea", "area": "Operations", "revenue_month": "2 lakh"},
    )
    assert (got["kind"], got["area"]) == ("business_idea", "Operations")
    row = _idea(db, cast["mine"]["id"])
    assert (row["kind"], row["area"]) == ("business_idea", "Operations")
    entry = db.execute(
        "SELECT before, after FROM audit_log WHERE action = 'desk.revise_worth' AND entity = %s",
        (f"idea:{ref}",),
    ).fetchone()
    assert entry is not None and entry["before"] == {"kind": "problem", "area": "Investor service"}
    assert (entry["after"]["kind"], entry["after"]["area"], entry["after"]["changed"]) == (
        "business_idea", "Operations", ["revenue_month"]
    )  # fmt: skip
    assert {x["measure"]: x["value"] for x in got["tiles"]}["revenue_month"] == "₹2,00,000 a month"


def test_V_FIELDS_review_7_a_bad_figure_is_refused(db: Conn, cast: dict[str, Any]) -> None:
    ref, meera = cast["mine"]["idea_id"], cast["meera"]["id"]
    with pytest.raises(Refused) as refused:
        revise.revise_worth(db, ref, meera, {"hours_month": "a lot of hours"})
    assert (refused.value.status, refused.value.code, refused.value.message, refused.value.field) == (
        422, "worth_invalid", "Write a figure or a range.", "hours_month"
    )  # fmt: skip
    with pytest.raises(Refused) as refused:
        revise.revise_worth(db, ref, meera, {"kind": "fix"})
    assert (refused.value.code, refused.value.field) == ("kind_invalid", "kind")
    assert db.execute("SELECT count(*) AS n FROM idea_worth").fetchone() == {"n": 0}


def test_L_WORTH_2_only_while_the_idea_is_on_the_desk(db: Conn, cast: dict[str, Any]) -> None:
    picked = f.idea(db, cast["kavya"], status="picked")
    with pytest.raises(Refused) as refused:
        revise.revise_worth(db, picked["idea_id"], cast["meera"]["id"], {"hours_month": "10"})
    assert (refused.value.status, refused.value.code) == (409, "already_decided")
