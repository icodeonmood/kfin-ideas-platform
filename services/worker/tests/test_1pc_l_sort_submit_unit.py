"""L-SORT and L-SUBMIT without a database (lane C, BLD-C080 to BLD-C086): the sorting lists and review routing as
configuration, the decide_by timer kind on lane A's engine, the clocks in India time, the words the screens show,
and the cross-lane adapters. The database-backed behaviour is in test_1pc_l_sort_submit_db.py."""

from __future__ import annotations

import datetime as dt
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from rules import RulesConfigError, load_rule

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


@pytest.fixture
def seed_rules(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The rules as seeded, not the dev stack's copy."""
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(SEED))
    get_settings.cache_clear()
    yield
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    dest = tmp_path / "kfin-ideas"
    shutil.copytree(SEED, dest)
    return dest


def _edit(repo: Path, rel: str, old: str, new: str) -> None:
    path = repo / rel
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# --- L-SORT.fields and L-SORT.rules/7: configuration ------------------------------------------------------------


def test_l_sort_fields_the_lists_are_configuration_in_the_company_repo() -> None:
    data = load_rule(SEED, "sorting").data
    assert data["affects"]["shown"] == ["Investors", "KFin teams", "Distributors"]
    assert len(data["affects"]["shown"]) + len(data["affects"]["more"]) == 6  # "Someone else? Search all 6"
    assert data["areas"]["shown"] == ["Investor service", "Operations", "Distributor experience"]
    assert {"Corporate registry", "Technology", "Compliance", "Sales", "New business"} <= set(
        data["areas"]["more"]
    )
    assert data["helpers"][0] == "Someone at a branch"


def test_l_sort_rules_7_default_is_any_reviewer_until_the_desk_lead_sends_a_map() -> None:
    routing = load_rule(SEED, "sorting").data["review_routing"]
    assert routing == {"default": "any_reviewer", "areas": {}}


def test_l_sort_rules_7_a_mapped_area_must_be_on_the_list(repo: Path) -> None:
    _edit(repo, "rules/sorting.md", "  areas: {}", "  areas:\n    Canteen:\n    - reviewer@example.test")
    with pytest.raises(RulesConfigError) as err:
        load_rule(repo, "sorting")
    assert "Canteen is not one of the areas" in str(err.value)


def test_l_sort_fields_a_value_listed_twice_is_a_config_error(repo: Path) -> None:
    _edit(repo, "rules/sorting.md", "  - Others", "  - investors")
    with pytest.raises(RulesConfigError) as err:
        load_rule(repo, "sorting")
    assert "affects: each value may appear only once" in str(err.value)


def test_a_api_config_sorting_controls_carry_their_words(seed_rules: None) -> None:
    from submit.config import DECLARATION_VERSION, public_config

    c = public_config()
    assert c["sorting"]["affects"]["search_label"] == "Someone else? Search all 6"
    assert c["sorting"]["affects"]["search_link"] == "Search all groups"
    assert (
        c["sorting"]["area"]["search_label"] == f"Another area? Search all {len(c['sorting']['area']['all'])}"
    )
    assert [o["label"] for o in c["sorting"]["kind"]["options"]] == [
        "A problem to fix",
        "A new business idea",
    ]
    assert c["sorting"]["brings"]["exclusive"] == "not_sure"
    assert c["declaration"]["version"] == DECLARATION_VERSION
    assert c["declaration"]["submit"].startswith(
        "By submitting, you confirm there’s no customer personal data"
    )
    assert c["declaration"]["save"].startswith("By saving, you confirm")
    assert c["windows"] == {"review_working_days": 5, "edit_window_days": 3}


# --- L-SUBMIT.send/4: the review clock is a timer kind lane A's engine knows ------------------------------------


def test_l_submit_send_4_decide_by_is_a_registered_timer_kind() -> None:
    """BLD-A182 makes the engine skip a kind it has no rule for, silently. decide_by must have its rule, with a
    limit and no reminders or escalation (a window: it stops quietly at its date; the desk lead's digest covers
    overdue ideas)."""
    from submit.clock import TIMER_KIND

    rules = load_rule(SEED, "sla").data
    assert TIMER_KIND == "decide_by"
    assert rules[TIMER_KIND] == {"limit_wd": 5}
    rule = rules[TIMER_KIND]
    assert not (rule.get("escalate_to") or rule.get("remind_at") or rule.get("on_breach"))


