"""L-SORT and L-SUBMIT without a database (lane C, BLD-C080 to BLD-C086): the sorting lists and review routing as
configuration, the decide_by timer kind on lane A's engine, the clocks in India time, the words the screens show,
and the cross-lane adapters. The database-backed behaviour is in test_1pc_l_sort_submit_db.py."""

from __future__ import annotations

import datetime as dt
import shutil
import uuid
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
    # F-COPY.plurals/3 (BLD-A225): office calendar days, so Saturday 10:10 am to Sunday 11:10 am is 1 day, not 2
    assert words.countdown(now + dt.timedelta(days=1, hours=1), now)["label"] == "1 day left"
    assert words.countdown(now + dt.timedelta(hours=7, minutes=38, seconds=30), now)["label"] == "07:38 left"
    assert words.countdown(now - dt.timedelta(minutes=1), now) == {
        "label": "Overdue by 1 minute",
        "variant": "bad",
        "until": (now - dt.timedelta(minutes=1)).isoformat(),
    }
    assert words.in_sentence("Investors") == "investors"
    assert words.in_sentence("KFin teams") == "KFin teams"
    assert words.in_sentence("AMC clients") == "AMC clients"


# --- L-SORT.rules/3 and the lines beside the sorting --------------------------------------------------------------


def _choices(source: str = "confirmed") -> Any:
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

    assert checked_line(2, 2, "pan") == "Personal details hidden, 2 similar ideas found"
    assert checked_line(1, 0, "pan") == "1 PAN hidden, no similar ideas found"
    assert checked_line(0, 1) == "No personal details found, 1 similar idea found"


def test_c_track_s06_l_submit_send_one_hidden_detail_is_named_as_s06_names_it_bld_c153() -> None:
    """J-SHARE's hand-over and S-06's track say one hidden detail the same way, by its kind, from the same words
    (`ideapage.track.KIND_WORDS`), and those are L-HIDE's nouns (hide/config.yaml), so neither drifts."""
    from hide import detect
    from ideapage.track import KIND_WORDS
    from submit.send import checked_line

    assert {k: detect.noun(k) for k in detect.KINDS} == KIND_WORDS
    for kind in detect.KINDS:
        assert checked_line(1, 3, kind) == f"1 {detect.noun(kind)} hidden, 3 similar ideas found"
    assert checked_line(1, 0, "phone") == "1 phone number hidden, no similar ideas found"
    assert checked_line(1, 0, "aadhaar") == "1 Aadhaar number hidden, no similar ideas found"
    assert (
        checked_line(1, 0) == "1 detail hidden, no similar ideas found"
    )  # S-06's own fallback, never reached
    assert checked_line(3, 0, "pan").startswith("Personal details hidden,")  # several stay as Status.md draws
    assert checked_line(0, 0, None).startswith("No personal details found,")


def test_l_similar_failure_the_track_says_couldnt_check_not_none_found_bld_c087() -> None:
    from submit.send import checked_line

    assert checked_line(1, None, "folio") == (
        "1 folio number hidden. Couldn’t check for similar ideas. The review desk will."
    )
    assert "no similar ideas" not in checked_line(0, None)


# --- Adapters (SHIP_PLAN §5a) ------------------------------------------------------------------------------------


def test_l_submit_withdraw_3_the_restore_hook_plugs_into_lane_e(monkeypatch: pytest.MonkeyPatch) -> None:
    """Withdraw and restore are lane E's alone (BLD-C087 removed lane C's unused wrappers); lane C plugs its part of a
    restore into lane E's ON_RESTORED_HOOK when that module is here, and does nothing when it is not."""
    import types

    from submit import adapters

    assert not hasattr(adapters, "withdraw") and not hasattr(adapters, "restore")
    monkeypatch.setattr(adapters, "_module", lambda name: None)
    assert adapters.install_hooks() is False
    fake = types.SimpleNamespace(ON_RESTORED_HOOK=None)
    monkeypatch.setattr(adapters, "_module", lambda name: fake if name == "ideapage.withdraw" else None)
    assert adapters.install_hooks() is True
    assert fake.ON_RESTORED_HOOK is adapters.on_restored


