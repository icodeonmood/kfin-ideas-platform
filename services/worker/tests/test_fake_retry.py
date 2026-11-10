"""The fake route corrects itself when the gateway asks again (dev and tests only, BLD-158).

The gateway re-asks once with the problems it found. A real model rewrites the offending fields; the fake used to
answer the same twice, so a group whose members' words the name model reads as a person ("batch carton") failed
every time, and two such groups in a grouping run tripped `agent.cluster-summary`'s automatic switch-off.
"""

from __future__ import annotations

from typing import Any

from gateway import checks, fakes
from gateway.routes import FakeRoute
from gateway.spec import load

MEMBERS: list[dict[str, Any]] = [
    {
        "ref": f"M{n}",
        "kind": "problem",
        "one_line": f"batch carton printer voucher pile up at the {city} counter; ledger batch again tomorrow.",
        "details": "",
        "who": {"segments": [], "frequency_or_reach": None},
        "category": None,
        "play": None,
        "areas": [],
        "lobs": ["LOB-OPS"],
        "roles_affected": ["operations_executive"],
        "fix": None,
    }
    for n, city in ((1, "Hyderabad"), (2, "Chennai"))
]
INPUTS = {"members": MEMBERS, "existing": None, "mode": "cluster"}


def test_first_answer_copies_the_members_words() -> None:
    out = fakes.output_for(load("cluster-summary"), INPUTS)
    assert out["name"].startswith("batch carton printer")


def test_the_corrected_answer_has_a_neutral_name_and_description_and_passes_the_checks() -> None:
    spec = load("cluster-summary")
    out = fakes.output_for(spec, INPUTS, retry=True)
    assert out["name"] == "Shared problem"
    assert out["description"] == "A shared problem raised by 2 colleagues."
    assert [v["member"] for v in out["variations"]] == ["M2"]  # the rest is the same summary
    assert checks.cluster_summary(INPUTS, out, None) == []


def test_the_fake_route_gives_the_corrected_answer_only_on_the_gateway_s_second_ask() -> None:
    spec = load("cluster-summary")
    route = FakeRoute()
    first = route.call(spec, "system", [{"role": "user", "content": "x"}], INPUTS)
    again = route.call(
        spec,
        "system",
        [
            {"role": "user", "content": "x"},
            {"role": "assistant", "content": first.text},
            {
                "role": "user",
                "content": "That output did not pass validation:\n- description must not name …",
            },
        ],
        INPUTS,
    )
    assert '"name": "batch carton' in first.text
    assert '"name": "Shared problem"' in again.text


def test_agents_without_a_corrected_form_answer_the_same_on_retry() -> None:
    spec = load("gatekeeper")
    example = spec.examples[0]
    assert fakes.output_for(spec, example.input, retry=True) == example.output