def test_l_submit_send_4_decide_by_follows_the_boards(seed_rules: None) -> None:
    """Shared Saturday 14 November: the review desk looks at it by Friday 20 November (6 pm India time)."""
    from submit import clock, config

    p = config.promises()
    sat = dt.datetime(2026, 11, 14, 10, 5, tzinfo=IST)
    assert clock.decide_by(sat, p) == dt.datetime(2026, 11, 20, 18, 0, tzinfo=IST)
    tue_morning = dt.datetime(2026, 11, 17, 10, 0, tzinfo=IST)  # day 1 is the share day
    assert clock.decide_by(tue_morning, p) == dt.datetime(2026, 11, 23, 18, 0, tzinfo=IST)
    tue_evening = dt.datetime(2026, 11, 17, 19, 0, tzinfo=IST)  # after 6 pm: day 1 is the next working day
    assert clock.decide_by(tue_evening, p) == dt.datetime(2026, 11, 24, 18, 0, tzinfo=IST)
    before_diwali = dt.datetime(
        2026, 11, 6, 9, 0, tzinfo=IST
    )  # 9 and 10 November are holidays in the seed calendar
    assert clock.decide_by(before_diwali, p) == dt.datetime(2026, 11, 16, 18, 0, tzinfo=IST)


def test_l_submit_edit_1_the_window_is_three_days(seed_rules: None) -> None:
    from submit import clock, config

    sat = dt.datetime(2026, 11, 14, 10, 5, tzinfo=IST)
    assert clock.edit_closes(sat, config.promises()) == dt.datetime(2026, 11, 17, 10, 5, tzinfo=IST)


# --- Words (A-API.conventions/6), India time ----------------------------------------------------------------------


def test_a_api_6_dates_read_as_the_boards_write_them() -> None:
    from submit import words

    now = dt.datetime(2026, 11, 14, 4, 40, tzinfo=dt.UTC)  # 10:10 am IST
    assert words.day(dt.datetime(2026, 11, 20, 12, 30, tzinfo=dt.UTC), now) == "Friday 20 November"
    assert words.day(dt.datetime(2027, 2, 16, 6, 0, tzinfo=dt.UTC), now) == "Tuesday 16 February 2027"
    assert words.when_shared(dt.datetime(2026, 11, 14, 4, 35, tzinfo=dt.UTC), now) == "Today, 10:05 am"
    assert words.when_shared(dt.datetime(2026, 11, 13, 12, 40, tzinfo=dt.UTC), now) == "Yesterday, 6:10 pm"
    assert words.short_date(dt.datetime(2026, 11, 14, 4, 35, tzinfo=dt.UTC)) == "14-Nov-26"
    assert words.clock(dt.datetime(2026, 11, 14, 8, 9, tzinfo=dt.UTC)) == "1:39 pm"
    assert words.countdown(now + dt.timedelta(days=2, hours=20), now)["label"] == "3 days left"
    assert words.countdown(now + dt.timedelta(hours=7, minutes=38, seconds=30), now)["label"] == "07:38 left"
    assert words.countdown(now - dt.timedelta(minutes=1), now)["label"] == "Overdue"
    assert words.in_sentence("Investors") == "investors"
    assert words.in_sentence("KFin teams") == "KFin teams"
    assert words.in_sentence("AMC clients") == "AMC clients"


# --- L-SORT.rules/3 and the lines beside the sorting --------------------------------------------------------------


def _choices(source: str = "confirmed") -> dict[str, Any]:
    from submit.sorting import Choice

    return {
        "affects": Choice(
            ["Investors", "KFin teams"], source, "because you mentioned investors and the branch"
        ),
        "kind": Choice("problem", source, "because you described something that goes wrong today."),
        "area": Choice("Investor service", source, "because it’s about investors and the SMS they get"),
        "brings": Choice(
            ["saves_time", "saves_cost"], source, "Suggested because you said “about 40 calls a day”."
        ),
    }