def test_l_submit_send_4_on_restored_fits_lane_es_hook_and_takes_a_now_bld_c154() -> None:
    """`on_restored` still fits lane E's `ON_RESTORED_HOOK: Callable[[Conn, str], None]` (mypy checks the assignment)
    and takes the restore's `now` as an optional third argument, by position or by name."""
    import inspect
    from collections.abc import Callable

    from core.db import Conn
    from submit import adapters

    hook: Callable[[Conn, str], None] = adapters.on_restored
    assert hook is adapters.on_restored
    now = inspect.signature(adapters.on_restored).parameters["now"]
    assert now.default is None and now.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD


def test_l_hide_an_edit_is_masked_by_the_patterns_until_hide_lands(monkeypatch: pytest.MonkeyPatch) -> None:
    """DEC-103: kind + •••• + the last two characters, with positions in the person's own text and no value."""
    from submit import adapters

    monkeypatch.setattr(adapters, "_module", lambda name: None)
    text = "Investor with PAN ABCPE1234F called twice"  # a made-up PAN
    masked, found = adapters.pattern_mask(text)
    assert masked == "Investor with PAN PAN ••••4F called twice"
    assert found == [adapters.Found("pan", 18, 28, "PAN ••••4F")]
    sql: list[str] = []

    class Conn:
        def execute(self, query: str, *a: Any) -> None:
            sql.append(query)

    clean = adapters.mask_text(Conn(), str(uuid.uuid4()), "Nothing personal here", by="u", source_id="x")  # type: ignore[arg-type]
    assert clean == adapters.Masked("Nothing personal here", [], 0)
    # Saved again under the same source id (a draft's fix answer): what was hidden from the old words goes first.
    assert sql == [
        "DELETE FROM hidden_details WHERE idea_uuid = %s AND source = 'edit' AND source_id = %s",
        "DELETE FROM idea_words_sealed WHERE idea_uuid = %s AND source = 'edit' AND source_id = %s",
    ]


@pytest.mark.parametrize(
    ("text", "masked", "kind"),
    [
        ("folio 9876543210", "folio Folio ••••10", "folio"),  # also a phone shape: the rule with context wins
        ("a/c 4111111111111111", "a/c Account ••••11", "account"),  # also a card number: one detail, once
    ],
)
def test_l_hide_overlapping_matches_mask_once_bld_c087(
    monkeypatch: pytest.MonkeyPatch, text: str, masked: str, kind: str
) -> None:
    """Two rules on one span keep one match (the longer, then the one with context), substituted from the end."""
    from submit import adapters

    out, found = adapters.pattern_mask(text)
    assert out == masked
    assert [(f.kind, text[f.start : f.end]) for f in found] == [(kind, text.split()[-1])]
    both, found = adapters.pattern_mask(f"PAN ABCPE1234F and {text} again")
    assert both == f"PAN PAN ••••4F and {masked} again" and len(found) == 2


def test_l_hide_an_edit_goes_through_c_hide_once_it_is_here(monkeypatch: pytest.MonkeyPatch) -> None:
    """c/hide's entry points by their exact names: an edit's words through `hide_message` (source "edit", the
    gatekeeper on), the check's final pass through `hide_text`. Hide stores and seals; the adapter returns the
    masked copy and S-06B's Save writes nothing of its own (no second hidden_details or sealed row)."""
    import types

    from submit import adapters, edit

    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def hide_message(*args: Any, **kw: Any) -> Any:
        calls.append(("hide_message", args, kw))
        return types.SimpleNamespace(
            masked="PAN ••••4F", spans=[{"start": 0, "end": 10, "kind": "pan"}], hidden_count=1
        )

    def hide_text(*args: Any, **kw: Any) -> tuple[str, int]:
        calls.append(("hide_text", args, kw))
        return "Phone ••••10", 1

    fake = types.SimpleNamespace(hide_message=hide_message, hide_text=hide_text)
    monkeypatch.setattr(adapters, "_module", lambda name: fake if name == "hide" else None)

    class NoWrites:
        def execute(self, *a: Any, **k: Any) -> Any:
            raise AssertionError("the edit wrote a row of its own")

    uid, user = str(uuid.uuid4()), str(uuid.uuid4())
    save = edit._Save(NoWrites(), {"id": uid}, user, 2)  # type: ignore[arg-type]
    assert save.mask("summary", "ABCPE1234F") == "PAN ••••4F"
    m = adapters.mask_text(None, uid, "9876543210", by=user, source_id=None)  # type: ignore[arg-type]
    assert m == adapters.Masked("Phone ••••10", [], 1)
    assert calls == [
        ("hide_message", (save.conn, uid, "ABCPE1234F"),
         {"by": user, "source": "edit", "source_id": f"{uid}:2:summary", "gatekeeper": True}),
        ("hide_text", (None, uid, "9876543210"), {"by": user, "source": "edit"}),
    ]  # fmt: skip


