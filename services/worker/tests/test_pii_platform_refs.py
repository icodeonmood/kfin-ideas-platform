"""The short refs the gateway hands agents are never read as people (BLD-160).

The NER model read "M13", "M17", "M86", "M88", "M96", "I15", "I28", "I47", "I50", "I63" and "I84" as PERSON. Tagged,
they reached the model as [[PERSON_1]] in place of a member ref, the output's refs failed the schema, and every group
of 13 or more ideas failed cluster-summary (role-themes, with up to 40 ideas, the same). Names are still found.
"""

from __future__ import annotations

import pytest

from pii.detect import PLATFORM_ID, Directory, detect

REFS = (
    [f"M{n}" for n in range(1, 100)]
    + [f"I{n}" for n in range(1, 100)]
    + [f"Member {n}" for n in range(1, 100)]
    + [f"Contributor {n}" for n in range(1, 100)]  # the committee's blind view (committee/rounds.py)
)


def test_no_agent_ref_is_read_as_a_person() -> None:
    d = Directory()
    people = [ref for ref in REFS if any(f.type == "PERSON" for f in detect(ref, d))]
    assert people == []


@pytest.mark.parametrize("value", ["M13", "I15", "Member 7", "Contributor 4", "CL-0010", "IDEA-2026-000123"])
def test_only_exact_platform_refs_are_exempt(value: str) -> None:
    assert PLATFORM_ID.fullmatch(value)


@pytest.mark.parametrize("value", ["M", "M123", "Mohan", "I", "Iqbal", "Members 3", "XM13"])
def test_near_misses_are_not_exempt(value: str) -> None:
    assert not PLATFORM_ID.fullmatch(value)


def test_a_name_beside_a_ref_is_still_found() -> None:
    found = detect("M13 says Rohan Kulkarni signs every courier slip twice.", Directory())
    assert [f.value for f in found if f.type == "PERSON"] == ["Rohan Kulkarni"]
