"""L-SIMILAR on the 1% Club seed (BLD-C091 to BLD-C093): chunks from database rows, matching with the judge or by
code, the stored links, and SimilarMatch[] as each person may see it. The seed is removed after each test."""

from __future__ import annotations

import json
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

import gateway
from bootstrap import club_seed
from core import killswitch
from similar import index, match_shared, similar_for
from similar import matching as m
from similar.preview import Viewer
from similar.views import matches_for


def _user(conn: Any, first: str) -> str:
    row = conn.execute("SELECT id FROM users WHERE name LIKE %s", (first + " %",)).fetchone()
    return str(row["id"])


def _switch(conn: Any, name: str, state: str) -> None:
    conn.execute("UPDATE kill_switches SET state = %s WHERE name = %s", (state, name))
    killswitch.clear_cache()


@pytest.fixture
def seeded(db: Any) -> Iterator[dict[str, Any]]:
    killswitch.clear_cache()
    made = club_seed.load(db)
    try:
        yield made
    finally:
        for name in ("ai.all", "matching.show"):
            _switch(db, name, "on")
        club_seed.remove(db)


def _links(conn: Any, idea_uuid: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT i.idea_id, l.strength, l.reason, l.rank, l.found_while, l.outcome FROM similar_links l "
        "JOIN ideas i ON i.id = l.other_idea_uuid WHERE l.idea_uuid = %s",
        (idea_uuid,),
    ).fetchall()
    return {str(r["idea_id"]): dict(r) for r in rows}


def test_bld_c091_chunks_come_from_shared_rows_only(db: Any, seeded: dict[str, Any]) -> None:
    index.sync(db)
    rows = {
        str(r["idea_uuid"]): r
        for r in db.execute(
            "SELECT idea_uuid, text, repo_path FROM chunks WHERE idea_uuid IS NOT NULL"
        ).fetchall()
    }
    for key, made in seeded.items():
        shared = made.spec.shared_days is not None and made.spec.status not in ("draft", "withdrawn")
        assert (made.uuid in rows) == shared, key
    t5 = rows[seeded["T5"].uuid]
    assert t5["repo_path"] is None
    assert t5["text"].startswith("Redemption status is not visible to the branch")
    for made in seeded.values():  # the masked title and short summary, never the sharer's own words
        if made.uuid in rows:
            assert rows[made.uuid]["text"] == index.chunk_text(
                {"title": made.spec.title, "summary": made.spec.summary}
            )
    assert index.sync(db)["embedded"] == 0  # nothing changed, nothing re-embedded
    db.execute("UPDATE ideas SET summary = summary || ' Every day.' WHERE id = %s", (seeded["T5"].uuid,))
    assert index.sync(db)["embedded"] == 1
    db.execute("UPDATE ideas SET status = 'withdrawn' WHERE id = %s", (seeded["T5"].uuid,))
    index.sync(db)
    assert db.execute("SELECT 1 FROM chunks WHERE idea_uuid = %s", (seeded["T5"].uuid,)).fetchone() is None


def test_bld_c092_with_the_assistant_off_matching_works_by_code(db: Any, seeded: dict[str, Any]) -> None:
    _switch(db, "ai.all", "off")
    t2 = seeded["T2"]  # Tanvi's draft: the SIP failure SMS gives no reason
    run = m.match_idea(db, t2.uuid)
    assert run.state == "done" and run.labelled_by == "code"
    links = _links(db, t2.uuid)
    assert seeded["R1"].ref in links  # Rekha's: no reason when a SIP debit fails
    tanvi = {made.ref for made in seeded.values() if made.spec.owner == "tanvi"}
    assert not set(links) & tanvi  # her own ideas never match
    shared = {made.ref for made in seeded.values() if made.ref}
    assert set(links) <= shared  # never a draft
    assert seeded["T10"].ref not in links  # never a withdrawn idea
    found = [x for x in links.values() if x["outcome"] is None]
    assert len(found) <= m.MAX_MATCHES
    for link in links.values():
        assert link["reason"].startswith("Close match: " if link["strength"] == "close" else "Related: ")
    ranks = sorted(found, key=lambda x: x["rank"])
    assert [x["strength"] for x in ranks] == sorted(
        (x["strength"] for x in ranks), key=lambda s: s != "close"
    )
    row = db.execute(
        "SELECT state, found, labelled_by, word_hashes FROM similar_runs WHERE idea_uuid = %s", (t2.uuid,)
    ).fetchone()
    assert row["state"] == "done" and row["labelled_by"] == "code" and row["found"] == run.found
    assert "sms" not in json.dumps(row["word_hashes"]).lower()