def test_l_submit_edit_3_words_sent_back_as_stored_are_not_masked_again_bld_c141(
    monkeypatch: pytest.MonkeyPatch, seed_rules: None
) -> None:
    """An unchanged Save (and a draft's who would help sent again): words sent back exactly as their stored masked
    copies reach neither hide nor the database, so no hidden-detail or sealed rows are written again."""
    from submit import adapters, config, edit, helpers

    def no_hide(*a: Any, **k: Any) -> Any:
        raise AssertionError("masked again")

    monkeypatch.setattr(adapters, "mask_text", no_hide)

    class NoWrites:
        def execute(self, *a: Any, **k: Any) -> Any:
            raise AssertionError("an unchanged save wrote a row")

    idea: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "title": "SMS codes confuse investors",
        "summary": "Folio Folio ••••90 gets the SMS with only a code.",
        "helper_picks": ["Someone from tech"],
        "helper_text": "whoever has Phone ••••10",
    }
    s = edit._Save(NoWrites(), idea, str(uuid.uuid4()), 3)  # type: ignore[arg-type]
    edit._save_texts(
        s,
        {
            "title": "SMS codes confuse investors",
            "summary": " Folio Folio ••••90 gets  the SMS with only a code. ",
        },
    )
    edit._save_helpers(
        s, {"helpers": {"picks": ["someone from tech"], "text": "whoever has Phone ••••10"}}, config.lists()
    )
    assert s.after == {}
    kept = helpers.mask(
        NoWrites(),  # type: ignore[arg-type]
        idea["id"],
        "u",
        "whoever has Phone ••••10",
        source_id=f"{idea['id']}:draft:helpers",
        stored="whoever has Phone ••••10",
    )
    assert kept == "whoever has Phone ••••10"


@pytest.mark.parametrize(("returned", "expected"), [(3, 3), (0, 0), (-1, None)])
def test_l_similar_failure_minus_one_is_couldnt_check_not_zero(
    monkeypatch: pytest.MonkeyPatch, returned: int, expected: int | None
) -> None:
    """c/similar's `match_shared(conn, idea_uuid, *, found_while) -> int`: -1 is "couldn't check" (None here)."""
    import types

    from submit import adapters

    seen: list[tuple[Any, ...]] = []

    def match_shared(conn: Any, idea_uuid: str, *, found_while: str) -> int:
        seen.append((conn, idea_uuid, found_while))
        return returned

    fake = types.SimpleNamespace(match_shared=match_shared)
    monkeypatch.setattr(adapters, "_module", lambda name: fake if name == "similar" else None)
    assert adapters.find_similar(None, "u-1", found_while="checking") == expected  # type: ignore[arg-type]
    assert seen == [(None, "u-1", "checking")]
    monkeypatch.setattr(adapters, "_module", lambda name: None)
    assert adapters.find_similar(None, "u-1", found_while="later") is None  # type: ignore[arg-type]


