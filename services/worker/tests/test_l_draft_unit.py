"""L-DRAFT without the stack (BLD-C070 to BLD-C075): which parts a message could change, the person's own values,
the why lines and the receipt in the boards' words, the saved labels, masking before anything else sees the words,
and the draft-part agent's check, drop and fake. Synthetic text only."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

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
        "status": "Saved at 8:42 pm",
        "my_ideas": "Saved 8:42 pm Friday, on your phone",
    }
    yesterday = dt.datetime(2026, 11, 16, 10, 5, tzinfo=IST)
    mine = labels.saved_labels(yesterday, "laptop", True, now)
    assert mine is not None
    assert mine["sidebar"] == "Yesterday, on this laptop"
    assert mine["my_ideas"] == "Saved yesterday, on this laptop"
    assert mine["prompt_line"] == "Saved on this laptop, 10:05 am."
    assert labels.saved_labels(now, "laptop", True, now)["status"] == "Saved at 1:38 pm"
    assert labels.message_label(now - dt.timedelta(seconds=20), "laptop", True, now) == "Just now"
    assert labels.message_label(friday, "phone", False, now) == "Friday, 8:42 pm, on your phone"
    assert labels.day(dt.datetime(2026, 11, 2, 9, 0, tzinfo=IST), now) == "Monday 2 November"


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