def test_bld_c092_the_judge_labels_through_the_gateway(db: Any, seeded: dict[str, Any]) -> None:
    t2 = seeded["T2"]
    run = m.match_idea(db, t2.uuid)
    assert run.state == "done" and run.labelled_by == "judge"
    calls = db.execute("SELECT count(*) AS n FROM llm_calls WHERE agent = 'judge'").fetchone()
    assert calls["n"] >= 1


def test_bld_c092_judge_labels_become_close_related_or_nothing(
    db: Any, seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    r1, t2 = seeded["R1"], seeded["T2"]

    def fake_run_agent(name: str, inputs: dict[str, Any], ref_id: str, **_: Any) -> Any:
        assert name == "judge" and ref_id == f"DRAFT-{t2.uuid}"
        results = []
        for i, c in enumerate(inputs["candidates"]):
            if c["cid"] == r1.ref:
                results.append(
                    {
                        "cid": c["cid"],
                        "label": "same",
                        "reason": "The same failed SIP debit.",
                        "confidence": 0.9,
                    }
                )
            else:
                label = "related" if i % 2 else "different"
                reason = "[[KFIN_EMPLOYEE_1]] raised it too" if label == "related" else "Different."
                results.append({"cid": c["cid"], "label": label, "reason": reason, "confidence": 0.5})
        return SimpleNamespace(data={"results": results, "best_same": r1.ref})

    monkeypatch.setattr(gateway, "run_agent", fake_run_agent)
    run = m.match_idea(db, t2.uuid, force=True)
    assert run.labelled_by == "judge"
    by_uuid = {f.uuid: f for f in run.matches}
    assert by_uuid[r1.uuid].strength == "close"
    assert by_uuid[r1.uuid].reason == "Close match: the same failed SIP debit"
    assert run.matches[0].uuid == r1.uuid  # close first
    for f in run.matches[1:]:
        assert f.strength == "related"
        assert "[[" not in f.reason and f.reason.startswith("Related: ")  # a tagged reason falls back to code


def test_bld_c092_a_failure_never_blocks_and_is_recorded(
    db: Any, seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    t4 = seeded["T4"]  # checking: being sent now

    def broken(*_: Any, **__: Any) -> Any:
        raise RuntimeError("index down")

    monkeypatch.setattr(m, "retrieve", broken)
    with db.transaction():  # as c/sort-submit calls it, inside its own transaction
        assert match_shared(db, t4.uuid, found_while="checking") == -1
        db.execute("SELECT 1")  # the caller's transaction is still usable
    row = db.execute("SELECT state, error_code FROM similar_runs WHERE idea_uuid = %s", (t4.uuid,)).fetchone()
    assert row["state"] == "failed" and row["error_code"] == "RuntimeError"
    assert (
        similar_for(db, seeded["T2"].uuid, "SIP failure SMS gives no reason", "") is None
    )  # "Couldn't check"


def test_bld_c093_reruns_only_on_a_material_change(db: Any, seeded: dict[str, Any]) -> None:
    _switch(db, "ai.all", "off")
    t2 = seeded["T2"]
    assert m.match_idea(db, t2.uuid).state == "done"
    assert m.match_idea(db, t2.uuid).state == "unchanged"
    assert m.match_idea(db, t2.uuid, title="SIP failure SMS gives no reason at all").state == "unchanged"
    changed = m.match_idea(
        db, t2.uuid, title="Rejection codes on letters", summary="Investors cannot read R07."
    )
    assert changed.state == "done"
    db.execute(
        "UPDATE ideas SET status = 'checking', shared_at = now(), idea_id = next_idea_ref() WHERE id = %s",
        (t2.uuid,),
    )
    n = match_shared(db, t2.uuid, found_while="checking")  # sending always runs
    assert n >= 0
    assert match_shared(db, t2.uuid, found_while="later") == n  # an edit with no material change
    run = db.execute("SELECT found_while FROM similar_runs WHERE idea_uuid = %s", (t2.uuid,)).fetchone()
    assert run["found_while"] == "checking"


def test_bld_c093_similar_for_gives_the_draft_part_its_matches(db: Any, seeded: dict[str, Any]) -> None:
    _switch(db, "ai.all", "off")
    t2 = seeded["T2"]
    out = similar_for(
        db,
        t2.uuid,
        "SIP failure SMS gives no reason",
        "When a SIP debit fails, the SMS says only that it failed.",
    )
    assert out is not None and 1 <= len(out) <= 8
    first = out[0]
    assert set(first) >= {"idea", "strength", "reason"}
    assert first["idea"]["id"].startswith("IDEA-") and "compare" not in first["idea"]
    assert any(x["idea"]["id"] == seeded["R1"].ref for x in out)
    assert seeded["R1"].spec.words[0][:60] not in json.dumps(
        out, ensure_ascii=False
    )  # never Rekha's own words


def test_bld_c092_who_sees_the_matches(db: Any, seeded: dict[str, Any]) -> None:
    p1, t5, t2 = seeded["P1"], seeded["T5"], seeded["T2"]  # the seed: T5 found P1 while Tanvi wrote
    pallavi, harish, tanvi = (Viewer.of(db, _user(db, n)) for n in ("Pallavi", "Harish", "Tanvi"))
    # Rule 6: the newer idea shows on the older idea's page, for its sharer and the reviewer.
    mine = matches_for(db, p1.ref, pallavi)
    assert mine is not None and [x["idea"]["id"] for x in mine] == [t5.ref]
    assert "compare" not in mine[0]["idea"]
    desk = matches_for(db, p1.ref, harish)
    assert desk is not None and desk[0]["idea"]["compare_with"]["id"] == p1.ref
    # Someone else's idea, or a draft for the desk: not found.
    assert matches_for(db, p1.ref, tanvi) is None
    assert matches_for(db, t2.uuid, harish) is None
    assert matches_for(db, t2.uuid, tanvi) is not None
    # matching.show off: the sharer sees none, the desk keeps the list.
    _switch(db, "matching.show", "off")
    assert matches_for(db, p1.ref, pallavi) == []
    assert matches_for(db, p1.ref, harish)


def test_bld_c092_my_request_and_merged_ideas(db: Any, seeded: dict[str, Any]) -> None:
    e1, t5, r2, t11 = seeded["E1"], seeded["T5"], seeded["R2"], seeded["T11"]
    esha = Viewer.of(db, _user(db, "Esha"))
    db.execute(
        "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason) VALUES (%s, %s, 'related', %s), "
        "(%s, %s, 'close', %s)",
        (e1.uuid, t5.uuid, "Related: also about plain words", e1.uuid, t11.uuid, "Close match: same message"),
    )
    out = {x["idea"]["id"]: x for x in matches_for(db, e1.ref, esha) or []}
    request = out[t5.ref]["my_request"]  # Esha's team-up request to Tanvi, waiting
    assert request["state"] == "sent" and request["idea_id"] == t5.ref
    assert request["note"].startswith("My factsheet idea")
    assert [b["id"] for b in request["brought"]] == [e1.ref]
    assert t11.ref not in out and out[r2.ref]["strength"] == "close"  # merged into Rekha's R2