def test_l_submit_send_3_without_the_sharers_users_id_the_final_pass_is_skipped_bld_c087(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hide's `by` is a users.id (the one person who may read the values): with no mapping for the sharer the check
    gives no made-up actor, skips the final pass with an id-only warning, and still sends the idea on."""
    import contextlib

    from submit import adapters, check

    uid = str(uuid.uuid4())
    sql: list[tuple[str, Any]] = []

    class Row:
        def __init__(self, row: dict[str, Any] | None) -> None:
            self.row = row

        def fetchone(self) -> dict[str, Any] | None:
            return self.row

    class Conn:
        def transaction(self) -> contextlib.nullcontext[None]:
            return contextlib.nullcontext()

        def execute(self, query: str, params: Any = None) -> Row:
            sql.append((query, params))
            if query.startswith("SELECT * FROM ideas"):
                return Row({"id": uid, "status": "checking", "contributor_code": "CTR-000000", "title": "T"})
            return Row(None)  # no contributor_map row

    def no_hiding(*a: Any, **k: Any) -> None:
        raise AssertionError("hidden with no users.id")

    monkeypatch.setattr(adapters, "mask_text", no_hiding)
    monkeypatch.setattr(adapters, "find_similar", lambda conn, idea_uuid, *, found_while: None)
    warned: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(check.log, "warning", lambda event, **kw: warned.append((event, kw)))
    check.run(Conn(), uid)  # type: ignore[arg-type]
    assert warned == [("submit.check_no_sharer", {"idea_uuid": uid})]
    moved = [p for q, p in sql if q.startswith("UPDATE ideas SET status = 'with_review_desk'")]
    assert moved == [("failed", uid)]  # couldn't check: recorded, never "none found"


def test_l_submit_send_queues_listen_once_c_sarvam_is_here(monkeypatch: pytest.MonkeyPatch) -> None:
    """c/sarvam's `speech.listen.enqueue_prefetch(conn, idea_uuid) -> None`, after a send; nothing until it lands."""
    import types

    from submit import adapters

    monkeypatch.setattr(adapters, "_module", lambda name: None)
    assert adapters.prefetch_listen(None, "u-1") is False  # type: ignore[arg-type]
    seen: list[tuple[Any, str]] = []
    fake = types.SimpleNamespace(enqueue_prefetch=lambda conn, idea_uuid: seen.append((conn, idea_uuid)))
    monkeypatch.setattr(adapters, "_module", lambda name: fake if name == "speech.listen" else None)
    assert adapters.prefetch_listen(None, "u-1") is True  # type: ignore[arg-type]
    assert seen == [(None, "u-1")]


# --- S-05.fix, A-API.drafts fix and helpers ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("measure", "raw", "low", "high", "text"),
    [
        ("hours_month", "70 to 150", 70.0, 150.0, "70 to 150 hours a month"),
        ("cost_month", "2 lakh", 200000.0, None, "₹2,00,000 a month"),
        ("cost_month", "2L", 200000.0, None, "₹2,00,000 a month"),
        ("cost_month", "2,00,000", 200000.0, None, "₹2,00,000 a month"),
        ("cost_month", "about 25k", 25000.0, None, "about ₹25,000 a month"),
        ("revenue_month", "1.2 crore", 12000000.0, None, "₹1,20,00,000 a month"),
        ("cost_month", 25000, 25000.0, None, "₹25,000 a month"),
        ("hours_month", {"low": 70, "high": 150}, 70.0, 150.0, "70 to 150 hours a month"),
        ("hours_month", {"low": 0, "text": "150 to 70"}, 70.0, 150.0, "70 to 150 hours a month"),
    ],
)
def test_l_worth_1_s05_fix_amounts_in_any_indian_form_through_lane_bs_reader(
    measure: str, raw: Any, low: float, high: float | None, text: str
) -> None:
    """A-API `PUT /drafts/:id/fix`: amounts parsed from any Indian form by `desk.worth` (one reader on the platform)
    and returned normalised in `Range.text`."""
    from desk.worth import Range
    from submit import fix

    assert not hasattr(__import__("submit.adapters").adapters, "parse_range")  # no second parser
    assert fix._figure(measure, raw, f"worth.{measure}") == Range(low, high, text)


@pytest.mark.parametrize("raw", ["a lot", -5, True, "9" * 81, {"low": "x"}, ["70"]])
def test_v_fields_checkit_9_an_unclear_amount_is_refused_with_its_message(raw: Any) -> None:
    from submit import fix
    from submit.errors import Refused

    with pytest.raises(Refused) as err:
        fix._figure("cost_month", raw, "worth.cost_month")
    assert err.value.body() == {
        "error": {
            "code": "worth_unclear",
            "message": "Write a rough figure or a range, like 70 to 150.",
            "field": "worth.cost_month",
        }
    }


