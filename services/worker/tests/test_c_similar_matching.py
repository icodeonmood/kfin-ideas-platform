"""L-SIMILAR on the 1% Club seed (BLD-C091 to BLD-C099): chunks from database rows, matching with the judge or by
code, the stored links, and SimilarMatch[] as each person may see it. The seed is removed after each test, with the
gateway rows its runs wrote (`llm_calls` and the vault by the seed ideas' scopes, the judge's new cache entries);
`audit_log` refuses deletes and these tests write none."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

import gateway
from bootstrap import club_seed
from core import killswitch
from onepc.context import seal_text
from similar import index, match_shared, similar_for, views
from similar import matching as m
from similar.preview import Viewer, checked_sentence
from similar.views import keep_separate, matches_for


def _user(conn: Any, first: str) -> str:
    row = conn.execute("SELECT id FROM users WHERE name LIKE %s", (first + " %",)).fetchone()
    return str(row["id"])


def _switch(conn: Any, name: str, state: str) -> None:
    conn.execute("UPDATE kill_switches SET state = %s WHERE name = %s", (state, name))
    killswitch.clear_cache()


def _scopes(conn: Any, made: dict[str, Any]) -> list[str]:
    """The gateway scopes of the seed's ideas as they are now: a draft's, and its reference once shared."""
    rows = conn.execute(
        "SELECT id, idea_id FROM ideas WHERE id = ANY(%s::uuid[])", ([x.uuid for x in made.values()],)
    ).fetchall()
    return [str(r["idea_id"]) for r in rows if r["idea_id"]] + [f"DRAFT-{r['id']}" for r in rows]


@pytest.fixture
def seeded(db: Any) -> Iterator[dict[str, Any]]:
    killswitch.clear_cache()
    cached = [
        bytes(r["key"]) for r in db.execute("SELECT key FROM llm_cache WHERE agent = 'judge'").fetchall()
    ]
    made = club_seed.load(db)
    try:
        yield made
    finally:
        for name in ("ai.all", "matching.show"):
            _switch(db, name, "on")
        scopes = _scopes(db, made)  # crunch rule 14: what the runs wrote goes with the seed
        db.execute("DELETE FROM llm_calls WHERE ref_id = ANY(%s)", (scopes,))
        db.execute("DELETE FROM pseudonym_vault WHERE scope_id = ANY(%s)", (scopes,))
        db.execute("DELETE FROM vault_counters WHERE scope_id = ANY(%s)", (scopes,))
        db.execute("DELETE FROM llm_cache WHERE agent = 'judge' AND NOT (key = ANY(%s::bytea[]))", (cached,))
        club_seed.remove(db)


def _links(conn: Any, idea_uuid: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT i.idea_id, l.strength, l.reason, l.rank, l.found_while, l.outcome FROM similar_links l "
        "JOIN ideas i ON i.id = l.other_idea_uuid WHERE l.idea_uuid = %s",
        (idea_uuid,),
    ).fetchall()
    return {str(r["idea_id"]): dict(r) for r in rows}


def test_bld_c091_chunks_come_from_shared_rows_only(db: Any, seeded: dict[str, Any]) -> None:
    """L-SIMILAR.rules/1: one chunk per shared idea that is not withdrawn, from its masked row."""
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
    """L-SIMILAR.rules/1-3: never own ideas, drafts or withdrawn ones; close or related with a reason; at most
    8, close first."""
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
    """L-SIMILAR.rules/2: the judge labels by meaning, through run_agent: one call per run, on the draft's scope."""
    t2 = seeded["T2"]
    count = "SELECT count(*) AS n FROM llm_calls WHERE agent = 'judge' AND ref_id = %s"
    before = db.execute(count, (f"DRAFT-{t2.uuid}",)).fetchone()["n"]
    run = m.match_idea(db, t2.uuid)
    assert run.state == "done" and run.labelled_by == "judge"
    assert db.execute(count, (f"DRAFT-{t2.uuid}",)).fetchone()["n"] == before + 1


