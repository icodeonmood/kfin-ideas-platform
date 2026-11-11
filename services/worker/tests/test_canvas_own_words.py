"""DEC-095 and DEC-097 (BLD-C020 to C029): canvas-assist suggests only what the person's own words say, works
figures only from their numbers and the allowed basic assumptions, and the gateway checks both.

No stack needed: the grounding check, the arithmetic, the repair and its fallbacks, the gateway's mend after the
re-ask, the fake builder over the golden set, what the confirm step shows, and the readers that must never fall
back to the person's words. The runs through `run_agent`, the review desk's summary edit and the database
readers are in `test_canvas_own_words_stack.py`.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from evalrunner import canvas_assist as ca_eval
from gateway import checks, core, fakes, grounding
from gateway.spec import load
from index.indexer import card_summary
from pii.restore import restore
from scan import view
from scan.inputs import assumptions, taxonomy_slice
from scan.matching import safe_summary
from scan.pipeline import FLAG_DROPPED, FLAG_SUMMARY_BLANK, with_drop_flags

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "eval" / "golden" / "canvas_assist.jsonl"
SEED = ROOT / "seed" / "company-repo"
ALLOWED = assumptions(SEED)
DETAILS = (
    "Every morning [[KFIN_EMPLOYEE_1]] in MF ops re-keys about 40 switch requests that arrive by email. "
    "It takes two hours and the same requests often come back as NIGO."
)


def answers(**over: Any) -> dict[str, Any]:
    base = copy.deepcopy(ca_eval.SKELETON)
    base["details"] = DETAILS
    base["value"]["category"] = "cost_saving"
    for path, value in over.items():
        grounding._set(base, path.replace("__", "."), value)
    return base


def sent_for(a: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "canvas_answers": a,
        "taxonomy_slice": {"lobs": [{"id": "LOB-mf"}], "areas": [{"id": "AREA-process"}]},
        "gatekeeper": {"kind": {"value": "idea_problem", "confidence": 0.9}},
        "past_corrections": extra.get("past_corrections", []),
        "assumptions": extra.get("assumptions", ALLOWED),
        **({"mode": extra["mode"]} if "mode" in extra else {}),
    }


def output(a: dict[str, Any], **suggest: tuple[Any, list[str]]) -> dict[str, Any]:
    """A schema-valid output: the person's answers, plus the given suggestions with their quotes."""
    out = copy.deepcopy(a)
    out["kind"] = out.get("kind") or "problem"
    out["ecosystem"]["solved_elsewhere"] = (
        out["ecosystem"]["solved_elsewhere"] or "dont_know"
    )  # no-answer value
    out["one_line"] = out.get("one_line") or "Switch requests from email are re-keyed by hand every morning"
    out["neutral_summary"] = "Switch requests that arrive by email are re-keyed by hand and often come back."
    out["system"] = {
        "scope": "lob", "lobs": ["LOB-mf"], "areas": ["AREA-process"], "systems": [], "roles_affected": [],
    }  # fmt: skip
    out["provenance"] = {"details": "submitter", "value.category": "submitter"}
    out["evidence"] = {"neutral_summary": ["re-keys about 40 switch requests that arrive by email"]}
    out["assumptions"] = []
    if not a.get("kind"):
        out["provenance"]["kind"] = "suggested"
        out["evidence"]["kind"] = ["the same requests often come back as NIGO"]
    if not a.get("one_line"):
        out["provenance"]["one_line"] = "suggested"
        out["evidence"]["one_line"] = ["re-keys about 40 switch requests that arrive by email"]
    for path, (value, quotes) in suggest.items():
        p = path.replace("__", ".")
        grounding._set(out, p, value)
        out["provenance"][p] = "suggested"
        out["evidence"][p] = quotes
    out["flags_for_reviewer"] = []
    out["confidence"] = {
        k: 0.5 for k in ("value.category", "value.play", "system.scope", "system.areas", "system.systems")
    }
    out["strength"] = {"score": 1, "next_best": ["Add what it is worth"]}
    return out