def test_l_sort_s05_part2_lines_before_and_after_confirming() -> None:
    from submit import sorting

    suggested = _choices("suggested")
    assert sorting.rail_line(suggested) == "Suggested, not confirmed yet"
    assert sorting.summary_line(suggested) == "Not confirmed yet"
    confirmed = _choices("confirmed")
    assert sorting.rail_line(confirmed) == "Investor service, saves time, saves cost"
    assert (
        sorting.summary_line(confirmed)
        == "Investor service, affecting investors and KFin teams, saves time, saves cost"
    )
    assert (
        sorting.why_line(confirmed["affects"]) == "Suggested because you mentioned investors and the branch."
    )
    assert sorting.why_line(confirmed["brings"]) == "Suggested because you said “about 40 calls a day”."


def test_l_sort_rules_3_a_changed_value_is_the_persons_call() -> None:
    from submit.sorting import Choice, why_line

    assert why_line(Choice("Operations", "changed", None)) is None


def test_e_enums_kind_a_problem_with_a_fix_is_stored_as_fix_and_sorted_as_a_problem() -> None:
    from submit.sorting import kind_on_check_it, stored_kind

    assert stored_kind("problem", True) == "fix"
    assert stored_kind("problem", False) == "problem"
    assert stored_kind("business_idea", True) == "business_idea"
    assert kind_on_check_it("fix") == "problem"
    assert kind_on_check_it("problem_with_solution") == "problem"
    assert kind_on_check_it("business_idea") == "business_idea"
    assert kind_on_check_it("anything else") is None


@pytest.mark.parametrize(
    ("field", "raw", "ok"),
    [
        ("affects", ["investors", "KFin Teams"], ["Investors", "KFin teams"]),
        ("affects", [], None),
        ("affects", ["Canteen staff"], None),
        ("area", "operations", "Operations"),
        ("area", "Somewhere else", None),
        ("kind", "business_idea", "business_idea"),
        ("kind", "fix", "problem"),
        ("kind", "wish", None),
        ("brings", ["saves_time", "saves_time", "earns_revenue"], ["saves_time", "earns_revenue"]),
        ("brings", ["not_sure"], ["not_sure"]),
        ("brings", ["not_sure", "saves_time"], None),  # "Not sure yet" clears the others (V-FIELDS.checkit/3)
        ("brings", ["saves_everything"], None),
        ("brings", [], None),
    ],
)
def test_v_fields_sorting_each_field_is_checked(seed_rules: None, field: str, raw: Any, ok: Any) -> None:
    from submit import config, sorting
    from submit.errors import Refused

    li = config.lists()
    if ok is None:
        with pytest.raises(Refused) as err:
            sorting._read_value(field, raw, li)  # type: ignore[arg-type]
        assert err.value.code == "sorting_incomplete"
        assert err.value.message == "Confirm these, or change any of them, before you send."
        assert err.value.field == "sorting"
    else:
        assert sorting._read_value(field, raw, li) == ok  # type: ignore[arg-type]


# --- L-SUBMIT.send: the hand-over to S-06 ------------------------------------------------------------------------


def test_l_submit_send_hands_over_what_s06_just_shared_shows() -> None:
    """V-ACC.share/12: the reference and "The review desk will look at it by <date>" are there at once."""
    from submit.send import handover

    shared = dt.datetime(2026, 11, 14, 4, 35, tzinfo=dt.UTC)
    idea = {
        "id": "00000000-0000-4000-8000-000000000001",
        "idea_id": "IDEA-2026-001481",
        "status": "checking",
        "title": "Investors call to ask why a redemption was rejected",
        "shared_at": shared,
        "decide_by": dt.datetime(2026, 11, 20, 12, 30, tzinfo=dt.UTC),
        "edit_closes_at": shared + dt.timedelta(days=3),
        "opened_at": None,
    }
    h = handover(None, idea, shared + dt.timedelta(seconds=2))  # type: ignore[arg-type]
    assert h["idea_id"] == h["ref"] == "IDEA-2026-001481"
    assert h["pill"] == {"status": "checking", "label": "Checking", "variant": "blue"}
    assert h["shared_label"] == "Shared 14-Nov-26"
    assert h["review"]["line"] == (
        "The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email when anything "
        "changes."
    )
    assert h["review"]["by_label"] == "By Friday 20 November"
    assert [(s["stage"], s["state"]) for s in h["stages"]] == [
        ("shared", "done"),
        ("checked_matched", "now"),
        ("reviewed", "to_come"),
        ("built", "to_come"),
        ("shipped", "to_come"),
    ]
    assert h["stages"][0]["detail"] == "Today, 10:05 am"
    assert h["stages"][1]["detail"] == "Checking…"
    assert h["edit_window"]["open"] is True
    assert h["edit_window"]["line"].startswith(
        "Open to changes until Tuesday 17 November. Edit or withdraw it"
    )
    assert h["edit_window"]["countdown"]["label"] == "3 days left"
    assert h["next"] == {"to": "/ideas/IDEA-2026-001481", "replace": True, "state": "just_shared"}


