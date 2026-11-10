"""DEC-095, BLD-C020: canvas-assist suggests only what the person's own words say, and the gateway checks it.

No stack needed: the grounding check, the repair, the gateway's mend-after-the-re-ask step, the fake builder over
the golden set, and what the confirm step shows. The run through `run_agent` with a scripted model is in
`test_canvas_own_words_stack.py`.
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
from pii.restore import restore
from scan import view
from scan.inputs import taxonomy_slice

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "eval" / "golden" / "canvas_assist.jsonl"
SEED = ROOT / "seed" / "company-repo"
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
        "scope": "lob",
        "lobs": ["LOB-mf"],
        "areas": ["AREA-process"],
        "systems": [],
        "roles_affected": [],
    }
    out["provenance"] = {"details": "submitter", "value.category": "submitter"}
    out["evidence"] = {"neutral_summary": ["re-keys about 40 switch requests that arrive by email"]}
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


def schema_ok(out: dict[str, Any]) -> bool:
    return not list(Draft202012Validator(load("canvas-assist").schema).iter_errors(out))


# ---- the check -----------------------------------------------------------------------------------------------


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
    ],
)
def test_a_quote_that_is_not_word_for_word_fails(quote: str, code: str) -> None:
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


def test_quotes_come_only_from_the_persons_own_text() -> None:
    other = "Reviewer note: branch staff scan every mandate twice"
    a = answers()
    out = output(a, who__today_alternative=("Scanned twice", ["branch staff scan every mandate twice"]))
    sent = sent_for(a, past_corrections=[{"note": other}])
    assert grounding.ungrounded(sent, out) == {"who.today_alternative": "not_found"}
    # A clean file's digest and the person's references are their own material.
    a2 = answers(attachments=[{"id": "ATT-1", "name": "x.pdf", "state": "clean", "digest": other}])
    assert (
        grounding.ungrounded(sent_for(a2), output(a2, who__today_alternative=("Scanned twice", [other])))
        == {}
    )


def test_estimates_need_the_persons_figures_and_prose_may_not_add_numbers() -> None:
    a = answers()
    no_figure = output(a, value__estimate__hours_saved_per_month=(44, ["re-keys about 40 switch requests"]))
    assert grounding.ungrounded(sent_for(a), no_figure) == {}  # "40" is a figure of theirs
    vague = output(a, value__estimate__hours_saved_per_month=(44, ["often come back as NIGO"]))
    assert grounding.ungrounded(sent_for(a), vague) == {"value.estimate.hours_saved_per_month": "no_figure"}
    new_number = output(
        a, who__today_alternative=("Re-keyed by 3 people", ["re-keys about 40 switch requests"])
    )
    assert grounding.ungrounded(sent_for(a), new_number) == {"who.today_alternative": "new_number"}


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


def test_the_persons_answers_and_no_answer_values_need_no_quote() -> None:
    a = answers(
        who__today_alternative="We key it by hand", ecosystem__solved_elsewhere=None, value__category=None
    )
    out = output(a)
    out["ecosystem"]["solved_elsewhere"] = "dont_know"
    out["value"]["category"] = "not_sure"
    out["provenance"] |= {"ecosystem.solved_elsewhere": "suggested", "value.category": "suggested"}
    assert grounding.ungrounded(sent_for(a), out) == {}


def test_problems_name_paths_and_rules_never_the_quoted_text() -> None:
    a = answers()
    secret = "fifteen lakh saved on courier every year"
    out = output(a, value__estimate__inr_saved_per_year=(1500000, [secret]))
    problems = checks.canvas_assist(sent_for(a), out, None)
    assert problems and all(secret not in p and "lakh" not in p for p in problems)
    assert problems[0].startswith("value.estimate.inr_saved_per_year: ")


# ---- the repair --------------------------------------------------------------------------------------------


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


def test_a_dropped_one_line_becomes_the_persons_first_sentence_and_kind_becomes_problem() -> None:
    long = " ".join(f"word{n}" for n in range(30)) + ". Second sentence here."
    a = answers(details=long)
    out = output(a)
    out["one_line"] = "An invented line"
    out["evidence"]["one_line"] = ["nothing like this"]
    out["kind"] = "business_idea"
    out["evidence"]["kind"] = ["not in the text either"]
    out["evidence"]["neutral_summary"] = ["not in the text"]
    fixed, dropped = grounding.repair(sent_for(a), out)
    assert dropped == ["kind", "neutral_summary", "one_line"]
    first20 = " ".join(f"word{n}" for n in range(20))
    assert fixed["one_line"] == first20 + "…"
    assert fixed["evidence"]["one_line"] == [first20] and fixed["provenance"]["one_line"] == "suggested"
    assert fixed["kind"] == "problem" and fixed["evidence"]["kind"] == [first20]
    assert fixed["neutral_summary"] == "" and "neutral_summary" not in fixed["evidence"]
    assert schema_ok(fixed) and checks.canvas_assist(sent_for(a), fixed, None) == []


def test_first_sentence_stops_at_a_danda_and_short_sentences_are_kept_whole() -> None:
    assert grounding.first_sentence("Forms wapas aate hain। Dobara bhejna padta hai.") == (
        "Forms wapas aate hain।",
        "Forms wapas aate hain।",
    )


def test_the_gateway_mends_only_when_dropping_is_enough() -> None:
    spec = load("canvas-assist")
    a = answers()
    bad = output(a, value__estimate__inr_saved_per_year=(500000, ["saves us five lakh a year"]))
    problems = checks.canvas_assist(sent_for(a), bad, None)
    mended = core._repaired(spec, sent_for(a), bad, problems, None)
    assert mended is not None and mended[1] == ["value.estimate.inr_saved_per_year"]
    # Another problem stays: the call fails as before.
    worse = copy.deepcopy(bad)
    worse["system"]["areas"] = ["AREA-not-offered"]
    assert (
        core._repaired(spec, sent_for(a), worse, checks.canvas_assist(sent_for(a), worse, None), None) is None
    )
    # A schema failure is never mended.
    broken = copy.deepcopy(bad)
    del broken["evidence"]
    assert core._repaired(spec, sent_for(a), broken, ["evidence: fails 'required'"], None) is None
    # Other agents have no repair.
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
    planted = 0
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
            planted += 1
        assert checks.canvas_assist(sent, out, None) == [], case["id"]
        assert grounding.ungrounded(sent, out) == {}, case["id"]
        expected = {k: v for k, v in case["expected_properties"].items() if k != "neutral_summary_no_names"}
        got = ca_eval._properties(expected, sent, out, None)
        fake_misses = {  # model properties the fake does not try to meet; only `make eval` on the real route does
            "system.areas_include",
            "system.lobs_include",
            "flag_mentions",
            "confidence.value.category_max",
            "value.play_suggested_in",
        }
        assert all(v for k, v in got.items() if k not in fake_misses), (case["id"], got)
    assert planted == 1  # CA-05: the fake plants a rupee figure and the gateway drops it


# ---- what the person sees ------------------------------------------------------------------------------------


def test_the_confirm_step_shows_each_suggestion_with_its_quotes_and_hides_no_answer_values() -> None:
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