def listed(*ids: str) -> list[dict[str, str]]:
    says = {a["id"]: a["says"] for a in ALLOWED}
    return [{"id": i, "says": says.get(i, "A made-up assumption")} for i in ids]


def schema_ok(out: dict[str, Any]) -> bool:
    return not list(Draft202012Validator(load("canvas-assist").schema).iter_errors(out))


# ---- the rules -------------------------------------------------------------------------------------------------


def test_the_allowed_assumptions_come_from_the_rules() -> None:
    assert {a["id"]: a["value"] for a in ALLOWED} == {
        "working_days_per_month": 22, "working_hours_per_day": 8, "months_per_year": 12,
    }  # fmt: skip


# ---- quotes ----------------------------------------------------------------------------------------------------


def test_a_suggestion_backed_by_the_persons_words_passes() -> None:
    a = answers()
    out = output(
        a, who__today_alternative=("Re-keyed by hand from email", ["re-keys about 40 switch requests"])
    )
    assert schema_ok(out)
    assert grounding.ungrounded(sent_for(a), out) == {}
    assert checks.canvas_assist(sent_for(a), out, None) == []


@pytest.mark.parametrize(
    ("quote", "code"),
    [
        ("re-keys about 40 switch requests that arrive by fax", "not_found"),  # one word changed
        ("re-keys … switch requests", "not_found"),  # an ellipsis joins two phrases
        ("ops", "too_short"),
        ("requeststhatarrive", "too_short"),  # one long word is not enough any more (B3)
        ("of the", "too_short"),  # two stopwords say nothing (B3)
        ("witch requests", "not_found"),  # word boundaries: not inside "switch" (B3)
    ],
)
def test_a_quote_that_is_not_word_for_word_or_says_nothing_fails(quote: str, code: str) -> None:
    a = answers()
    out = output(a, who__today_alternative=("Re-keyed by hand from email", [quote]))
    assert grounding.ungrounded(sent_for(a), out) == {"who.today_alternative": code}


def test_spacing_case_dashes_and_surrounding_marks_do_not_matter_but_tags_must_match_exactly() -> None:
    a = answers(details=DETAILS.replace("re-keys", "re–keys"))
    loose = output(
        a, who__today_alternative=("Re-keyed by hand", ['"IN MF OPS  re-keys about 40 switch requests."'])
    )
    assert grounding.ungrounded(sent_for(a), loose) == {}
    tag_case = output(
        a, who__today_alternative=("Re-keyed by hand", ["[[kfin_employee_1]] in MF ops re-keys"])
    )
    assert grounding.ungrounded(sent_for(a), tag_case) == {"who.today_alternative": "not_found"}
    tag_exact = output(
        a, who__today_alternative=("Re-keyed by hand", ["[[KFIN_EMPLOYEE_1]] in MF ops re-keys"])
    )
    assert grounding.ungrounded(sent_for(a), tag_exact) == {}


def test_hindi_matches_whatever_the_unicode_form_and_joiners() -> None:
    """B7: NFC, and zero-width joiners and non-joiners removed on both sides."""
    import unicodedata

    hindi = "हर रोज़ फ़ॉर्म वापस आते हैं और दोबारा भेजने में दो दिन लगते हैं"
    a = answers(details=unicodedata.normalize("NFD", hindi).replace(" ", " ‌", 3))
    quote = unicodedata.normalize("NFC", "फ़ॉर्म वापस आते हैं").replace("ॉ", "‍ॉ")
    out = output(a, who__today_alternative=("Forms come back every day", [quote]))
    out["evidence"]["neutral_summary"] = ["दोबारा भेजने में दो दिन लगते हैं"]
    out["evidence"].pop("kind", None)
    out["evidence"].pop("one_line", None)
    out["provenance"].pop("one_line", None)
    out["kind"] = "problem"
    out["provenance"].pop("kind", None)
    out["one_line"] = ""
    assert grounding.ungrounded(sent_for(a), out) == {}