def test_l_submit_send_checked_line() -> None:
    from submit.send import checked_line

    assert checked_line(2, 2) == "Personal details hidden, 2 similar ideas found"
    assert checked_line(1, 0) == "1 personal detail hidden, no similar ideas found"
    assert checked_line(0, 1) == "No personal details found, 1 similar idea found"


# --- Adapters (SHIP_PLAN §5a) ------------------------------------------------------------------------------------


def test_l_submit_withdraw_is_lane_es_and_waits_for_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Withdraw and restore have one implementation, lane E's ideapage.withdraw; until it is here the adapter says
    so instead of doing anything itself."""
    from submit import adapters

    monkeypatch.setattr(adapters, "_module", lambda name: None)
    with pytest.raises(adapters.NotYetAvailable):
        adapters.withdraw(None, "IDEA-2026-000001", "u")  # type: ignore[arg-type]
    with pytest.raises(adapters.NotYetAvailable):
        adapters.restore(None, "IDEA-2026-000001", "u")  # type: ignore[arg-type]
    assert adapters.install_hooks() is False


def test_l_submit_withdraw_3_the_restore_hook_plugs_into_lane_e(monkeypatch: pytest.MonkeyPatch) -> None:
    import types

    from submit import adapters

    fake = types.SimpleNamespace(
        ON_RESTORED_HOOK=None,
        withdraw=lambda conn, key, user, reason=None: {"called": ("withdraw", key, user, reason)},
        restore=lambda conn, key, user: {"called": ("restore", key, user)},
    )
    monkeypatch.setattr(adapters, "_module", lambda name: fake if name == "ideapage.withdraw" else None)
    assert adapters.install_hooks() is True
    assert fake.ON_RESTORED_HOOK is adapters.on_restored
    assert adapters.withdraw(None, "IDEA-2026-000001", "u", "x")["called"][0] == "withdraw"  # type: ignore[arg-type]
    assert adapters.restore(None, "IDEA-2026-000001", "u")["called"][0] == "restore"  # type: ignore[arg-type]


def test_l_hide_an_edit_is_masked_before_it_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    """DEC-103: kind + •••• + the last two characters, with positions in the person's own text and no value."""
    from submit import adapters

    monkeypatch.setattr(adapters, "_module", lambda name: None)
    text = "Investor with PAN ABCPE1234F called twice"  # a made-up PAN
    m = adapters.mask_text(None, "idea", text, source="edit", source_id="x")  # type: ignore[arg-type]
    assert m.text == "Investor with PAN PAN ••••4F called twice"
    assert m.found == [{"kind": "pan", "masked": "PAN ••••4F", "start": 18, "end": 28}]
    clean = adapters.mask_text(None, "idea", "Nothing personal here", source="edit", source_id="x")  # type: ignore[arg-type]
    assert clean.text == "Nothing personal here" and clean.found == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("70 to 150", (70.0, 150.0)),
        ("2 lakh", (200000.0, None)),
        ("2L", (200000.0, None)),
        ("2,00,000", (200000.0, None)),
        (25000, (25000.0, None)),
        ({"low": 70, "high": 150}, (70.0, 150.0)),
        ("150 to 70", None),
        ("a lot", None),
        (-5, None),
    ],
)
def test_l_worth_1_amounts_in_any_indian_form(
    monkeypatch: pytest.MonkeyPatch, raw: Any, expected: Any
) -> None:
    from submit import adapters

    monkeypatch.setattr(adapters, "_module", lambda name: None)
    assert adapters.parse_range("cost", raw) == expected


def test_a_api_errors_have_the_conventions_shape() -> None:
    from submit.errors import NotFound, Refused

    assert Refused(
        422, "sorting_unconfirmed", "Confirm the sorting first, or change any of it.", "sorting"
    ).body() == {
        "error": {
            "code": "sorting_unconfirmed",
            "message": "Confirm the sorting first, or change any of it.",
            "field": "sorting",
        }
    }
    assert NotFound().status == 404
