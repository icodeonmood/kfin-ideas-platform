"""Business ideas end to end, without the stack (lane C, BLD-C201 to BLD-C206): the draft-part agent suggests the
kind with a quote of the person's own words, checked by the gateway like every other part; the sorting takes it as
the suggestion while the person has not set or confirmed one, with New business by hand and the area as fallbacks;
a business idea gets its own next prompts; the golden set and its harness; the fake route's business sentence for
lane G. Synthetic text only."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from draft import parts
from draft.config import DEFAULT_DRAFTING
from draft.runs import result_of
from evalrunner import draft_part as harness
from gateway import checks, fakes
from gateway.fakes import BUSINESS_SENTENCE, NO_AREA_SENTENCE
from gateway.spec import load
from submit import sorting

ROOT = Path(__file__).resolve().parents[3]
AGENT = ROOT / "agents" / "draft-part"
GOLDEN = ROOT / "eval" / "golden" / "draft_part.jsonl"
PRIM = "A framework to launch PRIM for AMCs. Every AMC that wants PRIM asks us to set it up from scratch."
PROBLEM = "Investors who change their bank mandate at the branch wait a week before the new mandate shows."
QUOTE_LINE = "Suggested because you said “a framework to launch PRIM”."
PROBLEM_LINE = "Suggested because you described something that goes wrong today."
BUSINESS_LINE = "Suggested because you described something new KFintech could offer."


def example(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((AGENT / "examples" / name).read_text(encoding="utf-8"))
    return data


def title_out(**over: Any) -> dict[str, Any]:
    out = {
        "part": "title", "title": "A framework to launch PRIM for AMCs",
        "summary": "A ready framework that AMCs could use to launch PRIM.", "kind": "business_idea",
        "kind_evidence": "a framework to launch PRIM", "often": None, "who": [], "worth": [], "area": None,
        "reason": None, "evidence": ["A framework to launch PRIM for AMCs"],
    }  # fmt: skip
    out.update(over)
    return out


SENT = {"part": "title", "words": [{"n": 1, "text": PRIM}]}


# ---- BLD-C201: the agent's schema, examples and version ------------------------------------------------------------


def test_l_draft_parts_bld_c201_every_example_validates_and_passes_the_checks() -> None:
    validator = Draft202012Validator(json.loads((AGENT / "schema.json").read_text(encoding="utf-8")))
    names = sorted(p.name for p in (AGENT / "examples").glob("*.json"))
    assert "07-business-title.json" in names
    for name in names:
        ex = example(name)
        assert list(validator.iter_errors(ex["output"])) == [], name
        assert checks.draft_part(ex["input"], ex["output"], None) == [], name
        assert {"kind", "kind_evidence"} <= set(ex["output"]), name
    business = example("07-business-title.json")["output"]
    assert business["kind"] == "business_idea" and business["kind_evidence"]
    assert example("01-title.json")["output"]["kind"] == "problem"


def test_l_draft_parts_bld_c201_the_version_and_the_prompt_say_it() -> None:
    spec = load("draft-part", ROOT / "agents")
    assert spec.version == "0.2.1"
    assert "07-business-title.json" in spec.raw["examples_in_prompt"]
    prompt = (AGENT / "prompt.md").read_text(encoding="utf-8")
    assert "(v0.2.1)" in prompt and "`kind_evidence`" in prompt and "describe the new offer" in prompt
    changelog = (AGENT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "| 0.2.0 |" in changelog and "| 0.2.1 |" in changelog


def test_l_draft_parts_bld_c201_the_schema_allows_only_the_two_kinds_or_none() -> None:
    validator = Draft202012Validator(json.loads((AGENT / "schema.json").read_text(encoding="utf-8")))
    assert list(validator.iter_errors(title_out(kind=None, kind_evidence=None))) == []
    assert list(validator.iter_errors(title_out(kind="problem"))) == []
    assert list(validator.iter_errors(title_out(kind="fix")))
    missing = title_out()
    del missing["kind"]
    assert list(validator.iter_errors(missing))


# ---- BLD-C201: the gateway checks the kind's quote like every other part's ------------------------------------------


def test_l_draft_parts_bld_c201_a_kind_quotes_the_persons_own_words() -> None:
    assert checks.draft_part(SENT, title_out(), None) == []
    assert (
        checks.draft_part(SENT, title_out(kind="problem", kind_evidence="asks us to set it up"), None) == []
    )
    assert checks.draft_part(SENT, title_out(kind=None, kind_evidence=None), None) == []
    # No quote, a quote not in the words, a quote too thin, a quote with no kind: all refused, as "evidence".
    for bad in (
        title_out(kind_evidence=None),
        title_out(kind_evidence="a new product for AMCs"),
        title_out(kind_evidence="the"),
        title_out(kind=None, kind_evidence="a framework to launch PRIM"),
    ):
        problems = checks.draft_part(SENT, bad, None)
        assert problems and all("kind_evidence" in p for p in problems), bad


def test_l_draft_parts_bld_c201_the_kind_never_quotes_the_english_copy_dec_108() -> None:
    sent = {
        "part": "title",
        "words": [
            {
                "n": 1,
                "text": "Distributors ke liye ek naya product bana sakte hain, jo hum har mahine bech sakte hain.",
                "english": "We can make a new product for distributors, which we can sell every month.",
            }
        ],
    }
    out = title_out(
        title="A monthly product for distributors",
        summary="A new monthly product KFintech could make for distributors.",
        evidence=["Distributors ke liye ek naya product"],
        kind_evidence="a new product for distributors",
    )
    assert any("kind_evidence" in p for p in checks.draft_part(sent, out, None))
    assert checks.draft_part(sent, {**out, "kind_evidence": "ek naya product bana sakte hain"}, None) == []


def test_l_draft_parts_bld_c201_only_the_title_carries_a_kind() -> None:
    often = {**example("02-often.json")["output"], "kind": "problem", "kind_evidence": "about 40 calls a day"}
    problems = checks.draft_part(example("02-often.json")["input"], often, None)
    assert "kind belongs to another part; leave it null" in problems
    assert "kind_evidence belongs to another part; leave it null" in problems


def test_l_draft_parts_bld_c201_after_the_re_ask_only_an_unbacked_kind_is_dropped() -> None:
    bad_kind = title_out(kind_evidence="a new product for AMCs")
    fixed, dropped = checks.draft_part_repair(SENT, bad_kind)
    assert dropped == ["kind", "kind_evidence"]
    assert fixed["kind"] is None and fixed["kind_evidence"] is None
    assert fixed["title"] == bad_kind["title"] and fixed["summary"] == bad_kind["summary"]
    assert checks.draft_part(SENT, fixed, None) == []
    # A title that is itself unbacked still drops the whole part, the kind with it.
    both = title_out(kind_evidence="a new product for AMCs", evidence=["not in the words at all"])
    fixed, dropped = checks.draft_part_repair(SENT, both)
    assert fixed["title"] is None and fixed["kind"] is None
    assert set(dropped) == {"title", "summary", "kind", "kind_evidence"}


def test_l_draft_parts_bld_c201_the_harness_counts_an_unbacked_kind_as_ungrounded() -> None:
    problems = checks.draft_part(SENT, title_out(kind_evidence="a new product for AMCs"), None)
    assert any("evidence" in p for p in problems)  # evalrunner/draft_part.py: `ungrounded`


# ---- BLD-C201: the kind is kept with the title -------------------------------------------------------------------


def test_l_draft_parts_bld_c201_the_kind_is_kept_with_the_title_masked_as_the_words_are() -> None:
    said = [{"n": 1, "text": PRIM}]
    value, why, quote, _ = result_of("title", title_out(), said, None)
    assert value == {
        "title": "A framework to launch PRIM for AMCs",
        "summary": "A ready framework that AMCs could use to launch PRIM.",
        "pinned": [],
        "kind": "business_idea",
        "kind_quote": "a framework to launch PRIM",
    }
    assert why == "From your first sentence." and quote == "A framework to launch PRIM for AMCs"
    # An answer with no kind keeps the one before while its quote still stands in the words.
    again, *_ = result_of("title", title_out(kind=None, kind_evidence=None), said, value)
    assert again["kind"] == "business_idea" and again["kind_quote"] == "a framework to launch PRIM"
    # Once an edit takes the quote out of the words, the kind goes with it.
    edited = [{"n": 1, "text": "Every AMC that wants PRIM asks us to set it up from scratch."}]
    gone, *_ = result_of("title", title_out(kind=None, kind_evidence=None), edited, value)
    assert "kind" not in gone and "kind_quote" not in gone
    # A new kind replaces the old one; a pinned title and summary keep the person's words.
    pinned = {**value, "title": "My title", "pinned": ["title"]}
    now, *_ = result_of(
        "title", title_out(kind="problem", kind_evidence="asks us to set it up"), said, pinned
    )
    assert now["title"] == "My title" and now["kind"] == "problem"


# ---- BLD-C201, BLD-C204, BLD-C196: which kind the sorting suggests -------------------------------------------------


AGENT_BUSINESS = {
    "title": "t",
    "summary": "s",
    "kind": "business_idea",
    "kind_quote": "a framework to launch PRIM",
}
AGENT_PROBLEM = {"title": "t", "summary": "s", "kind": "problem", "kind_quote": "asks us to set it up"}


@pytest.mark.parametrize(
    ("title", "area", "by_hand", "kind", "why"),
    [
        # The agent's kind is the suggestion: a business idea reads its quote, a problem the drawn line.
        (AGENT_BUSINESS, "Operations", False, "business_idea", QUOTE_LINE),
        (AGENT_PROBLEM, "Operations", False, "problem", PROBLEM_LINE),
        # The agent's kind wins over the area's rule (BLD-C196 is the fallback).
        (AGENT_PROBLEM, "New business", False, "problem", PROBLEM_LINE),
        # No kind from the agent: the area's rule.
        (None, "New business", False, "business_idea", BUSINESS_LINE),
        ({"title": "t", "summary": "s"}, "Investor service", False, "problem", PROBLEM_LINE),
        (None, None, False, "problem", PROBLEM_LINE),
        # New business picked by hand suggests a business idea, whatever the agent said (BLD-C204).
        (AGENT_PROBLEM, "New business", True, "business_idea", BUSINESS_LINE),
        (None, "new  business", True, "business_idea", BUSINESS_LINE),
        # Another area picked by hand undoes only what the area suggested: the agent's kind stands.
        (AGENT_BUSINESS, "Operations", True, "business_idea", QUOTE_LINE),
        (AGENT_PROBLEM, "Sales", True, "problem", PROBLEM_LINE),
        # A kind without its quote is not a suggestion.
        ({"kind": "business_idea", "kind_quote": ""}, "Operations", False, "problem", PROBLEM_LINE),
    ],
)
def test_l_sort_bld_c201_c204_the_kind_suggested(
    title: Any, area: str | None, by_hand: bool, kind: str, why: str
) -> None:
    got_kind, got_why = parts.kind_suggestion(title, area, area_by_hand=by_hand)
    assert got_kind == kind
    assert sorting.why_line(sorting.Choice(got_kind, "suggested", got_why), "kind") == why


def test_l_sort_bld_c201_c204_the_kind_shown_now() -> None:
    hand = {"area": {"source": "changed"}}
    confirmed = {"area": {"source": "confirmed"}}
    # The person's own kind is never replaced.
    assert parts.kind_now("problem", hand, "New business", AGENT_BUSINESS, "New business") == "problem"
    assert parts.kind_now("fix", {}, None, AGENT_BUSINESS, None) == "problem"
    assert parts.kind_now("business_idea", {}, "Operations", AGENT_PROBLEM, "Operations") == "business_idea"
    # Otherwise the suggestion, with the person's area in place of the draft's once they confirmed or picked it.
    assert parts.kind_now(None, {}, None, AGENT_BUSINESS, "Operations") == "business_idea"
    assert parts.kind_now(None, hand, "New business", AGENT_PROBLEM, "Operations") == "business_idea"
    assert parts.kind_now(None, hand, "Operations", None, "New business") == "problem"
    assert parts.kind_now(None, confirmed, "New business", None, "Operations") == "business_idea"
    assert parts.kind_now(None, None, None, None, None) == "problem"


def test_l_sort_bld_c196_the_area_rule_stays_where_it_was() -> None:
    assert sorting.kind_for_area("New business") == "business_idea"
    assert sorting.kind_for_area("Operations") == "problem"
    assert sorting.KIND_WHY is parts.KIND_WHY and sorting.NEW_BUSINESS == "New business"
    assert sorting.kind_on_check_it("problem_with_solution") == "problem"


# ---- BLD-C203: a business idea's next prompts ---------------------------------------------------------------------


def test_l_draft_parts_8_bld_c203_a_business_idea_gets_its_own_next_prompts() -> None:
    assert parts.suggestions({}, kind="business_idea") == ["Say who it is for", "Say how many would use it"]
    who_known = {"who": ["Distributors"]}
    assert parts.suggestions(who_known, kind="business_idea") == [
        "Say how many would use it",
        "Add who offers it today",
    ]
    full = {"who": ["Distributors"], "often": "About 300 distributors", "title": {"title": "A ready feed"}}
    assert parts.suggestions(full, kind="business_idea") == ["Add who offers it today", "Change the title"]
    # A problem keeps today's prompts, with or without the kind named.
    assert (
        parts.suggestions({}, kind="problem")
        == parts.suggestions({})
        == [
            "Say how often it happens",
            "Say who feels it most",
        ]
    )
    assert set(parts.BUSINESS_PROMPTS.values()).isdisjoint(parts.suggestions({}))


# ---- BLD-C205: the golden set and its harness ---------------------------------------------------------------------


def _golden() -> list[dict[str, Any]]:
    return [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_l_draft_bld_c205_the_golden_set_holds_the_business_cases() -> None:
    cases = {c["id"]: c for c in _golden()}
    assert len(cases) == 20
    words = {cid: " ".join(w["text"] for w in c["input"]["words"]) for cid, c in cases.items() if
             isinstance(c["input"], dict)}  # fmt: skip
    assert "a framework to launch PRIM".casefold() in words["DP-13"].casefold()
    assert "a new product on loan against mutual funds".casefold() in words["DP-15"].casefold()
    for cid in ("DP-13", "DP-15", "DP-17", "DP-18", "DP-19"):
        exp = cases[cid]["expected"]
        assert exp["kind"] == "business_idea" and exp["kind_evidence_from_text"] is True, cid
        assert exp["summary_offer"]["what"] and exp["summary_offer"]["for"], cid
    assert cases["DP-14"]["expected"] == cases["DP-16"]["expected"] == {"area": "New business"}
    assert cases["DP-20"]["expected"]["kind"] == "problem"
    assert "english" in cases["DP-19"]["input"]["words"][0]


@pytest.mark.parametrize("case", _golden(), ids=lambda c: c["id"])
def test_l_draft_bld_c205_the_fake_passes_its_own_checks_on_every_golden_case(case: dict[str, Any]) -> None:
    """The harness gates (`checks_hold`) without the stack: whatever the fake answers passes the gateway's checks."""
    sent = harness._inputs(case["input"])
    if "{{" in json.dumps(sent):
        pytest.skip("filled by the eval context's generators")
    if case["id"] == "DP-08":
        pytest.skip("planted: the fake quotes a figure nobody gave, so the gateway drops it (DEC-095)")
    out = fakes.draft_part(load("draft-part", ROOT / "agents"), sent)
    assert checks.draft_part(sent, out, None) == []