def test_a_quote_may_not_join_two_answers() -> None:
    """B8: each answer is checked on its own, so a quote cannot stitch the end of one to the start of another."""
    a = answers(details="Forms come back by courier.", who__today_alternative="We key them twice")
    out = output(a, solution__needs=("Courier and keying", ["back by courier. We key them"]))
    out["evidence"] = {"solution.needs": ["back by courier. We key them"]}
    out["provenance"] = {
        "details": "submitter", "value.category": "submitter", "who.today_alternative": "submitter",
        "solution.needs": "suggested",
    }  # fmt: skip
    out["kind"], out["one_line"], out["neutral_summary"] = "problem", "", ""
    assert grounding.ungrounded(sent_for(a), out) == {"solution.needs": "not_found"}


def test_quotes_come_only_from_the_persons_own_text() -> None:
    other = "Reviewer note: branch staff scan every mandate twice"
    a = answers()
    out = output(a, who__today_alternative=("Scanned twice", ["branch staff scan every mandate twice"]))
    sent = sent_for(a, past_corrections=[{"note": other}])
    assert grounding.ungrounded(sent, out) == {"who.today_alternative": "not_found"}
    a2 = answers(attachments=[{"id": "ATT-1", "name": "x.pdf", "state": "clean", "digest": other}])
    assert (
        grounding.ungrounded(sent_for(a2), output(a2, who__today_alternative=("Scanned twice", [other])))
        == {}
    )


def test_unmarked_additions_invented_references_and_stray_evidence_are_named() -> None:
    a = answers()
    out = output(a)
    out["solution"]["risks"] = "May need a compliance check"  # added with no provenance and no quote
    out["ecosystem"]["references"] = [{"kind": "note", "value": "Some fintechs do this", "player": "fintech"}]
    out["evidence"]["details"] = ["re-keys about 40 switch requests"]  # evidence for the person's own answer
    assert grounding.ungrounded(sent_for(a), out) == {
        "solution.risks": "not_marked",
        "ecosystem.references": "not_given",
        "details": "stray_evidence",
    }


def test_the_persons_answers_no_answer_values_and_the_default_kind_need_no_quote() -> None:
    a = answers(
        who__today_alternative="We key it by hand", ecosystem__solved_elsewhere=None, value__category=None
    )
    out = output(a)
    out["ecosystem"]["solved_elsewhere"] = "dont_know"
    out["value"]["category"] = "not_sure"
    out["provenance"] |= {"ecosystem.solved_elsewhere": "suggested", "value.category": "suggested"}
    out["provenance"].pop("kind")
    out["evidence"].pop("kind")  # "problem" with no provenance: the platform's default (DEC-097)
    assert grounding.ungrounded(sent_for(a), out) == {}
    guessed = copy.deepcopy(out)
    guessed["kind"] = "business_idea"  # any other kind is a guess and needs its quote
    assert grounding.ungrounded(sent_for(a), guessed) == {"kind": "not_marked"}


def test_problems_name_paths_and_rules_never_the_quoted_text() -> None:
    a = answers()
    secret = "fifteen lakh saved on courier every year"
    out = output(a, value__estimate__inr_saved_per_year=(1500000, [secret]))
    problems = checks.canvas_assist(sent_for(a), out, None)
    assert problems and all(secret not in p and "lakh" not in p for p in problems)
    assert problems[0].startswith("value.estimate.inr_saved_per_year: ")


# ---- figures and assumptions (DEC-097) -----------------------------------------------------------------------------