def test_v_fields_checkit_8_how_is_needed_to_add_a_fix_not_to_keep_one() -> None:
    from submit import fix
    from submit.errors import Refused

    for body in ({}, {"how": "Print it."}, {"how": "   "}):
        with pytest.raises(Refused) as err:
            fix.read_answers(body, need_how=True)
        assert (err.value.code, err.value.field, err.value.message) == (
            "fix_how_needed",
            "how",
            "Say how you’d solve it, or close this to send without a fix.",
        )
    kept = fix.read_answers(
        {"needs": "Two people for a week", "worth": {"hours_month": "70"}}, need_how=False
    )
    assert kept.words["how"] is None and kept.words["needs"] == "Two people for a week"
    with pytest.raises(Refused) as err:
        fix.read_answers({"fix": {}}, need_how=True, at="fix.")
    assert err.value.field == "fix.how"
    odd = fix.read_answers(
        {"how": "Send the reason in plain words in the SMS.", "solved_already": "maybe", "basis": "gut",
         "worth": {"outside_tools": "lots"}},
        need_how=True,
    )  # fmt: skip
    assert (odd.solved_already, odd.basis, odd.worth.outside_tools) == (None, None, None)


def test_s05_fix_readiness_counts_five_and_names_the_most_useful_next() -> None:
    """S-05.fix: "2 of 5 ready for the review desk" with how and solved already given names a rough size; the risks
    never count."""
    from desk.worth import Range, Worth
    from submit import fix

    row: dict[str, Any] = {
        "how": "Send the reason in plain words.",
        "solved_already": "partly",
        "risks": "None",
    }
    assert fix.ready_count(row, None) == 2
    assert fix.next_up(row, None) == {
        "key": "worth",
        "line": "Most useful next: a rough size. A range is fine.",
    }
    hours = Worth(hours_month=Range(70, 150, "70 to 150 hours a month"))
    assert fix.ready_count(row, hours) == 3 and fix.next_up(row, hours) == {
        "key": "basis",
        "line": "Most useful next: what that is based on.",
    }
    full = {**row, "needs": "A template change", "basis": "conversation"}
    assert fix.ready_count(full, hours) == 5 and fix.next_up(full, hours) is None
    assert fix.ready_count(None, None) == 0 and (fix.next_up(None, None) or {}).get("key") == "how"


def test_s05_fix_the_size_line_reads_as_the_board() -> None:
    from desk.worth import Range, Worth
    from submit import fix

    w = Worth(
        hours_month=Range(70, 150, "70 to 150 hours a month"),
        cost_month=Range(25000, None, "about ₹25,000 a month"),
    )
    assert fix.size_line(w, "partly") == (
        "70 to 150 hours a month, about ₹25,000 a month saved, solved elsewhere: partly"
    )
    assert fix.size_line(None, "dont_know") == ""
    assert fix.size_line(Worth(outside_tools="fully"), None) == "less reliance on outside tools"


def test_s05_fix_about_is_kept_before_a_single_figure_bld_c140() -> None:
    """S-05.fix, Review.md "about ₹25,000 a month saved": the flag written per figure (`idea_worth.<m>_about`) and
    the text rebuilt from the stored numbers with it, so Check it, Send it and the edit page all keep "about"."""
    import types

    from desk.worth import parse
    from submit import fix

    assert fix.about(parse("cost_month", "about 25k")) is True
    assert fix.about(parse("hours_month", "~70")) is True
    assert fix.about(parse("cost_month", "25k")) is False
    assert fix.about(parse("hours_month", "about 70 to 150")) is False  # a range never keeps it
    assert fix.about(None) is None
    row: dict[str, Any] = {
        "hours_low": 70, "hours_high": 150, "hours_about": None,
        "cost_low": 25000, "cost_high": None, "cost_about": True,
        "revenue_low": 1200000, "revenue_high": None, "revenue_about": None,  # a row from before the flag
        "outside_tools": None,
    }  # fmt: skip

    class Conn:
        def execute(self, query: str, params: Any = None) -> Any:
            assert "by_side = 'sharer'" in query
            return types.SimpleNamespace(fetchone=lambda: row)

    w = fix.sharer_worth(Conn(), str(uuid.uuid4()))  # type: ignore[arg-type]
    assert w is not None and w.cost_month is not None
    assert w.cost_month.text == "about ₹25,000 a month"
    assert fix.size_line(w, "partly") == (
        "70 to 150 hours a month, about ₹25,000 a month saved, ₹12,00,000 a month in new revenue, "
        "solved elsewhere: partly"
    )