def test_l_draft_bld_c205_the_kind_is_a_model_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """0.2.1 (the cbiz review): `kind_accuracy` is gated, not only reported. A model that reads the business ideas as
    problems fails the golden set, as eval-live will show it on a real route; one wrong kind of six still passes."""
    cases = [
        {"id": f"K-{i}", "input": {"words": []}, "expected": {"kind": "business_idea"}} for i in range(5)
    ]
    cases.append({"id": "K-5", "input": {"words": []}, "expected": {"kind": "problem"}})
    said: list[str] = []
    monkeypatch.setattr(harness, "read_jsonl", lambda name: cases)
    monkeypatch.setattr(harness, "check", lambda sent, out, prior: [])

    def answer(agent: str, sent: dict[str, Any], scope: str, **kw: Any) -> SimpleNamespace:
        return SimpleNamespace(data={"kind": said.pop(0)}, sent=sent, outcome="ok", dropped=[])

    monkeypatch.setattr(harness, "run_agent", answer)
    ctx: Any = SimpleNamespace(fill=lambda sent: sent, scope=lambda: "eval-scope", conn=None)
    assert load("draft-part", ROOT / "agents").raw["pass_gates"]["kind_accuracy_min"] == 0.8

    said[:] = ["problem"] * 6  # every business idea read as a problem: 1 of 6
    report = harness.run(ctx)
    assert report["metrics"]["kind_accuracy"] < 0.2 and report["model_gates"]["kind_accuracy"] is False
    said[:] = ["business_idea"] * 3 + ["problem"] * 3  # two business ideas read as problems: 4 of 6
    assert harness.run(ctx)["model_gates"]["kind_accuracy"] is False
    said[:] = ["business_idea"] * 6  # one wrong (the problem): 5 of 6
    assert harness.run(ctx)["model_gates"]["kind_accuracy"] is True

    # Nothing answered (no key on the server): n/a and FAIL, never 100% over no answers (lane A's review, 27 Nov).
    def failed(*_a: Any, **_k: Any) -> Any:
        raise harness.AgentFailed("agent_failed")

    monkeypatch.setattr(harness, "run_agent", failed)
    none = harness.run(ctx)
    assert none["metrics"]["expectations"] is None and none["metrics"]["kind_accuracy"] is None
    assert none["model_gates"]["expectations"] is False and none["model_gates"]["kind_accuracy"] is False