def test_a_figure_worked_with_a_listed_assumption_passes_and_without_it_fails() -> None:
    a = answers(
        details="In the investor service team, 10 people each spend 2 hours a day re-keying address changes."
    )
    quotes = ["10 people each spend 2 hours a day"]
    out = output(a, value__estimate__hours_saved_per_month=(440, quotes))
    out["evidence"] = {"value.estimate.hours_saved_per_month": quotes, "neutral_summary": quotes}
    out["provenance"].pop("kind"), out["provenance"].pop("one_line")
    out["one_line"] = ""
    out["assumptions"] = listed("working_days_per_month")
    assert grounding.ungrounded(sent_for(a), out) == {}
    unlisted = copy.deepcopy(out)
    unlisted["assumptions"] = []
    assert grounding.ungrounded(sent_for(a), unlisted) == {
        "value.estimate.hours_saved_per_month": "new_number"
    }


def test_estimates_read_indian_forms_and_number_words() -> None:
    a = answers(
        details="We pay Rs. 5 lakh a month to re-key forms, and ten people spend 2 hours a day on it."
    )
    figures = {
        "inr_saved_per_year": (6000000, ["We pay Rs. 5 lakh a month"]),  # 5 lakh × 12 months
        "hours_saved_per_month": (440, ["ten people spend 2 hours a day"]),  # word "ten"
        "inr_revenue_one_time": (500000, ["We pay Rs. 5 lakh a month"]),  # their own figure as it stands
    }
    out = output(a, **{f"value__estimate__{k}": v for k, v in figures.items()})
    out["evidence"] = {f"value.estimate.{k}": v[1] for k, v in figures.items()}
    out["evidence"]["neutral_summary"] = ["We pay Rs. 5 lakh a month to re-key forms"]
    out["provenance"].pop("kind"), out["provenance"].pop("one_line")
    out["one_line"] = ""
    out["assumptions"] = listed("months_per_year", "working_days_per_month")
    assert grounding.ungrounded(sent_for(a), out) == {}
    assert grounding.numbers("₹1,20,000 once and 2 crore later, 3,000 forms, Rs.750") == {
        120000.0, 20000000.0, 3000.0, 750.0,
    }  # fmt: skip


def test_unlisted_unused_and_misworded_assumptions_are_named_and_mended() -> None:
    a = answers(details="Two people spend the whole day re-keying refund requests from email every day.")
    quotes = ["Two people spend the whole day"]
    out = output(a, value__estimate__inr_saved_per_year=(720000, quotes))
    out["evidence"] = {"value.estimate.inr_saved_per_year": quotes, "neutral_summary": quotes}
    out["provenance"].pop("kind"), out["provenance"].pop("one_line")
    out["one_line"] = ""
    out["assumptions"] = [
        {"id": "average_salary_per_month", "says": "₹30,000 salary a month"},  # not on the list
        {"id": "months_per_year", "says": "twelve months"},  # on the list, words changed
        {"id": "working_hours_per_day", "says": "8 working hours in a day"},  # on the list, unused
    ]
    bad = grounding.ungrounded(sent_for(a), out)
    assert bad == {
        "value.estimate.inr_saved_per_year": "new_number",
        "assumptions.average_salary_per_month": "unknown_assumption",
        "assumptions.months_per_year": "unused_assumption",
        "assumptions.working_hours_per_day": "unused_assumption",
    }
    fixed, dropped = grounding.repair(sent_for(a), out)
    assert fixed["value"]["estimate"]["inr_saved_per_year"] is None and fixed["assumptions"] == []
    assert (
        "value.estimate.inr_saved_per_year" in dropped
        and checks.canvas_assist(sent_for(a), fixed, None) == []
    )
    worded = copy.deepcopy(out)
    worded["value"]["estimate"]["inr_saved_per_year"] = 24  # two people × 12 months
    worded["assumptions"] = [{"id": "months_per_year", "says": "twelve months"}]
    assert grounding.ungrounded(sent_for(a), worded) == {"assumptions.months_per_year": "assumption_words"}
    mended, _ = grounding.repair(sent_for(a), worded)
    assert mended["assumptions"] == listed("months_per_year")


