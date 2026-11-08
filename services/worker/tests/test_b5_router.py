"""Retrieval plans (B5): P2 finds glossary systems exactly and by near spelling; P3 fuses graph, meaning and
keyword lists by reciprocal rank (k = 60), applies the trust boost, keeps 3 solution and 3 decision slots,
cuts to 20 (AT-B5-02) and keeps committee-only files out of the submitter's list (AT-B5-03); P6 returns the
nearest past corrections."""

from __future__ import annotations

from typing import Any

import pytest

from embeddings import embed
from router.corrections import corrections_for
from router.match import for_submitter, match
from router.taxonomy import glossary_ids, taxonomy_slice
from tests import repo_fixtures as rf

pytestmark = pytest.mark.stack
CARD = "SIP registrations slip because ops re-check every SIP form by hand for missing bank fields"


@pytest.fixture
def indexed(db: Any, company_repo: Any, test_database: str) -> Any:
    repo = company_repo
    for i in range(25):  # a crowd of similar open ideas
        rf.idea(repo, 100 + i, f"{CARD} in branch {i}", f"Manual SIP form checks slow registration ({i})")
    rf.idea(repo, 200, CARD + " at the review desk", "A related idea with the desk", visibility="committee")
    for i in range(3):
        rf.concept(
            repo,
            "solution",
            i + 1,
            f"Solved: {CARD}; an automated check now runs (v{i})",
            "Automated SIP checks",
        )
        rf.concept(
            repo,
            "decision",
            i + 1,
            f"Declined: {CARD}; outsourcing was turned down (p{i})",
            "Outsourcing was declined",
        )
    rf.idea(repo, 300, "Canteen seating is cramped during lunch on the fourth floor", "Canteen seating")
    rf.idea(repo, 301, "Unrelated wording entirely", "Linked by system only", systems=["GL-nigo"])
    rf.commit_and_index(repo, test_database)
    return db


def test_p2_finds_systems_exactly_and_by_near_spelling(indexed: Any) -> None:
    db = indexed
    assert "GL-sip" in glossary_ids(db, "Our SIP book grew")
    assert "GL-nigo" in glossary_ids(db, "NIGO forms go back by courier")
    near = glossary_ids(db, "the alternative investmnt fund desk")  # misspelt alias of GL-aif
    assert "GL-aif" in near
    assert "GL-sif" not in glossary_ids(
        db, "Our SIP book grew"
    )  # short acronyms never stand in for each other
    s = taxonomy_slice(db, "NIGO forms")
    assert s["systems"] and s["lobs"] and s["areas"] and s["roles"] and "cost_saving" in s["categories"]


def test_p3_fuses_reserves_and_cuts_to_twenty(indexed: Any) -> None:
    db = indexed
    found = match(db, CARD, ["GL-sip", "GL-nigo"], exclude_ids=("IDEA-2026-000100",))
    assert len(found) == 20
    kinds = [c.file_type for c in found]
    assert kinds.count("solution") == 3 and kinds.count("decision") == 3  # reserved despite the crowd
    assert all(c.kfin_id != "IDEA-2026-000100" for c in found)  # the card's own idea is excluded
    assert all(c.score > 0 for c in found)
    assert [c.score for c in found] == sorted((c.score for c in found), reverse=True)
    graph_only = next((c for c in found if c.kfin_id == "IDEA-2026-000301"), None)
    if graph_only:  # reached through GL-nigo only: one graph list entry at rank 1, unverified (0.9)
        assert graph_only.via == ["graph"] and abs(graph_only.score - 0.9 / 61) < 1e-9
    assert "IDEA-2026-000300" not in {c.kfin_id for c in found}


def test_p3_trust_boost(indexed: Any, company_repo: Any, test_database: str) -> None:
    db = indexed
    rf.idea(
        company_repo,
        400,
        "Pension contribution receipts reach subscribers late every quarter",
        "x",
        human=True,
    )
    rf.idea(company_repo, 401, "Pension contribution receipts reach subscribers late every quarter", "y")
    rf.commit_and_index(company_repo, test_database)
    found = {
        c.kfin_id: c
        for c in match(db, "Pension contribution receipts reach subscribers late every quarter", [])
    }
    human, unverified = found["IDEA-2026-000400"], found["IDEA-2026-000401"]
    assert human.trust == "human" and unverified.trust == "unverified"
    # Identical texts take adjacent ranks (raw RRF ratio at least 61/62), so the 1.15 / 0.9 boost decides.
    assert human.score / unverified.score >= (1.15 / 0.9) * (61 / 62) - 1e-9
    order = [
        c.kfin_id for c in match(db, "Pension contribution receipts reach subscribers late every quarter", [])
    ]
    assert order.index("IDEA-2026-000400") < order.index("IDEA-2026-000401")


def test_committee_only_files_never_reach_the_submitter(indexed: Any) -> None:
    db = indexed
    found = match(db, CARD + " at the review desk", ["GL-sip"])
    desk = [c for c in found if c.kfin_id == "IDEA-2026-000200"]
    assert desk and desk[0].visibility == "committee"  # the reviewer's list has it
    shown = dict((c.kfin_id, kind) for kind, c in for_submitter(found))
    assert shown["IDEA-2026-000200"] == "with_desk"  # the submitter sees only a placeholder


def test_p6_returns_the_nearest_corrections(db: Any) -> None:
    item = db.execute(
        "INSERT INTO review_items (item_type, ref_id) VALUES ('idea', 'IDEA-2026-000001') RETURNING id"
    ).fetchone()["id"]
    near, far = embed(["SIP form re-checks", "Canteen seating"])
    for vec, field in ((near, "system.areas"), (far, "value.category")):
        db.execute(
            "INSERT INTO corrections (review_item_id, field, proposed, final, card_embedding) "
            "VALUES (%s, %s, '[\"AREA-x\"]', '[\"AREA-process\"]', %s::vector)",
            (item, field, str(vec)),
        )
    got = corrections_for(db, embed(["SIP form re-checks by hand"])[0])
    assert [g["field"] for g in got] == ["system.areas", "value.category"]
    assert [g["field"] for g in corrections_for(db, near, field="value.category")] == ["value.category"]