def test_l_draft_bld_c205_the_harness_checks_the_kind_its_quote_and_the_offer() -> None:
    sent = {"words": [{"n": 1, "text": PRIM, "english": "A set-up kit for PRIM launches."}]}
    out = title_out()
    met = harness._met
    assert met({"kind": "business_idea", "kind_evidence_from_text": True}, out, sent) == (2, 2)
    assert met({"kind": "problem"}, out, sent) == (0, 1)
    assert met({"kind_evidence_from_text": True}, {**out, "kind_evidence": "not said"}, sent) == (0, 1)
    assert met({"kind_evidence_from_text": True}, {**out, "kind": None}, sent) == (0, 1)
    # From the English copy, never the person's words (DEC-108).
    english = {**out, "kind_evidence": "set-up kit for PRIM"}
    assert met({"kind_evidence_from_text": True}, english, sent) == (0, 1)
    assert met({"quotes_from_text_only": True}, english, sent) == (0, 1)
    assert met({"quotes_from_text_only": True}, {**out, "kind_evidence": "launch PRIM for AMCs"}, sent) == (
        1,
        1,
    )
    offer = {"what": ["PRIM"], "for": ["AMC"]}
    assert met({"summary_offer": offer}, out, sent) == (1, 1)
    assert met({"summary_offer": offer}, {**out, "summary": "Launching PRIM is slow."}, sent) == (0, 1)
    assert met({"summary_offer": offer}, {**out, "summary": None}, sent) == (0, 1)