def test_the_notes_working_may_use_only_their_figures_the_results_and_listed_assumptions() -> None:
    a = answers(
        details="In the investor service team, 10 people each spend 2 hours a day re-keying address changes."
    )
    quotes = ["10 people each spend 2 hours a day"]
    out = output(
        a,
        value__estimate__hours_saved_per_month=(440, quotes),
        value__estimate__note=("2 hours a day × 10 people × 22 working days = 440 hours a month", quotes),
    )
    out["evidence"]["neutral_summary"] = quotes
    out["provenance"].pop("kind"), out["provenance"].pop("one_line")
    out["evidence"].pop("kind"), out["evidence"].pop("one_line")
    out["one_line"] = ""
    out["assumptions"] = listed("working_days_per_month")
    assert grounding.ungrounded(sent_for(a), out) == {}
    padded = copy.deepcopy(out)
    padded["value"]["estimate"]["note"] = "2 hours × 10 people × 22 days × ₹300 an hour = ₹1,32,000 a month"
    assert grounding.ungrounded(sent_for(a), padded) == {"value.estimate.note": "new_number"}


# ---- the repair and its fallbacks (B2) ----------------------------------------------------------------------------


def test_repair_drops_only_the_unsupported_suggestions_and_then_passes() -> None:
    a = answers()
    out = output(
        a,
        value__estimate__inr_saved_per_year=(500000, ["saves us five lakh a year"]),
        who__today_alternative=("Re-keyed by hand from email", ["re-keys about 40 switch requests"]),
    )
    fixed, dropped = grounding.repair(sent_for(a), out)
    assert dropped == ["value.estimate.inr_saved_per_year"]
    assert fixed["value"]["estimate"]["inr_saved_per_year"] is None
    assert "value.estimate.inr_saved_per_year" not in fixed["provenance"]
    assert "value.estimate.inr_saved_per_year" not in fixed["evidence"]
    assert fixed["who"]["today_alternative"] == "Re-keyed by hand from email"  # kept: it was backed
    assert schema_ok(fixed) and checks.canvas_assist(sent_for(a), fixed, None) == []
    assert out["value"]["estimate"]["inr_saved_per_year"] == 500000  # the original is not changed


def _all_unbacked(a: dict[str, Any]) -> dict[str, Any]:
    out = output(a)
    out["one_line"] = "An invented line"
    out["evidence"]["one_line"] = ["nothing like this"]
    out["kind"] = "business_idea"
    out["evidence"]["kind"] = ["not in the text either"]
    out["evidence"]["neutral_summary"] = ["not in the text"]
    return out


def test_a_dropped_one_line_becomes_the_persons_first_sentence_and_kind_the_default() -> None:
    long = " ".join(f"word{n}" for n in range(30)) + ". Second sentence here."
    a = answers(details=long)
    fixed, dropped = grounding.repair(sent_for(a), _all_unbacked(a))
    assert dropped == ["kind", "neutral_summary", "one_line"]
    first20 = " ".join(f"word{n}" for n in range(20))
    assert fixed["one_line"] == first20 + "…"
    assert fixed["evidence"]["one_line"] == [first20] and fixed["provenance"]["one_line"] == "suggested"
    assert (
        fixed["kind"] == "problem" and "kind" not in fixed["provenance"] and "kind" not in fixed["evidence"]
    )
    assert fixed["neutral_summary"] == "" and "neutral_summary" not in fixed["evidence"]
    assert schema_ok(fixed) and checks.canvas_assist(sent_for(a), fixed, None) == []


@pytest.mark.parametrize(
    ("details", "line"),
    [
        (
            "Rs. 5 lakh goes on courier every year. We could stop it.",
            "Rs. 5 lakh goes on courier every year.",
        ),
        ("Hi. We see 40 forms a day come back.", "Hi. We see 40 forms a day come back."),  # one-word sentence
        ("No. 17 counter is always full. People wait.", "No. 17 counter is always full."),
        ("Forms wapas aate hain। Dobara bhejna padta hai.", "Forms wapas aate hain।"),
    ],
)
def test_the_first_sentence_survives_abbreviations_and_one_word_sentences(details: str, line: str) -> None:
    a = answers(details=details)
    fixed, _ = grounding.repair(sent_for(a), _all_unbacked(a))
    assert fixed["one_line"] == line
    assert schema_ok(fixed) and checks.canvas_assist(sent_for(a), fixed, None) == []