def test_bld_c092_judge_labels_become_close_related_or_nothing(
    db: Any, seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """L-SIMILAR.rules/2-3: same is close, related is related, different is dropped; close first; a reason
    that fails the checks falls back to code."""
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
    """L-SIMILAR.rules/9 (L-SIMILAR.failure): a failure never blocks sharing, is recorded, and the draft part
    says it couldn't check."""
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
    """L-SIMILAR.rules/4-5: re-runs on a material change only; sending always runs."""
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
    """L-SIMILAR.rules/4: the draft part's matches, stored, masked, never the other sharer's own words."""
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
    """L-SIMILAR.rules/5-6: the sharer and the reviewer see the matches; a newer idea shows on the older
    idea's page."""
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
    """L-SIMILAR.rules/1, /7: a merged idea resolves to the one it joined; the viewer's own team-up request
    rides on the match."""
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


def test_bld_c095_keep_mine_separate_is_recorded_for_the_reviewer(db: Any, seeded: dict[str, Any]) -> None:
    """L-SIMILAR.rules/7-8: Keep mine separate is recorded for the reviewer; a merge request stays; Show them
    again undoes it."""
    t2, t1 = seeded["T2"], seeded["T1"]  # T2 asked Rekha to merge (kept as it is); T1 found R1 while writing
    tanvi, pallavi = Viewer.of(db, _user(db, "Tanvi")), Viewer.of(db, _user(db, "Pallavi"))
    assert keep_separate(db, t1.uuid, pallavi) is None  # not hers
    assert keep_separate(db, seeded["T5"].uuid, tanvi) is None  # already sent
    out = keep_separate(db, t1.uuid, tanvi)
    assert out == {"kept_separate": True, "found_while_drafting": 1}
    assert db.execute("SELECT kept_separate FROM ideas WHERE id = %s", (t1.uuid,)).fetchone()["kept_separate"]
    assert {x["outcome"] for x in _links(db, t1.uuid).values()} == {"kept_separate"}
    keep_separate(db, t2.uuid, tanvi)
    assert _links(db, t2.uuid)[seeded["R1"].ref]["outcome"] == "merge_asked"
    assert keep_separate(db, t1.uuid, tanvi, on=False) == {"kept_separate": False, "found_while_drafting": 1}
    assert {x["outcome"] for x in _links(db, t1.uuid).values()} == {None}


# ---- Review fixes (BLD-C096 to BLD-C099) -------------------------------------------------------------------------


def test_bld_c096_a_decrypt_failure_leaves_the_callers_transaction_usable(
    db: Any, seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """L-SIMILAR.failure: a failure before retrieval (the person's words cannot be opened) or an unknown idea,
    inside c/sort-submit's and c/draft's own transactions: `match_shared` answers -1 and `similar_for` None, neither
    raises, and the caller's transaction carries on."""
    t4, t2 = seeded["T4"], seeded["T2"]

    def cannot_open(*_: Any, **__: Any) -> str:
        raise ValueError("decrypt failed")

    monkeypatch.setattr(m, "open_text", cannot_open)
    with db.transaction():  # as c/sort-submit calls it
        assert match_shared(db, t4.uuid, found_while="checking") == -1
        assert db.execute("SELECT 1 AS ok").fetchone()["ok"] == 1
    with db.transaction():  # as c/draft calls it
        assert similar_for(db, t2.uuid, "SIP failure SMS gives no reason", "") is None
        assert db.execute("SELECT 1 AS ok").fetchone()["ok"] == 1
    row = db.execute("SELECT state, error_code FROM similar_runs WHERE idea_uuid = %s", (t4.uuid,)).fetchone()
    assert row["state"] == "failed" and row["error_code"] == "ValueError"

    unknown = str(uuid.uuid4())
    with db.transaction():
        assert match_shared(db, unknown, found_while="later") == -1
        assert similar_for(db, unknown, "A title", "A summary") is None
        assert db.execute("SELECT 1 AS ok").fetchone()["ok"] == 1
    assert db.execute("SELECT 1 FROM similar_runs WHERE idea_uuid = %s", (unknown,)).fetchone() is None


def test_bld_c097_a_word_only_in_one_sharers_messages_never_reaches_the_other(
    db: Any, seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """L-SIMILAR.rules/2, DEC-104 (non-negotiable 7): the judge reads each side's masked title and short summary,
    never the messages, so a detail only in Tanvi's messages (a made-up customer surname) cannot become the reason
    Rekha reads, even from a judge that repeats whatever it was given."""
    t2, r1 = seeded["T2"], seeded["R1"]
    secret = "Venkatachalapathy"
    mid = str(uuid.uuid4())
    db.execute(
        "INSERT INTO idea_messages (id, idea_uuid, seq, via, device, lang, text_encrypted, spans, char_count, "
        "created_at) SELECT %s, idea_uuid, seq + 1, via, device, lang, %s, '[]'::jsonb, %s, "
        "created_at + interval '1 minute' FROM idea_messages WHERE idea_uuid = %s ORDER BY seq DESC LIMIT 1",
        (mid, seal_text("idea_messages", "text_encrypted", mid, f"Mr {secret} called about it twice."), 33,
         t2.uuid),
    )  # fmt: skip
    assert secret in m.query_text(db, m._idea(db, t2.uuid) or {})  # retrieval still reads the person's words
    db.execute(
        "UPDATE ideas SET status = 'checking', shared_at = now(), idea_id = next_idea_ref() WHERE id = %s",
        (t2.uuid,),
    )
    seen: list[str] = []

    def echoing_judge(name: str, inputs: dict[str, Any], ref_id: str, **_: Any) -> Any:
        payload = json.dumps(inputs, ensure_ascii=False)
        seen.append(payload)
        reason = f"the same {secret} case" if secret in payload else "the same failed SIP debit"
        results = [
            {"cid": c["cid"], "label": "same", "reason": reason, "confidence": 0.9}
            for c in inputs["candidates"]
        ]
        return SimpleNamespace(data={"results": results, "best_same": None})

    monkeypatch.setattr(gateway, "run_agent", echoing_judge)
    assert match_shared(db, t2.uuid, found_while="checking") >= 1
    assert seen and all(secret not in p for p in seen)
    assert all(secret not in x["reason"] for x in _links(db, t2.uuid).values())
    rekha = Viewer.of(db, _user(db, "Rekha"))
    for_rekha = matches_for(db, r1.ref, rekha) or []
    t2_ref = db.execute("SELECT idea_id FROM ideas WHERE id = %s", (t2.uuid,)).fetchone()["idea_id"]
    assert any(x["idea"]["id"] == t2_ref for x in for_rekha)  # Rekha sees Tanvi's idea, and its reason …
    assert secret not in json.dumps(
        for_rekha, ensure_ascii=False
    )  # … never a word only Tanvi's messages hold


def test_bld_c097_a_judge_reason_failing_the_pattern_or_name_check_falls_back_to_code(
    db: Any, seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """L-SIMILAR.rules/2-3: a judge phrase holding an identifier the patterns catch (a distributor code) or a
    colleague's name is not shown; the reason is the one code builds from the words the two ideas share."""
    t2, r1 = seeded["T2"], seeded["R1"]
    rekha = db.execute("SELECT name FROM users WHERE name LIKE 'Rekha %'").fetchone()["name"]
    hits: list[m.Hit] = []
    real_retrieve = m.retrieve

    def keep_hits(*args: Any, **kwargs: Any) -> list[m.Hit]:
        hits[:] = real_retrieve(*args, **kwargs)
        return hits

    def judge_with_bad_reasons(name: str, inputs: dict[str, Any], ref_id: str, **_: Any) -> Any:
        results = []
        for c in inputs["candidates"]:
            close = c["cid"] == r1.ref
            reason = "the same ARN-123456 code" if close else f"raised by {rekha} as well"
            results.append(
                {
                    "cid": c["cid"],
                    "label": "same" if close else "related",
                    "reason": reason,
                    "confidence": 0.8,
                }
            )
        return SimpleNamespace(data={"results": results, "best_same": r1.ref})

    monkeypatch.setattr(m, "retrieve", keep_hits)
    monkeypatch.setattr(gateway, "run_agent", judge_with_bad_reasons)
    run = m.match_idea(db, t2.uuid, force=True)
    assert run.state == "done" and run.labelled_by == "judge" and run.matches
    idea = m._idea(db, t2.uuid) or {}
    text = m.query_text(db, idea)
    by_uuid = {h.uuid: h for h in hits}
    for f in run.matches:
        h = by_uuid[f.uuid]
        built = m.code_reason(f.strength, m.shared_words(text, h), h.area, h.area == (idea.get("area") or ""))
        fallback = "Close match: the same problem" if f.strength == "close" else "Related: a similar problem"
        assert f.reason == (checked_sentence(db, built) or fallback), f.uuid
        assert "ARN" not in f.reason and rekha.split()[0] not in f.reason
    assert any(f.uuid == r1.uuid and f.strength == "close" for f in run.matches)


def test_bld_c099_the_list_is_capped_at_8_close_first(db: Any, seeded: dict[str, Any]) -> None:
    """L-SIMILAR.rules/3: forward links kept after an outcome and reverse links are capped together at 8 on the
    GET route, after sorting, so every close match is kept."""
    t5 = seeded["T5"]
    close = ["R1", "R2", "V1"]
    others = close + [
        k
        for k, x in seeded.items()
        if x.ref and x.spec.owner != "tanvi" and x.spec.status != "merged" and k not in close
    ]
    assert len(others) >= 11
    for k in others:
        if k in close:  # newer ideas that found T5: reverse links
            db.execute(
                "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason, outcome) "
                "VALUES (%s, %s, 'close', 'Close match: the same status', NULL) ON CONFLICT DO NOTHING",
                (seeded[k].uuid, t5.uuid),
            )
        else:  # found by T5, kept after Keep mine separate
            db.execute(
                "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason, outcome) "
                "VALUES (%s, %s, 'related', 'Related: also about branches', 'kept_separate') ON CONFLICT DO NOTHING",
                (t5.uuid, seeded[k].uuid),
            )
    tanvi = Viewer.of(db, _user(db, "Tanvi"))
    out = matches_for(db, t5.ref, tanvi)
    assert out is not None and len(out) == m.MAX_MATCHES
    strengths = [x["strength"] for x in out]
    assert strengths == sorted(strengths, key=lambda s: s != "close")
    ids = {x["idea"]["id"] for x in out}
    assert {seeded[k].ref for k in close} <= ids  # every close match survives the cap


def test_bld_c099_withdrawn_and_own_ideas_never_show(
    db: Any, seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """L-SIMILAR.rules/1, /6: a stored link to an idea withdrawn since is hidden, both ways; so is an idea under any
    of the sharer's contributor codes (`owner_codes`, as retrieval has them: a re-hire)."""
    t5, k1, j1 = seeded["T5"], seeded["K1"], seeded["J1"]
    tanvi = Viewer.of(db, _user(db, "Tanvi"))
    db.execute(
        "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason) VALUES "
        "(%s, %s, 'related', 'Related: also about branches'), (%s, %s, 'related', 'Related: also about branches') "
        "ON CONFLICT DO NOTHING",
        (t5.uuid, k1.uuid, j1.uuid, t5.uuid),
    )
    shown = {x["idea"]["id"] for x in matches_for(db, t5.ref, tanvi) or []}
    assert {k1.ref, j1.ref} <= shown
    db.execute("UPDATE ideas SET status = 'withdrawn' WHERE id = ANY(%s::uuid[])", ([k1.uuid, j1.uuid],))
    shown = {x["idea"]["id"] for x in matches_for(db, t5.ref, tanvi) or []}
    assert not {k1.ref, j1.ref} & shown
    db.execute("UPDATE ideas SET status = %s WHERE id = %s", (k1.spec.status, k1.uuid))  # back, as seeded
    k1_code = db.execute("SELECT contributor_code FROM ideas WHERE id = %s", (k1.uuid,)).fetchone()
    real_owner_codes = views.owner_codes

    def rehired(conn: Any, code: str) -> set[str]:  # Tanvi's earlier code, before she re-joined
        return real_owner_codes(conn, code) | {str(k1_code["contributor_code"])}

    monkeypatch.setattr(views, "owner_codes", rehired)
    assert k1.ref not in {x["idea"]["id"] for x in matches_for(db, t5.ref, tanvi) or []}


def test_bld_c098_each_run_reads_only_changed_ideas_and_refreshes_the_stage(
    db: Any, seeded: dict[str, Any]
) -> None:
    """L-SIMILAR.rules/1: a match run reads only the ideas changed since their chunk; a stage change with the same
    words refreshes the chunk's stage without re-embedding; the indexer's loop sweeps them all."""
    r1 = seeded["R1"]
    first = index.sync(db, full=True)
    assert first["read"] >= 1
    again = index.sync(db)
    assert again["read"] == 0 and again["embedded"] == 0 and again["refreshed"] == 0
    db.execute("UPDATE ideas SET status = 'picked' WHERE id = %s", (r1.uuid,))
    after = index.sync(db)
    assert after["read"] == 1 and after["refreshed"] == 1 and after["embedded"] == 0
    stage = db.execute("SELECT stage FROM chunks WHERE idea_uuid = %s", (r1.uuid,)).fetchone()["stage"]
    assert stage == "picked"
    assert index.sync(db)["read"] == 0
    assert index.sync(db, full=True)["read"] == first["read"]


def test_bld_c187_l_teamup_rules_1_the_similar_read_carries_lane_fs_team_up_check(
    db: Any, seeded: dict[str, Any]
) -> None:
    """L-TEAMUP.rules/1, C-SIMGRID.tile, J-SHARE/8 (BLD-C187): each match carries `can_team_up` and `team_up_why_not`
    from lane F's `team_up_refusal`, the check `POST /ideas/:id/team-up` refuses by. An open idea: yes. Not now and
    Not picked: no, `idea_closed`. An idea the viewer is on the crew of: no, `already_on_crew`. Codes only."""
    t2, b1, g1, f1 = seeded["T2"], seeded["B1"], seeded["G1"], seeded["F1"]
    tanvi = Viewer.of(db, _user(db, "Tanvi"))
    db.execute(
        "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason) VALUES "
        "(%s, %s, 'related', 'Related: also about branches'), (%s, %s, 'related', 'Related: also about branches'), "
        "(%s, %s, 'related', 'Related: also about branches') ON CONFLICT DO NOTHING",
        (t2.uuid, b1.uuid, t2.uuid, g1.uuid, t2.uuid, f1.uuid),
    )
    out = {x["idea"]["id"]: x for x in matches_for(db, t2.uuid, tanvi) or []}
    assert out[b1.ref]["can_team_up"] is True and out[b1.ref]["team_up_why_not"] is None
    for closed in (g1, f1):  # not_now, not_picked
        assert out[closed.ref]["idea"]["status"] == closed.spec.status
        assert out[closed.ref]["can_team_up"] is False and out[closed.ref]["team_up_why_not"] == "idea_closed"
    code = tanvi.codes[0]
    db.execute(
        "INSERT INTO crew_members (idea_uuid, contributor_code, role, via) VALUES (%s, %s, 'crew', 'teamup')",
        (b1.uuid, code),
    )
    try:
        on = {x["idea"]["id"]: x for x in matches_for(db, t2.uuid, tanvi) or []}[b1.ref]
        assert on["can_team_up"] is False and on["team_up_why_not"] == "already_on_crew"
    finally:
        db.execute("DELETE FROM crew_members WHERE idea_uuid = %s AND contributor_code = %s", (b1.uuid, code))


def test_bld_c187_team_up_refusal_refuses_every_closed_state_before_reading_the_crew() -> None:
    """L-TEAMUP.rules/1, E-ENUMS.idea-status (BLD-C187): every status in the `closed` group (Not now, Not picked,
    Withdrawn, Merged) is `idea_closed` without a database read; an open idea with no contributor code reads nothing."""
    from onepc.enums import CLOSED_STATUSES
    from teamup.store import team_up_refusal

    class NoReads:
        def execute(self, *_a: Any, **_k: Any) -> Any:
            raise AssertionError("no read expected")

    assert set(CLOSED_STATUSES) == {"not_now", "not_picked", "withdrawn", "merged"}
    for status in CLOSED_STATUSES:
        assert team_up_refusal(NoReads(), {"id": "x", "status": status}, "C-1") == "idea_closed", status  # type: ignore[arg-type]
    assert team_up_refusal(NoReads(), {"id": "x", "status": "with_review_desk"}, None) is None  # type: ignore[arg-type]