# ---- BLD-C206: the fake route's business sentence, for lane G's journey ----------------------------------------------


def _fake(part: str, texts: list[str], options: str | None = None) -> dict[str, Any]:
    inputs: dict[str, Any] = {"part": part, "words": [{"n": i + 1, "text": t} for i, t in enumerate(texts)]}
    if options:
        inputs["options"] = {
            "choices": [{"label": o["label"], "cues": o["cues"]} for o in DEFAULT_DRAFTING[options]]
        }
    out = fakes.draft_part(None, inputs)  # type: ignore[arg-type]
    assert checks.draft_part(inputs, out, None) == []
    return out


def test_v_acc_s04_bld_c206_the_fake_sentence_is_a_new_business_idea_under_new_business() -> None:
    assert len(BUSINESS_SENTENCE) >= 30 and "[[" not in BUSINESS_SENTENCE
    title = _fake("title", [BUSINESS_SENTENCE])
    assert title["kind"] == "business_idea" and title["kind_evidence"] == "KFintech could offer small AMCs"
    assert title["title"] == "KFintech could offer small AMCs a new product that checks factsheets"
    assert title["summary"] == BUSINESS_SENTENCE
    area = _fake("area", [BUSINESS_SENTENCE], "area")
    assert area["area"] == "New business" and area["reason"] == "it's about a new product"
    # Whatever else is said, in any case and spacing.
    loud = _fake("area", ["Investors call the branch about the SMS.", BUSINESS_SENTENCE.upper()], "area")
    assert loud["area"] == "New business"
    assert _fake("who", [BUSINESS_SENTENCE], "affects")["who"] == ["AMC clients"]
    stored = {"kind": title["kind"], "kind_quote": title["kind_evidence"]}
    kind, why = parts.kind_suggestion(stored, "New business", area_by_hand=False)
    assert kind == "business_idea"
    line = sorting.why_line(sorting.Choice(kind, "suggested", why), "kind")
    assert line == "Suggested because you said “KFintech could offer small AMCs”."