def test_with_no_usable_words_the_fallbacks_are_schema_valid_and_unclaimed() -> None:
    a = answers(details="")
    fixed, _ = grounding.repair(sent_for(a), _all_unbacked(a))
    assert fixed["one_line"] == "" and "one_line" not in fixed["provenance"]
    assert fixed["kind"] == "problem" and "kind" not in fixed["provenance"]
    assert schema_ok(fixed) and checks.canvas_assist(sent_for(a), fixed, None) == []


def test_attachment_mode_keeps_its_kind() -> None:
    a = answers()
    out = output(a)
    out["kind"] = "business_idea"
    out["provenance"].pop("kind")
    out["evidence"].pop("kind")
    assert "kind" not in grounding.ungrounded(sent_for(a, mode="attachment"), out)
    fixed, _ = grounding.repair(sent_for(a, mode="attachment"), out)
    assert fixed["kind"] == "business_idea"


def test_the_gateway_mends_only_when_dropping_is_enough() -> None:
    spec = load("canvas-assist")
    a = answers()
    bad = output(a, value__estimate__inr_saved_per_year=(500000, ["saves us five lakh a year"]))
    problems = checks.canvas_assist(sent_for(a), bad, None)
    mended = core._repaired(spec, sent_for(a), bad, problems, None)
    assert mended is not None and mended[1] == ["value.estimate.inr_saved_per_year"]
    worse = copy.deepcopy(bad)
    worse["system"]["areas"] = ["AREA-not-offered"]
    assert (
        core._repaired(spec, sent_for(a), worse, checks.canvas_assist(sent_for(a), worse, None), None) is None
    )
    broken = copy.deepcopy(bad)
    del broken["evidence"]
    assert core._repaired(spec, sent_for(a), broken, ["evidence: fails 'required'"], None) is None
    assert checks.repair("judge", {}, {}) is None


def test_a_quote_holding_a_tag_survives_the_leak_check_and_restores_for_the_owner_only() -> None:
    a = answers()
    out = output(a, who__today_alternative=("Re-keyed by hand", ["[[KFIN_EMPLOYEE_1]] in MF ops re-keys"]))
    assert core.leak_hits(out) == []
    mapping = {"[[KFIN_EMPLOYEE_1]]": ("KFIN_EMPLOYEE", "Asha Verghese")}  # synthetic
    real = restore(out["evidence"], mapping, "real")
    assert real["who.today_alternative"] == ["Asha Verghese in MF ops re-keys"]
    neutral = restore(out["evidence"], mapping, "neutral")
    assert "Asha" not in json.dumps(neutral)


# ---- after an edit (B6) ------------------------------------------------------------------------------------------


def test_edited_details_drop_quotes_left_behind_and_cleared_figures_free_their_assumptions() -> None:
    a = answers(
        details="In the investor service team, 10 people each spend 2 hours a day re-keying address changes."
    )
    quotes = ["10 people each spend 2 hours a day"]
    card = output(a, value__estimate__hours_saved_per_month=(440, quotes))
    card["assumptions"] = listed("working_days_per_month")
    allowed = {x["id"]: float(x["value"]) for x in ALLOWED}
    evidence, kept = grounding.still_backed(card, allowed)
    assert evidence["value.estimate.hours_saved_per_month"] == quotes and kept == listed(
        "working_days_per_month"
    )
    card["details"] = "The investor service team re-keys address changes by hand."  # the person rewrote it
    evidence, kept = grounding.still_backed(card, allowed)
    assert "value.estimate.hours_saved_per_month" not in evidence and kept == []


# ---- the fake route, the examples and the golden set (as `make eval` will run them) ---------------------------