def test_s05_part6_who_would_help_picks_come_from_the_list(seed_rules: None) -> None:
    """E-ENUMS.sorting `helper`: the configured list, any case, kept in the list's spelling, each once; own words up
    to 140 characters (V-FIELDS.checkit/10). The Send part's row reads "Not said" until something is said."""
    from submit import config, helpers
    from submit.errors import Refused

    li = config.lists()
    picks, words = helpers.read(
        {"picks": ["someone from tech", "Data or reports", "Someone from tech"], "text": "  a  branch head "},
        li,
    )
    assert picks == ["Someone from tech", "Data or reports"] and words == "a branch head"
    assert helpers.read({"picks": []}, li) == ([], None)
    for bad in ({"picks": ["The canteen"]}, {"picks": "Someone from tech"}, {"picks": [], "text": 7}):
        with pytest.raises(Refused) as err:
            helpers.read(bad, li)
        assert err.value.code == "field_needed"
    with pytest.raises(Refused) as err:
        helpers.read({"picks": [], "text": "x" * 141}, li)
    assert (err.value.field, err.value.message) == ("text", "Keep it to 140 characters.")
    assert helpers.line([], None) == "Not said"
    assert helpers.line(["Someone at a branch"], "a branch head") == "Someone at a branch and a branch head"


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


class _NoQuestions:
    """A connection whose only answer is "no question set": `edit.window` asks for one and nothing else."""

    def execute(self, *_args: Any) -> Any:
        class _Rows:
            def fetchone(self) -> None:
                return None

        return _Rows()


@pytest.mark.parametrize("status", ["picked", "not_now", "not_picked", "withdrawn", "merged", "shipped"])
def test_s06b_a_closed_window_always_has_a_line(status: str) -> None:
    """S-06B, L-SUBMIT.edit/5 (review of c/s06b): an idea that has moved on without the desk opening it, reached by
    its edit address, still gets the NOT DRAWN closed line, so the page never shows an empty status."""
    from submit import edit

    shared = dt.datetime(2026, 11, 14, 4, 35, tzinfo=dt.UTC)
    idea = {
        "id": "00000000-0000-4000-8000-000000000001",
        "status": status,
        "opened_at": None,
        "edit_closes_at": shared + dt.timedelta(days=3),
    }
    w = edit.window(_NoQuestions(), idea, shared + dt.timedelta(hours=1))  # type: ignore[arg-type]
    assert w["open"] is False
    assert w["line"] == (
        "The time for changes has ended, so the idea itself can’t be changed now. Write to the review desk in the "
        "conversation."
    )
    open_idea = {**idea, "status": "with_review_desk"}
    assert "line" not in edit.window(_NoQuestions(), open_idea, shared + dt.timedelta(hours=1))  # type: ignore[arg-type]


def test_s06b_files_are_named_by_their_ids_only() -> None:
    """BLD-C161: Save's `files` takes attachment IDs only; anything else is refused before the database is asked."""
    from submit import edit
    from submit.errors import Refused

    assert edit._file_ids({"added": ["ATT-2026-000123", "ATT-2026-000123"]}, "added") == ["ATT-2026-000123"]
    assert edit._file_ids({}, "removed") == []
    for bad in (
        {"added": "ATT-2026-000123"},
        {"added": ["x"]},
        {"added": [1]},
        {"added": ["ATT-2026-1"] * 101},
    ):
        with pytest.raises(Refused):
            edit._file_ids(bad, "added")