@pytest.mark.parametrize(
    "words",
    [
        PROBLEM,
        NO_AREA_SENTENCE,
        # lane G's journey words (J-SHARE, J-RESUME, J-RECOVER): each stays a problem to fix.
        "Investors who change their bank mandate at the branch wait a week before the new mandate shows. One "
        "investor with PAN ••••8Z called four times last week. It happens about 25 times a week at our branch.",
        "Walk-in investors who update their address at the branch fill the same form twice, once for KYC and once "
        "for the folio. It happens about ten times a day at our branch.",
        "Courier returns of redemption forms are logged in a paper register at the branch. It happens about ten "
        "times a week.",
        "The loan against mutual funds page shows last month's lien limit, so investors call the branch.",
    ],
)
def test_v_acc_s04_bld_c206_other_words_stay_a_problem_on_the_fake(words: str) -> None:
    title = _fake("title", [words])
    assert title["kind"] == "problem" and title["kind_evidence"]
    assert _fake("area", [words], "area")["area"] != "New business"


def test_v_acc_s04_bld_c206_the_rule_lives_only_on_the_fake_route() -> None:
    import inspect

    from gateway import routes

    assert "BUSINESS_SENTENCE" not in inspect.getsource(routes)
    assert inspect.getsource(fakes).count("BUSINESS_SENTENCE =") == 1