def _golden() -> list[dict[str, Any]]:
    return [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_examples_pass_the_schema_and_every_check() -> None:
    spec = load("canvas-assist")
    for ex in spec.examples:
        assert schema_ok(ex.output), ex.description
        assert checks.canvas_assist(ex.input, ex.output, None) == [], ex.description


def test_every_golden_case_ends_grounded_through_the_fake_route(monkeypatch: Any) -> None:
    """What the gateway does in fake mode: build, check, re-ask (the fake answers the same), then mend."""
    spec = load("canvas-assist")
    monkeypatch.setattr(ca_eval, "taxonomy_slice", lambda text: taxonomy_slice(text, SEED))
    monkeypatch.setattr(ca_eval, "assumptions", lambda: ALLOWED)
    planted = []
    for case in _golden():
        sent = ca_eval._inputs(case["input"])
        out = fakes.output_for(spec, sent)
        assert schema_ok(out), case["id"]
        problems = checks.canvas_assist(sent, out, None)
        if problems:
            again = fakes.output_for(spec, sent, retry=True)
            mended = core._repaired(spec, sent, again, checks.canvas_assist(sent, again, None), None)
            assert mended is not None, case["id"]
            out = mended[0]
            planted.append(case["id"])
        assert checks.canvas_assist(sent, out, None) == [], case["id"]
        assert grounding.ungrounded(sent, out) == {}, case["id"]
        expected = {k: v for k, v in case["expected_properties"].items() if k != "neutral_summary_no_names"}
        got = ca_eval._properties(expected, sent, out, None)
        fake_misses = {  # model properties the fake does not try to meet; only `make eval` on the real route does
            "system.areas_include", "system.lobs_include", "flag_mentions", "confidence.value.category_max",
            "value.play_suggested_in",
        }  # fmt: skip
        assert all(v for k, v in got.items() if k not in fake_misses), (case["id"], got)
    assert planted == ["CA-05", "CA-09"]  # the planted rupee figure and the unlisted salary are dropped


# ---- what the person and colleagues see --------------------------------------------------------------------------


def test_the_confirm_step_shows_each_suggestion_with_its_quotes_and_the_assumptions() -> None:
    a = answers()
    out = output(
        a, who__today_alternative=("Re-keyed by hand from email", ["re-keys about 40 switch requests"])
    )
    out["ecosystem"]["solved_elsewhere"] = "dont_know"
    out["provenance"]["ecosystem.solved_elsewhere"] = "suggested"
    shown = {s["path"]: s for s in view._suggested(out)}
    assert shown["who.today_alternative"]["quotes"] == ["re-keys about 40 switch requests"]
    assert "ecosystem.solved_elsewhere" not in shown
    assert view._left_blank(out) == ["who.frequency_or_reach", "value.estimate", "value.basis"]


def test_dropped_suggestions_leave_neutral_flags_for_the_review_desk() -> None:
    ca = {"flags_for_reviewer": ["Thin evidence for the size of the claim."]}
    assert with_drop_flags(ca, []) is ca
    flagged = with_drop_flags(ca, ["neutral_summary", "value.estimate.inr_saved_per_year"])
    assert flagged["flags_for_reviewer"] == [
        FLAG_SUMMARY_BLANK,
        FLAG_DROPPED,
        "Thin evidence for the size of the claim.",
    ]
    assert all(len(f.split()) <= 20 for f in (FLAG_SUMMARY_BLANK, FLAG_DROPPED))  # the schema's limit
    full = with_drop_flags({"flags_for_reviewer": [f"Flag {n}" for n in range(5)]}, ["neutral_summary"])
    assert len(full["flags_for_reviewer"]) == 5 and full["flags_for_reviewer"][0] == FLAG_SUMMARY_BLANK


def test_an_empty_summary_is_no_summary_for_the_readers_that_need_no_database() -> None:
    assert safe_summary(None, "") is None  # type: ignore[arg-type]  # returns before touching the database
    assert card_summary("idea", {"description": "the person's own line"}, {"neutral_summary": ""}) is None
