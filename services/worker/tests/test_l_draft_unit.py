"""L-DRAFT without the stack (BLD-C070 to BLD-C075): which parts a message could change, the person's own values,
the why lines and the receipt in the boards' words, the saved labels, masking before anything else sees the words,
and the draft-part agent's check, drop and fake. Synthetic text only."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, cast

import pytest

from draft import adapters, labels, parts
from draft.config import DEFAULT_DRAFTING, DEFAULT_PROMISES, build
from draft.runs import result_of
from gateway import checks, fakes
from gateway.spec import load
from rules import load_rule

ROOT = Path(__file__).resolve().parents[3]
AGENTS = ROOT / "agents"
SEED = ROOT / "seed" / "company-repo"
EXAMPLES = AGENTS / "draft-part" / "examples"
RULES = build(DEFAULT_DRAFTING, DEFAULT_PROMISES)
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
W1 = (
    'When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 '
    "means, so they call the branch."
)
W2 = "Our branch takes about 40 calls a day like this, and each one takes 5 to 10 minutes."


def example(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    return data


# ---- L-DRAFT.parts/3, /4: when parts form and which a message re-runs ---------------------------------------------


def test_l_draft_rules_seed_matches_the_defaults_bld_c070() -> None:
    seeded = load_rule(SEED, "drafting").data
    for key in (
        "parts_from_chars",
        "similar_from_chars",
        "run_stale_seconds",
        "latency_days",
        "default_means_ms",
    ):
        assert seeded[key] == DEFAULT_DRAFTING[key], key
    assert seeded["parts_from_chars"] == 25 and seeded["similar_from_chars"] == 50  # L-DRAFT.parts/3
    assert load_rule(SEED, "promises").data["draft"] == DEFAULT_PROMISES  # 30 characters, 30 days


def test_l_draft_parts_4_a_message_reruns_only_what_it_could_change() -> None:
    filled = {
        "title": ("filled", {"title": "T", "summary": "S", "pinned": []}),
        "often": ("filled", "About 40 calls a day"),
        "who": ("filled", ["Investors"]),
        "value": ("filled", ["saves_time"]),
        "area": ("filled", "Investor service"),
    }
    # Nothing about frequency, worth, groups or areas: only the title and summary take it in.
    assert parts.affected(
        "It started after the new layout went live.", filled, RULES.affects, RULES.area
    ) == ["title"]
    got = parts.affected("Distributors ask about it every week.", filled, RULES.affects, RULES.area)
    assert got == ["title", "often", "who", "area"]  # distributors are a group and an area
    # An empty or failed part is always tried again.
    empty = {**filled, "often": ("waiting", None), "area": ("failed", None)}
    assert parts.affected("It started after the new layout.", empty, RULES.affects, RULES.area) == [
        "title",
        "often",
        "area",
    ]


def test_l_draft_parts_4_a_masked_detail_or_a_bare_number_reruns_neither_often_nor_worth_bld_c033() -> None:
    filled = {
        "title": ("filled", {"title": "T", "summary": "S", "pinned": []}),
        "often": ("filled", "About 40 calls a day"),
        "value": ("filled", ["saves_time"]),
    }
    for text in ("He read out Folio ••••89 and Phone ••••10 on the call.", "Form 2B is the one they reject."):
        got = parts.affected(text, filled, RULES.affects, RULES.area)
        assert "often" not in got and "value" not in got, text
    got = parts.affected("It happens 3x on Mondays, about 50k gone.", filled, RULES.affects, RULES.area)
    assert "often" in got and "value" in got  # a number with its unit still counts


def test_l_draft_parts_4_a_drop_or_an_empty_answer_keeps_a_filled_part_bld_c033() -> None:
    texts, q = [W1, W2], "about 40 calls a day"
    often = "About 40 calls a day"
    # "Unchanged parts keep their value": a drop, or an empty answer, while the part's own quote still stands.
    assert parts.landing("often", None, often, q, texts, dropped=True) == "keep"
    assert parts.landing("often", None, often, q, texts, dropped=False) == "keep"
    assert (
        parts.landing("value", ["not_sure"], ["saves_time"], "5 to 10 minutes", texts, dropped=False)
        == "keep"
    )
    title = {"title": "Rejection codes confuse investors", "summary": "S.", "pinned": []}
    assert parts.landing("title", None, title, "the SMS to the investor", texts, dropped=False) == "keep"
    # An edit took the quoted words out: the part is emptied, never left showing words that are gone.
    assert parts.landing("often", None, often, q, [W1], dropped=False) == "waiting"
    assert parts.landing("often", None, often, q, [W1], dropped=True) == "failed"
    # Nothing before: a drop settles to "Add it yourself" (keep -> failed); an empty answer waits for words.
    assert parts.landing("often", None, None, None, texts, dropped=True) == "keep"
    assert parts.landing("often", None, None, None, texts, dropped=False) == "waiting"
    assert parts.landing("value", ["not_sure"], None, None, texts, dropped=False) == "filled"
    # A new answer always lands.
    assert parts.landing("often", "About 60 calls a day", often, q, texts, dropped=False) == "filled"
    assert parts.still_said(q, texts) and not parts.still_said(q, [W1]) and parts.still_said(None, [])


def test_l_draft_pins_a_pinned_part_is_never_rerun() -> None:
    pinned = {
        "title": ("filled", {"title": "Mine", "summary": "S", "pinned": ["title"]}),
        "often": ("pinned", "Every day"),
        "who": ("pinned", ["Investors"]),
    }
    got = parts.affected("Investors call every day, 40 times.", pinned, RULES.affects, RULES.area)
    assert "often" not in got and "who" not in got
    assert "title" in got  # the summary is still the assistant's
    both = {"title": ("pinned", {"title": "Mine", "summary": "Mine too", "pinned": ["summary", "title"]})}
    assert "title" not in parts.affected("More words.", both, RULES.affects, RULES.area)


# ---- L-DRAFT.pins: the person's own value -------------------------------------------------------------------------


def test_l_draft_pins_the_persons_own_values_are_checked_and_tidied() -> None:
    assert parts.clean_value("title", "  Investors   call  about R07 ") == "Investors call about R07"
    assert parts.clean_value("often", "") is None
    assert parts.clean_value("who", ["Investors", "investors", "Branch staff"]) == [
        "Investors",
        "Branch staff",
    ]
    assert parts.clean_value("value", ["saves_cost", "saves_time"]) == ["saves_time", "saves_cost"]
    assert parts.clean_value("value", ["not_sure", "saves_time"]) == ["not_sure"]  # V-FIELDS.checkit/3
    for key, bad, code in (
        ("title", "x" * 71, "too_long"),
        ("title", "  ", "value_required"),
        ("who", [], "value_required"),
        ("value", ["saves_money"], "value_invalid"),
        ("similar", [], "not_editable"),
    ):
        with pytest.raises(parts.PartValueError) as err:
            parts.clean_value(key, bad)
        assert err.value.code == code


# ---- L-DRAFT.parts rule 2, rule 8: why lines and the receipt in the boards' words ---------------------------------


def test_l_draft_parts_2_every_suggestion_says_why() -> None:
    texts = [W1, W2]
    assert parts.why_for("title", {"title": "T"}, ["the SMS to the investor only says"], None, texts) == (
        "From your first sentence."
    )
    assert parts.why_for("title", {"title": "T"}, ["about 40 calls a day"], None, texts) == (
        "From your third sentence."
    )
    assert parts.why_for("often", "About 40 calls a day", ["about 40 calls a day"], None, texts) == (
        "From your words: “about 40 calls a day”"
    )
    assert parts.why_for(
        "who", ["Investors"], ["q"], "Because you mentioned investors and the branch", texts
    ) == ("Suggested because you mentioned investors and the branch.")
    assert parts.why_for("value", ["not_sure"], [], None, texts) is None
    # BLD-C194: S-04B's who and area lines with no reason keep one quote; only the sorting reason joins two.
    for key in ("who", "area"):
        assert parts.why_for(
            key, ["Investors"], ["about 40 calls a day", "5 to 10 minutes each"], None, texts
        ) == ("Suggested because you said “about 40 calls a day”.")


def test_l_draft_parts_8_receipt_copy_is_the_boards() -> None:
    after = {
        "title": {
            "title": "Investors call to ask why a redemption was rejected",
            "summary": "S",
            "pinned": [],
        },
        "area": "Investor service",
        "who": ["Investors", "KFin teams"],
        "often": "About 40 calls a day at one branch",
        "value": ["saves_time", "saves_cost"],
    }
    lines = parts.receipt(
        {},
        after,
        hidden_masked=["Folio ••••89", "PAN ••••4F", "Phone ••••10"],
        similar_found=2,
        ready=True,
    )
    assert lines == [  # reference/copy/Compose.md, state=Offline
        "Drafted a title: “Investors call to ask why a redemption was rejected”.",
        "Sorted it under Investor service, affecting investors and KFin teams.",
        "Noted how often: about 40 calls a day at one branch.",
        "Marked it as saves time and saves cost.",
        "Hid 3 personal details from everyone but you: Folio ••••89, PAN ••••4F, Phone ••••10.",
        "Found 2 similar ideas from colleagues. You can team up on the next step.",
        "Your draft is ready. Add a detail, or check it.",
    ]
    # Only what changed: the same draft again says nothing new.
    assert parts.receipt(after, after) == []
    assert parts.receipt({}, {}, hidden_masked=["Folio ••••89"]) == [
        "Hid 1 personal detail from everyone but you: Folio ••••89."
    ]
    assert parts.receipt({}, {}, all_failed=True)[0] == (
        "We couldn't build the draft just now. Your words are saved. Try again."
    )
    assert parts.suggestions(after) == ["Add what you already tried", "Change the title"]
    assert parts.suggestions({}) == ["Say how often it happens", "Say who feels it most"]


# ---- L-DRAFT.autosave/4, /6: where and when it was saved ----------------------------------------------------------


def test_l_draft_autosave_4_saved_labels() -> None:
    now = dt.datetime(2026, 11, 17, 13, 38, tzinfo=IST)  # a Tuesday
    friday = dt.datetime(2026, 11, 13, 20, 42, tzinfo=IST)
    got = labels.saved_labels(friday, "phone", False, now)
    assert got == {
        "sidebar": "Friday, on your phone",
        "resume": "Last saved on your phone, Friday 8:42 pm.",
        "prompt_day": "Friday",
        "prompt_line": "Last saved on your phone, 8:42 pm.",
        "status": "Saved Friday, 8:42 pm",  # BLD-C192: an earlier day carries its day
        "my_ideas": "Saved 8:42 pm Friday, on your phone",
    }
    yesterday = dt.datetime(2026, 11, 16, 10, 5, tzinfo=IST)
    mine = labels.saved_labels(yesterday, "laptop", True, now)
    assert mine is not None
    assert mine["sidebar"] == "Yesterday, on this laptop"
    assert mine["my_ideas"] == "Saved yesterday, on this laptop"
    assert mine["prompt_line"] == "Saved on this laptop, 10:05 am."
    # BLD-C158, S-04B.layout/4: the picked-up line always carries the day, as the sidebar does ("Today, on …").
    assert mine["resume"] == "Last saved on this laptop, yesterday 10:05 am."
    today = labels.saved_labels(now - dt.timedelta(minutes=26), "laptop", False, now)
    assert today is not None
    assert today["sidebar"] == "Today, on your laptop"
    assert today["resume"] == "Last saved on your laptop, today 1:12 pm."
    assert labels.saved_labels(now, "laptop", True, now)["status"] == "Saved at 1:38 pm"
    assert labels.message_label(now - dt.timedelta(seconds=20), "laptop", True, now) == "Just now"
    assert labels.message_label(friday, "phone", False, now) == "Friday, 8:42 pm, on your phone"
    assert labels.day(dt.datetime(2026, 11, 2, 9, 0, tzinfo=IST), now) == "Monday 2 November"


def test_l_draft_autosave_4_c_taskbar_save_bld_c192_the_save_status_names_an_earlier_day() -> None:
    """J-RECOVER/3, /6, /16, J-SIMILAR/6b, /6c (BLD-C192): S-04B's and S-05's task bar read `saved_labels.status`.
    Saved today it reads as now ("Saved at 1:12 pm"); saved on an earlier day it carries the day and time a picked-up
    message reads (BLD-C185's `earlier_label`, the one helper), lower case mid-sentence."""
    now = dt.datetime(2026, 11, 17, 13, 38, tzinfo=IST)  # a Tuesday

    def status(at: dt.datetime) -> str:
        got = labels.saved_labels(at, "phone", False, now)
        assert got is not None
        return got["status"]

    assert status(dt.datetime(2026, 11, 17, 0, 5, tzinfo=IST)) == "Saved at 12:05 am"
    assert status(now - dt.timedelta(minutes=26)) == "Saved at 1:12 pm"
    assert status(dt.datetime(2026, 11, 16, 22, 59, tzinfo=IST)) == "Saved yesterday, 10:59 pm"
    sunday = dt.datetime(2026, 11, 15, 22, 59, tzinfo=IST)
    assert status(sunday) == "Saved Sunday, 10:59 pm"
    # The same day and time the picked-up messages read (BLD-C185), from the same helper
    assert labels.earlier_label(sunday, "phone", False, now) == "Sunday, 10:59 pm, on your phone"
    assert status(dt.datetime(2026, 11, 2, 9, 0, tzinfo=IST)) == "Saved Monday 2 November, 9:00 am"


def test_s04b_layout_1_an_earlier_message_reads_with_its_day_time_and_device() -> None:
    """S-04B.layout/1, ComposeResume.md "Friday, 8:42 pm, on your phone" (BLD-C185; lane G's walk, J-RESUME/3)."""
    now = dt.datetime(2026, 11, 17, 13, 38, tzinfo=IST)
    friday = dt.datetime(2026, 11, 13, 20, 42, tzinfo=IST)
    assert labels.earlier_label(friday, "phone", False, now) == "Friday, 8:42 pm, on your phone"
    # A message picked up seconds after it was saved is still an earlier message: never "Just now"
    seconds = now - dt.timedelta(seconds=20)
    assert labels.message_label(seconds, "phone", False, now) == "Just now"
    assert labels.earlier_label(seconds, "phone", False, now) == "Today, 1:37 pm, on your phone"
    yesterday = dt.datetime(2026, 11, 16, 10, 5, tzinfo=IST)
    assert labels.earlier_label(yesterday, "laptop", False, now) == "Yesterday, 10:05 am, on your laptop"
    # Today carries its day once the minute is out, as the side bar's "Today, on your laptop" does
    assert labels.message_label(now - dt.timedelta(minutes=26), "laptop", False, now) == (
        "Today, 1:12 pm, on your laptop"
    )
    # No device known: day and time only
    assert labels.earlier_label(friday, None, False, now) == "Friday, 8:42 pm"


# ---- DEC-103: masked before anything else sees the words ----------------------------------------------------------


def test_dec_103_customer_details_are_masked_with_spans_in_the_persons_text() -> None:
    import generators  # eval/golden: synthetic values made at run time, never committed

    rng = generators.default_rng(7)
    folio, pan, phone = generators.folio(rng), generators.pan(rng), generators.mobile(rng)
    text = f"One investor, folio {folio}, called three times from {phone} and read out his PAN, {pan}."
    found = adapters.find(text)
    assert [f.kind for f in found] == ["folio", "phone", "pan"]
    for f in found:
        assert text[f.start : f.end] == f.value  # positions in the person's own text
        assert f.masked.endswith("••••" + "".join(c for c in f.value if c.isalnum())[-2:])
    hidden = adapters.preview(None, text)
    assert all(f.value not in hidden.masked for f in found)
    assert hidden.masked.startswith("One investor, folio Folio ••••")
    assert hidden.spans[0] == {"start": found[0].start, "end": found[0].end, "kind": "folio"}
    assert hidden.counts == {"folio": 1, "phone": 1, "pan": 1} and hidden.hidden_count == 3
    plain = adapters.preview(None, "Nothing to hide here, ARN-12345 is a distributor code.")
    assert plain.spans == [] and plain.masked == "Nothing to hide here, ARN-12345 is a distributor code."


# ---- L-DRAFT.parts/1-2: the draft-part agent's check, drop and fake (DEC-095, DEC-108) -----------------------------


@pytest.mark.parametrize("name", sorted(p.name for p in EXAMPLES.glob("*.json")))
def test_l_draft_parts_examples_pass_the_gateway_check(name: str) -> None:
    ex = example(name)
    assert checks.draft_part(ex["input"], ex["output"], None) == []


def test_l_draft_parts_1_a_quote_from_the_english_copy_is_refused_dec_108() -> None:
    sent = {
        "part": "often",
        "words": [
            {
                "n": 1,
                "text": "Har roz branch pe 30 se zyada investors call karte hain.",
                "english": "Every day more than 30 investors call the branch.",
            }
        ],
    }
    from_english = {**example("06-not-in-the-words.json")["output"], "part": "often"}
    from_english.update(often="More than 30 calls a day", evidence=["more than 30 investors call the branch"])
    assert any("evidence" in p for p in checks.draft_part(sent, from_english, None))
    own = {**from_english, "evidence": ["30 se zyada investors call"]}
    assert checks.draft_part(sent, own, None) == []


def test_l_draft_parts_1_no_new_numbers_no_tags_only_listed_choices() -> None:
    ex = example("03-who.json")
    out = {**ex["output"], "who": ["Investors", "Auditors"]}
    assert any("options.choices" in p for p in checks.draft_part(ex["input"], out, None))
    title = example("01-title.json")
    invented = {**title["output"], "summary": "About 400 calls a day reach the branch."}
    assert any("number" in p for p in checks.draft_part(title["input"], invented, None))
    tagged = {**title["output"], "title": "[[KFIN_EMPLOYEE_1]] gets the calls"}
    assert any("tags" in p for p in checks.draft_part(title["input"], tagged, None))
    other_part = {**title["output"], "often": "Every day"}
    assert any("another part" in p for p in checks.draft_part(title["input"], other_part, None))


def test_l_draft_parts_1_after_the_re_ask_an_unbacked_answer_is_dropped() -> None:
    ex = example("02-often.json")
    bad = {**ex["output"], "evidence": ["costs about 5 lakh a month"]}
    fixed, dropped = checks.draft_part_repair(ex["input"], bad)
    assert fixed["often"] is None and fixed["evidence"] == [] and dropped == ["often"]
    assert checks.draft_part(ex["input"], fixed, None) == []
    good, none = checks.draft_part_repair(ex["input"], ex["output"])
    assert good is ex["output"] and none == []
    value = example("04-value.json")
    fixed, _ = checks.draft_part_repair(
        value["input"], {**value["output"], "evidence": ["not in the words at all"]}
    )
    assert fixed["worth"] == ["not_sure"]


@pytest.mark.parametrize("part", ["title", "often", "who", "value", "area"])
def test_l_draft_parts_the_fake_passes_its_own_checks(part: str) -> None:
    spec = load("draft-part", AGENTS)
    words = [{"n": 1, "text": W1}, {"n": 2, "text": W2}]
    inputs: dict[str, Any] = {"part": part, "words": words}
    for name in ("03-who.json", "04-value.json", "05-area.json"):
        ex = example(name)
        if ex["input"]["part"] == part:
            inputs["options"] = ex["input"]["options"]
    out = fakes.draft_part(spec, inputs)
    assert checks.draft_part(inputs, out, None) == []
    assert out["part"] == part


def test_l_draft_parts_a_summary_sentence_does_not_end_at_rs_or_eg_bld_c033() -> None:
    assert parts.sentences(["It costs Rs. 500 a month, e.g. for couriers. Then more! And a tail"]) == [
        "It costs Rs. 500 a month, e.g. for couriers.",
        "Then more!",
        "And a tail",
    ]
    ex = example("01-title.json")
    summary = (
        "The rejection SMS only gives a code, e.g. R07. Investors don't know what it means, so they call the "
        "branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each."
    )
    assert checks.draft_part(ex["input"], {**ex["output"], "summary": summary}, None) == []
    four = summary + " They call again."
    assert any(
        "3 sentences" in p for p in checks.draft_part(ex["input"], {**ex["output"], "summary": four}, None)
    )


def test_l_draft_parts_the_fake_keeps_the_summary_and_who_limits_bld_c033() -> None:
    spec = load("draft-part", AGENTS)
    long_words = [{"n": i, "text": "Investors call the branch about " + "the same code again " * 20 + "."}
                  for i in (1, 2, 3)]  # fmt: skip
    out = fakes.draft_part(spec, {"part": "title", "words": long_words})
    assert out["summary"] and len(out["summary"]) <= parts.LIMITS["summary"]
    assert not out["summary"].endswith(" ")
    choices = [{"label": f"Group {n}", "cues": [f"cue{n}"]} for n in range(10)]
    said = [{"n": 1, "text": " ".join(f"we see cue{n} often" for n in range(10))}]
    who = fakes.draft_part(spec, {"part": "who", "words": said, "options": {"choices": choices}})
    assert len(who["who"]) == parts.MAX_PICKS == 8


def test_l_draft_parts_the_fake_plants_an_unbacked_figure_for_the_drop_path() -> None:
    spec = load("draft-part", AGENTS)
    inputs = {"part": "often", "words": [{"n": 1, "text": "It costs us a lot of money every month."}]}
    out = fakes.draft_part(spec, inputs)
    assert checks.draft_part(inputs, out, None)  # refused, so the gateway re-asks and then drops


def test_l_draft_pins_a_pinned_title_survives_a_new_answer() -> None:
    data = {
        "part": "title",
        "title": "New title",
        "summary": "New summary.",
        "evidence": ["the SMS to the investor"],
    }
    prior = {"title": "My own title", "summary": "Old summary.", "pinned": ["title"]}
    value, why, quote, _ = result_of("title", data, [{"n": 1, "text": W1}], prior)
    assert value == {"title": "My own title", "summary": "New summary.", "pinned": ["title"]}
    assert why == "From your first sentence." and quote == "the SMS to the investor"


def test_l_draft_adapters_call_c_hide_and_c_similar_by_their_names_once_they_land_bld_c038(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    import types

    import hide as hide_on_main
    import similar

    # L-HIDE is on main (BLD-C151): the draft hides through it.
    assert adapters.landed("hide", "hide_message") is hide_on_main.hide_message
    assert adapters.similar_for(cast(Any, None), "u", "T", "S") is None  # not on main yet: "couldn't check"
    seen: dict[str, Any] = {}

    def hide_message(
        conn: Any, idea_uuid: str, text: str, *, by: str, source: str, source_id: str | None = None,
        gatekeeper: bool = True,
    ) -> Any:  # fmt: skip
        seen["hide"] = (idea_uuid, text, by, source, source_id, gatekeeper)
        return adapters.Hidden("PAN ••••4F")

    hide = types.ModuleType("hide")
    hide.hide_message = hide_message
    monkeypatch.setitem(sys.modules, "hide", hide)

    class _Conn:  # no hidden details held yet: nothing for the vault to drop
        def execute(self, *_: Any) -> Any:
            return types.SimpleNamespace(fetchall=lambda: [])

    got = adapters.hide_message(
        cast(Any, _Conn()), "idea-1", "own words", by="user-1", source="edit", source_id="s-1"
    )
    assert got.masked == "PAN ••••4F"
    assert seen["hide"] == ("idea-1", "own words", "user-1", "edit", "s-1", True)  # the gatekeeper runs too

    def similar_for(conn: Any, idea_uuid: str, title: str, summary: str) -> list[dict[str, Any]] | None:
        seen["similar"] = (idea_uuid, title, summary)
        return []

    monkeypatch.setattr(similar, "similar_for", similar_for, raising=False)
    assert adapters.similar_for(cast(Any, None), "idea-1", "T", "S") == []  # none found, not "couldn't check"
    assert seen["similar"] == ("idea-1", "T", "S")


def test_l_draft_channels_origin_labels_are_the_boards() -> None:
    from draft.channels import origin_label

    now = dt.datetime(2026, 11, 17, 13, 38, tzinfo=IST)
    email = {"received_at": "2026-11-17T09:14:00+05:30", "subject": "Fwd: R07 rejections again"}
    assert (
        origin_label("email", email, now) == "From your email, today at 9:14 am: “Fwd: R07 rejections again”"
    )
    teams = {"received_at": "2026-11-16T19:02:00+05:30"}
    assert origin_label("teams", teams, now) == "From Teams, yesterday 7:02 pm"
    assert origin_label("email", {"received_at": "not a date"}, now) is None


def test_l_draft_sort_lists_from_l_sort_carry_draftings_cues() -> None:
    from draft.config import with_sorting

    lists = {
        "affects": ["Investors", "KFin teams", "AMC clients", "Others"],
        "area": ["Investor service", "Payments"],
    }
    merged = with_sorting(RULES, lists)
    assert [o.label for o in merged.affects] == ["Investors", "KFin teams", "AMC clients"]  # never "Others"
    assert "investor" in merged.affects[0].cues and merged.area[1].cues == ()
    assert with_sorting(RULES, None) is RULES


# ---- L-DRAFT.autosave/5, /7: a true offline replay only (BLD-C036) --------------------------------------------------


def test_l_draft_autosave_5_a_message_stamped_now_is_live_not_an_offline_replay_bld_c036() -> None:
    from draft.store import offline_replay

    now = dt.datetime(2026, 11, 17, 21, 0, tzinfo=IST)
    editor_at = now - dt.timedelta(seconds=20)  # the other device saved 20 seconds ago
    assert offline_replay(now, editor_at, now) is False  # a stale tab naming "now" gets "Carry on here?"
    # after the editor's last save, and a clock ahead, are not offline either
    assert offline_replay(now - dt.timedelta(seconds=5), editor_at, now) is False
    assert offline_replay(None, editor_at, now) is False
    assert offline_replay(now + dt.timedelta(minutes=5), editor_at, now) is False
    assert offline_replay(now - dt.timedelta(days=31), editor_at, now) is False  # past the 30-day window


def test_l_draft_autosave_7_typed_before_the_editors_save_or_a_minute_ago_is_a_replay_bld_c036() -> None:
    from draft.store import offline_replay

    now = dt.datetime(2026, 11, 17, 21, 0, tzinfo=IST)
    assert offline_replay(now - dt.timedelta(seconds=30), now - dt.timedelta(seconds=10), now) is True
    assert offline_replay(now - dt.timedelta(minutes=2), now, now) is True  # before the other device saved
    assert offline_replay(now - dt.timedelta(seconds=61), None, now) is True  # over a minute old
    assert offline_replay(now - dt.timedelta(days=29), now, now) is True


# ---- L-DRAFT.voice: a voice note's message from c/sarvam's voice_to_message (DEC-108, BLD-C038) ---------------------


STREAM = "5f0c2d3e-8a41-4c6b-9f7e-2b1d0c9a8e71"
HEARD = "R07 ka matlab kisi ko nahi pata, isliye sab branch ko call karte hain."
HEARD_EN = "Nobody knows what R07 means, so everyone calls the branch."


def _speech(monkeypatch: pytest.MonkeyPatch, note: Any) -> dict[str, Any]:
    """A stand-in `speech.drafts` with c/sarvam's signature."""
    import sys
    import types

    seen: dict[str, Any] = {}

    def voice_to_message(
        conn: Any, stream_id: str, *, idea_uuid: str, by_code: str, consume: bool = True
    ) -> Any:
        seen["call"] = (stream_id, idea_uuid, by_code, consume)
        return note

    pkg, mod = types.ModuleType("speech"), types.ModuleType("speech.drafts")
    mod.voice_to_message = voice_to_message
    pkg.drafts = mod
    monkeypatch.setitem(sys.modules, "speech", pkg)
    monkeypatch.setitem(sys.modules, "speech.drafts", mod)
    return seen


def _note(text: str = HEARD, text_en: str | None = HEARD_EN, lang: str | None = "hi-IN") -> Any:
    import types

    return types.SimpleNamespace(
        stream_id=STREAM, text=text, text_masked=text, spans=[], text_en=text_en,
        text_en_label="Typed up in English", translated=True, lang=lang, language="Hindi", seconds=12.0,
        summary="Voice message, 12 seconds, in Hindi", via="voice",
    )  # fmt: skip


def test_l_draft_voice_the_adapter_hands_over_the_note_once_by_c_sarvams_name_bld_c038(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _speech(monkeypatch, _note())
    got = adapters.voice_message(cast(Any, None), STREAM, idea_uuid="idea-1", by_code="CTR-0a1b2c")
    assert got == adapters.VoiceNote(text=HEARD, text_en=HEARD_EN, lang="hi")
    assert seen["call"] == (STREAM, "idea-1", "CTR-0a1b2c", True)  # consumed: the held copies go
    _speech(monkeypatch, None)  # not theirs, not finished, handed over or expired
    assert adapters.voice_message(cast(Any, None), STREAM, idea_uuid="idea-1", by_code="CTR-0a1b2c") is None
    _speech(monkeypatch, _note(text_en="  ", lang=None))  # the translation failed
    untranslated = adapters.voice_message(cast(Any, None), STREAM, idea_uuid="i", by_code="CTR-0a1b2c")
    assert untranslated == adapters.VoiceNote(text=HEARD, text_en=None, lang=None)


def test_l_draft_voice_without_speech_in_the_build_the_adapter_says_unavailable_bld_c038(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "speech.drafts", None)  # absent, whatever the checkout holds
    with pytest.raises(adapters.VoiceUnavailable):
        adapters.voice_message(cast(Any, None), STREAM, idea_uuid="idea-1", by_code="CTR-0a1b2c")
    assert adapters.landed("no_such_lane_pkg.drafts", "voice_to_message") is None  # a missing parent too


def test_l_draft_voice_a_landed_package_that_breaks_on_import_is_an_error_bld_c038(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import sys

    pkg = tmp_path / "brokenlane"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "drafts.py").write_text("import no_such_dependency_xyz\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "brokenlane", raising=False)
    with pytest.raises(ModuleNotFoundError):
        adapters.landed("brokenlane.drafts", "voice_to_message")


def test_l_draft_voice_4_sent_as_heard_keeps_the_own_words_and_the_english_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from draft.store import Owner, _from_voice

    owner = Owner("0b5e7f7a-1c2d-4e3f-8a9b-0c1d2e3f4a5b", "CTR-0a1b2c")
    seen = _speech(monkeypatch, _note())
    assert _from_voice(cast(Any, None), owner, "idea-1", STREAM, HEARD, None) == (HEARD, HEARD_EN, "hi")
    assert seen["call"] == (STREAM, "idea-1", "CTR-0a1b2c", True)
    _speech(monkeypatch, _note())
    assert _from_voice(cast(Any, None), owner, "idea-1", STREAM, None, None) == (HEARD, HEARD_EN, "hi")
    _speech(monkeypatch, _note())
    assert _from_voice(cast(Any, None), owner, "idea-1", STREAM, "  ", None) == (HEARD, HEARD_EN, "hi")


def test_l_draft_voice_2_words_changed_before_sending_are_kept_without_the_notes_english(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from draft.store import Owner, _from_voice

    owner = Owner("0b5e7f7a-1c2d-4e3f-8a9b-0c1d2e3f4a5b", "CTR-0a1b2c")
    changed = HEARD + " Roz 40 call aate hain."
    _speech(monkeypatch, _note())
    assert _from_voice(cast(Any, None), owner, "idea-1", STREAM, changed, None) == (changed, None, "hi")
    _speech(monkeypatch, None)  # nothing to hand over: the words in the box, as sent
    assert _from_voice(cast(Any, None), owner, "idea-1", STREAM, changed, None) == (changed, None, None)
    seen = _speech(monkeypatch, _note())
    got = _from_voice(cast(Any, None), owner, "idea-1", "not-a-stream", changed, None)
    assert got == (changed, None, None)
    assert "call" not in seen  # a malformed stream id is never looked up


def test_l_draft_voice_without_speech_the_message_route_answers_voice_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    from draft.store import DraftError, Owner, _from_voice

    owner = Owner("0b5e7f7a-1c2d-4e3f-8a9b-0c1d2e3f4a5b", "CTR-0a1b2c")
    monkeypatch.setitem(sys.modules, "speech.drafts", None)
    with pytest.raises(DraftError) as err:
        _from_voice(cast(Any, None), owner, "idea-1", STREAM, HEARD, None)
    assert (err.value.status, err.value.body()) == (503, {"error": "voice_unavailable"})


# ---- L-INBOX "Draft kept": refs.via and the action by source (J-RESUME/3, /6) ---------------------------------------


@pytest.mark.parametrize(
    ("via", "label"), [("email", "Check and send"), ("teams", "Check and send"), ("phone", "Carry on")]
)
def test_l_inbox_draft_kept_posts_refs_via_with_its_action_j_resume_3_6(
    monkeypatch: pytest.MonkeyPatch, via: str, label: str
) -> None:
    import notify
    from draft.channels import kept
    from draft.store import Owner

    owner = Owner("0b5e7f7a-1c2d-4e3f-8a9b-0c1d2e3f4a5b", "CTR-0a1b2c")
    posted: list[tuple[Any, ...]] = []
    monkeypatch.setattr(notify, "post", lambda conn, kind, to, **kw: posted.append((kind, to, kw)))
    kept(cast(Any, None), owner, "idea-1", via)
    [(kind, to, kw)] = posted
    assert (kind, to, kw["refs"]) == ("draft_kept", [owner.user_id], {"via": via})  # never `channel`
    [action] = kw["actions"]
    assert (action.label, action.style, action.to) == (label, "primary", "/share/idea-1")  # S-04B
    with pytest.raises(ValueError):
        kept(cast(Any, None), owner, "idea-1", "web")


def test_l_draft_l_hide_the_vault_scope_is_hide_core_scope_for_uuid_normalised_bld_c151() -> None:
    # One scope for the draft whoever builds it: L-HIDE's details, the values an edit took out, and the run.
    from draft import runs
    from hide.core import scope_for

    lower = "6f1c2a8e-3b4d-4e5f-8a9b-0c1d2e3f4a5b"
    for given in (lower, lower.upper(), lower.replace("-", "")):
        assert adapters.vault_scope(given) == runs.scope(given) == scope_for(lower) == f"DRAFT-{lower}"


# ---- S-04B.layout/2: each message keeps its own receipt (BLD-C184) ------------------------------------------------


def test_s04b_layout_2_own_receipts_keep_the_latest_non_empty_receipt_per_message() -> None:
    """Lane C's review of c/walk-a-1: a later run with no lines never blanks a message's receipt."""
    from draft.store import own_receipts

    t0 = dt.datetime(2026, 11, 19, 10, 0, tzinfo=IST)
    m1, m2 = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"
    messages = [
        {"id": m1, "at": t0.isoformat()},
        {"id": m2, "at": (t0 + dt.timedelta(minutes=5)).isoformat()},
    ]
    hid = ["Drafted a title: “Synthetic title”.", "Hid 1 personal detail from everyone but you: PAN ••••8Z."]
    often = ["Noted how often: about 10 a day."]

    def run(mid: str | None, minutes: int, lines: list[str]) -> dict[str, object]:
        return {
            "message_id": mid,
            "started_at": t0 + dt.timedelta(minutes=minutes, seconds=1),
            "receipt": lines,
        }

    # A later run of the same message that ends with no lines keeps the earlier receipt
    assert own_receipts(messages[:1], [run(m1, 0, hid), run(m1, 1, [])]) == {m1: hid}
    # ... and so does a "Try again" with no message and no lines, which belongs to the newest message
    assert own_receipts(messages[:1], [run(m1, 0, hid), run(None, 2, [])]) == {m1: hid}
    # A later run with new lines shows the new ones
    edited = ["Changed the title to “Synthetic title, edited”."]
    assert own_receipts(messages[:1], [run(m1, 0, hid), run(m1, 1, edited)]) == {m1: edited}
    # Two messages keep their own; a message-less run after the second belongs to the second
    both = own_receipts(messages, [run(m1, 0, hid), run(m2, 5, often), run(None, 6, [])])
    assert both == {m1: hid, m2: often}
    retried = ["Your draft is ready. Add a detail, or check it."]
    assert own_receipts(messages, [run(m1, 0, hid), run(m2, 5, often), run(None, 6, retried)]) == {
        m1: hid,
        m2: retried,
    }
    assert own_receipts([], [run(m1, 0, hid)]) == {}


def test_l_draft_parts_bld_c194_because_and_quotes_in_are_one_builder() -> None:
    """The reason builder S-04B's parts and S-05's sorting both use (BLD-C194): a reason, or the first two quotes as
    Review.md joins them; `quotes_in` reads back the quotes `quoted` wrote, still masked."""
    line = parts.quoted(["about 40 calls a day", "5 to 10 minutes each", "a third"])
    assert line == "From your words: “about 40 calls a day” and “5 to 10 minutes each”"
    assert parts.quotes_in(line) == ["about 40 calls a day", "5 to 10 minutes each"]
    assert parts.quotes_in("From your words: “with folio Folio ••••17”") == ["with folio Folio ••••17"]
    assert (
        parts.because(None, ["about 40 calls a day"]) == "Suggested because you said “about 40 calls a day”."
    )
    assert (
        parts.because(None, ["about 40 calls a day", "5 to 10 minutes each"])
        == "Suggested because you said “about 40 calls a day” and “5 to 10 minutes each”."
    )
    assert parts.because("Because it’s about investors", []) == "Suggested because it’s about investors."
    assert parts.because(None, []) == "Suggested because of your words."
