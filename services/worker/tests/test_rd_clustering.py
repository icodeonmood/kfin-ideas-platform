"""Weekly clustering (§4.4 B, review desk tools): the batch groups reviewed ideas and only proposes; the desk
approves, removes members or turns proposals down; approval writes the cluster, moves the members, tells the
contributors and runs the working-group trigger; turned-down groups and removed members become cannot-link pairs.
Vectors are written straight into `chunks` so the groups are known in advance."""

from __future__ import annotations

import json
import secrets
from typing import Any

import numpy as np
import pytest
from psycopg.types.json import Jsonb

from cluster import batch, proposals
from cluster.linkage import (
    Existing,
    apply_constraints,
    average_linkage,
    classify,
    normalise,
)
from core import killswitch
from okf.frontmatter import parse
from okf.validate import check_concept_meta
from repo_writer.writer import RepoWriter
from review.service import ActionRefused
from tests import helpers

DIM = 1024
T = {"grow_overlap": 0.5, "new_max_centroid": 0.80}


def _vec(axis: int, seed: int, noise: float = 0.005) -> list[float]:
    rng = np.random.default_rng(seed)
    v = rng.normal(scale=noise, size=DIM)
    v[axis] += 1.0
    return [float(x) for x in normalise(v.reshape(1, -1))[0]]


# ---- the arithmetic -------------------------------------------------------------------------------------------


def test_average_linkage_groups_near_vectors_and_leaves_far_ones_alone() -> None:
    v = np.array([_vec(0, 1), _vec(0, 2), _vec(0, 3), _vec(1, 4), _vec(1, 5), _vec(2, 6)])
    assert average_linkage(v, 0.25) == [[0, 1, 2], [3, 4], [5]]
    assert average_linkage(v, 0.0001) == [[0], [1], [2], [3], [4], [5]]


def test_constraints_merge_must_links_and_split_cannot_links() -> None:
    order = ["IDEA-2026-000001", "IDEA-2026-000002", "IDEA-2026-000003", "IDEA-2026-000004"]
    assert apply_constraints([[0, 1], [2], [3]], must=[(1, 2)], cannot=[], order=order) == [[0, 1, 2], [3]]
    # The later idea of a cannot-link pair leaves the group; a must-link never overrides it.
    assert apply_constraints([[0, 1, 2]], must=[(0, 2)], cannot=[(0, 2)], order=order) == [[0, 1], [2]]


def test_classify_names_new_grow_and_merge() -> None:
    c1 = Existing("CL-0001", {"IDEA-2026-000001", "IDEA-2026-000002"}, np.array(_vec(0, 1)))
    c2 = Existing("CL-0002", {"IDEA-2026-000003"}, np.array(_vec(1, 2)))
    far = np.array(_vec(5, 9))
    new = classify({"IDEA-2026-000010", "IDEA-2026-000011"}, far, set(), [c1, c2], T)
    assert new is not None and new.kind == "new" and new.members == ["IDEA-2026-000010", "IDEA-2026-000011"]
    grow = classify({"IDEA-2026-000012"}, np.array(_vec(0, 3)), {"CL-0001"}, [c1, c2], T)
    assert grow is not None and grow.kind == "grow" and grow.members == ["IDEA-2026-000012"]
    merge = classify({"IDEA-2026-000013"}, np.array(_vec(0, 3)), {"CL-0001", "CL-0002"}, [c1, c2], T)
    assert merge is not None and merge.kind == "merge" and merge.targets == ["CL-0001", "CL-0002"]
    # Near an existing cluster but not in it: no "new" proposal (centroid cosine ≥ 0.80).
    assert classify({"IDEA-2026-000014", "IDEA-2026-000015"}, np.array(_vec(0, 4)), set(), [c1], T) is None


# ---- the batch and the desk -------------------------------------------------------------------------------------

pytestmark_stack = pytest.mark.stack


def _user(db: Any, role: str | None = None, lob: str | None = None) -> tuple[str, str]:
    tag = secrets.token_hex(3)
    u = db.execute(
        "INSERT INTO users (emp_id_hash, name, email, source, lob_id) VALUES (%s, %s, %s, 'hr', %s) RETURNING id",
        (f"test:{tag}", f"Person {tag}", f"p.{tag}@kfintech.example", lob),
    ).fetchone()
    code = f"CTR-{secrets.token_hex(3)}"
    db.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, u["id"]))
    if role:
        db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, %s)", (u["id"], role))
    return str(u["id"]), code


def _reviewed(db: Any, vector: list[float], code: str, one_line: str | None = None) -> str:
    idea_id = helpers.insert_idea(db, contributor=code, stage="reviewed")
    path = f"ideas/2026/11/{idea_id}.md"
    if one_line:
        db.execute(
            "UPDATE ideas SET canvas = jsonb_set(jsonb_set(canvas, '{one_line}', %s), '{details}', %s) WHERE idea_id = %s",
            (Jsonb(one_line), Jsonb(one_line + " every week in operations."), idea_id),
        )
    db.execute("UPDATE ideas SET repo_path = %s WHERE idea_id = %s", (path, idea_id))
    db.execute(
        "INSERT INTO chunks (repo_path, file_type, section, text, embedding, trust) "
        "VALUES (%s, 'idea', 'card', 'card', %s::vector, 'human')",
        (path, json.dumps(vector)),
    )
    db.execute(
        "INSERT INTO review_items (item_type, ref_id, state, decided_at) VALUES ('idea', %s, 'decided', now())",
        (idea_id,),
    )
    return idea_id


@pytest.fixture
def pool(db: Any, company_repo: Any, test_database: str) -> Any:
    killswitch.clear_cache()
    db.execute(
        "TRUNCATE cluster_pairs, cluster_proposals, cluster_runs, contributor_map, role_grants, jobs CASCADE"
    )
    db.execute("DELETE FROM clusters")
    db.execute("DELETE FROM id_counters WHERE kind IN ('CL', 'REV')")
    people = [_user(db, lob=lob) for lob in ("LOB-mf", "LOB-sif", "LOB-mf", "LOB-nps", "LOB-mf")]
    a = [_reviewed(db, _vec(0, n), people[n][1]) for n in range(3)]  # one group, three people, two LOBs
    b = [_reviewed(db, _vec(1, 10 + n), people[3 + n][1]) for n in range(2)]  # another group
    lone = _reviewed(db, _vec(7, 99), people[0][1])
    reviewer, _ = _user(db, "reviewer")
    reviewer2, _ = _user(db, "reviewer")
    yield {"db": db, "a": a, "b": b, "lone": lone, "people": people, "reviewer": reviewer,
           "reviewer2": reviewer2, "repo": company_repo, "database": test_database}  # fmt: skip
    killswitch.clear_cache()


def _items(db: Any) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in db.execute(
            "SELECT p.*, r.state AS item_state FROM cluster_proposals p JOIN review_items r ON r.id = p.review_item_id "
            "ORDER BY p.id"
        ).fetchall()
    ]


@pytestmark_stack
def test_the_batch_only_proposes(pool: Any) -> None:
    db = pool["db"]
    # A colleague named in one card: the summary sees a tag, under the proposal's own scope, never the name.
    db.execute("UPDATE users SET name = 'Meera Venkataraman' WHERE id = %s", (pool["reviewer2"],))
    from pii import detect

    detect.clear_cache()
    db.execute(
        "UPDATE ideas SET canvas = jsonb_set(canvas, '{details}', to_jsonb('Meera Venkataraman checks these by hand'::text)) "
        "WHERE idea_id = %s",
        (pool["a"][0],),
    )
    out = batch.run_batch(db)
    assert out["state"] == "done" and out["pool_size"] == 6
    props = _items(db)
    assert sorted(tuple(p["members"]) for p in props) == sorted([tuple(pool["a"]), tuple(pool["b"])])
    assert all(p["kind"] == "new" and p["state"] == "open" and p["item_state"] == "open" for p in props)
    for p in props:
        assert (
            p["summary"]["name"]
            and p["summary"]["description"]
            and set(p["summary"]["refs"].values()) == set(p["members"])
        )
        assert p["tag_scope"].startswith("CLP-RUN-")
        timer = db.execute(
            "SELECT state FROM sla_timers WHERE entity_id = %s AND stage = 'cluster_proposal'",
            (str(p["review_item_id"]),),
        ).fetchone()
        assert timer["state"] == "running"
    # Nothing about any idea changed: agents propose, people decide.
    stages = {r["stage"] for r in db.execute("SELECT stage FROM ideas").fetchall()}
    assert stages == {"reviewed"} and db.execute("SELECT count(*) AS n FROM clusters").fetchone()["n"] == 0
    run = db.execute("SELECT * FROM cluster_runs").fetchone()
    assert run["state"] == "done" and run["counts"]["new"] == 2
    scopes = {r["scope_id"] for r in db.execute("SELECT DISTINCT scope_id FROM pseudonym_vault").fetchall()}
    a_scope = next(p["tag_scope"] for p in props if p["members"] == pool["a"])
    assert a_scope in scopes
    assert "Meera" not in str(next(p["summary"] for p in props if p["members"] == pool["a"]))
    assert db.execute(
        "SELECT 1 FROM outbox WHERE event_type = 'cluster.run_recorded' AND aggregate_id = %s", (run["id"],)
    ).fetchone()


@pytestmark_stack
def test_switched_off_the_batch_does_nothing(pool: Any) -> None:
    db = pool["db"]
    killswitch.set_switch(db, "clusters.batch", "off", reason="test switch off", actor="test")
    killswitch.clear_cache()
    assert batch.run_batch(db) == {"state": "skipped", "reason": "switched_off"}
    assert db.execute("SELECT count(*) AS n FROM cluster_runs").fetchone()["n"] == 0


@pytestmark_stack
def test_approve_writes_the_cluster_and_tells_everyone(pool: Any) -> None:
    db = pool["db"]
    batch.run_batch(db)
    prop = next(p for p in _items(db) if p["members"] == pool["a"])
    out = proposals.act(
        db,
        prop["review_item_id"],
        pool["reviewer"],
        {"action": "approve", "name": "Manual checks on SIP forms"},
    )
    cid = out["cluster_id"]
    assert cid == "CL-0001" and out["members"] == pool["a"]
    rows = db.execute("SELECT stage, cluster_id FROM ideas WHERE idea_id = ANY(%s)", (pool["a"],)).fetchall()
    assert {(r["stage"], r["cluster_id"]) for r in rows} == {("in_cluster", cid)}
    c = db.execute("SELECT * FROM clusters WHERE id = %s", (cid,)).fetchone()
    assert (
        c["title"] == "Manual checks on SIP forms"
        and c["member_count"] == 3
        and c["distinct_contributors"] == 3
    )
    assert (
        c["centroid"] is not None
        and c["approved_by"].startswith("REV-")
        and c["tag_scope"] == prop["tag_scope"]
    )
    events = [r["event_type"] for r in db.execute("SELECT event_type FROM outbox ORDER BY id").fetchall()]
    assert events.count("idea.stage_changed") == 3 and "cluster.approved" in events
    jobs = db.execute("SELECT payload FROM jobs WHERE type = 'comms.route'").fetchall()
    assert any(j["payload"]["event"] == "cluster.approved" for j in jobs)
    # Three contributors from two LOBs: the working-group trigger fires once.
    assert out["working_group_item"] is True
    wg = db.execute("SELECT proposal FROM review_items WHERE item_type = 'working_group_trigger'").fetchone()
    assert len(wg["proposal"]["contributors"]) == 3 and wg["proposal"]["lobs"] == ["LOB-mf", "LOB-sif"]
    assert db.execute("SELECT 1 FROM audit_log WHERE action = 'cluster.approved'").fetchone()
    with pytest.raises(ActionRefused) as again:
        proposals.act(db, prop["review_item_id"], pool["reviewer"], {"action": "approve"})
    assert again.value.code == "already_decided"

    # The repo writer writes a valid cluster file, the members' history lines and the run file.
    writer = RepoWriter(helpers.settings_for(pool["repo"], pool["database"]))
    assert writer.acquire()
    try:
        writer.run_once()
    finally:
        writer.release()
    assert db.execute("SELECT count(*) AS n FROM outbox WHERE committed_at IS NULL").fetchone()["n"] == 0
    text = (pool["repo"] / "clusters" / f"{cid}.md").read_text(encoding="utf-8")
    doc = parse(text)
    assert not [i for i in check_concept_meta(doc.meta or {}, f"clusters/{cid}.md") if i.level == "error"]
    assert doc.meta["kfin"]["members"] == pool["a"] and doc.meta["verified"][0]["by"].startswith("human:REV-")
    assert cid in (pool["repo"] / "clusters" / "index.md").read_text(encoding="utf-8")
    run_id = prop["run_id"]
    run_file = (pool["repo"] / "learning" / "cluster-runs" / f"{run_id}.md").read_text(encoding="utf-8")
    assert "| approved | 1 |" in run_file


@pytestmark_stack
def test_turning_down_keeps_them_apart_next_week(pool: Any) -> None:
    db = pool["db"]
    batch.run_batch(db)
    prop = next(p for p in _items(db) if p["members"] == pool["b"])
    proposals.act(
        db, prop["review_item_id"], pool["reviewer"], {"action": "reject", "reason_code": "not_same_problem"}
    )
    lo, hi = sorted(pool["b"])
    assert (
        db.execute("SELECT source FROM cluster_pairs WHERE idea_a = %s AND idea_b = %s", (lo, hi)).fetchone()[
            "source"
        ]
        == "proposal_rejected"
    )
    batch.run_batch(db)
    open_now = [p for p in _items(db) if p["state"] == "open"]
    assert [p["members"] for p in open_now] == [
        pool["a"]
    ]  # b is not proposed again; the old a proposal is superseded
    assert {p["state"] for p in _items(db) if p["members"] == pool["a"]} == {"open", "superseded"}


@pytestmark_stack
def test_remove_a_member_then_approve_the_rest(pool: Any) -> None:
    db = pool["db"]
    batch.run_batch(db)
    prop = next(p for p in _items(db) if p["members"] == pool["a"])
    gone = pool["a"][2]
    out = proposals.act(
        db,
        prop["review_item_id"],
        pool["reviewer"],
        {"action": "remove_member", "idea_id": gone, "reason_code": "other"},
    )
    assert out["members"] == pool["a"][:2] and out["cannot_links"] == 2
    approved = proposals.act(db, prop["review_item_id"], pool["reviewer"], {"action": "approve"})
    assert approved["members"] == pool["a"][:2]
    assert db.execute("SELECT stage FROM ideas WHERE idea_id = %s", (gone,)).fetchone()["stage"] == "reviewed"


@pytestmark_stack
def test_a_reviewer_cannot_decide_a_group_with_their_own_idea(pool: Any) -> None:
    db = pool["db"]
    batch.run_batch(db)
    prop = next(p for p in _items(db) if p["members"] == pool["a"])
    owner = db.execute(
        "SELECT user_id FROM contributor_map WHERE contributor_code = (SELECT contributor_code FROM ideas WHERE idea_id = %s)",
        (pool["a"][0],),
    ).fetchone()["user_id"]
    db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, 'reviewer')", (owner,))
    with pytest.raises(ActionRefused) as refused:
        proposals.act(db, prop["review_item_id"], str(owner), {"action": "approve"})
    assert refused.value.code == "own_idea"
    assert db.execute("SELECT 1 FROM audit_log WHERE action = 'review.own_idea_refused'").fetchone()


@pytestmark_stack
def test_the_description_must_be_safe_for_everyone(pool: Any) -> None:
    db = pool["db"]
    batch.run_batch(db)
    prop = next(p for p in _items(db) if p["members"] == pool["a"])
    from pii import detect

    db.execute("UPDATE users SET name = 'Meera Venkataraman' WHERE id = %s", (pool["reviewer2"],))
    detect.clear_cache()
    name = "Meera Venkataraman"  # a synthetic colleague (BLD-035)
    with pytest.raises(ActionRefused) as refused:
        proposals.act(
            db, prop["review_item_id"], pool["reviewer"],
            {"action": "approve", "description": f"Raised first by {name} in the Hyderabad branch."},
        )  # fmt: skip
    assert refused.value.code == "description_not_card_safe"


@pytestmark_stack
def test_a_later_idea_grows_the_approved_cluster(pool: Any) -> None:
    db = pool["db"]
    batch.run_batch(db)
    prop = next(p for p in _items(db) if p["members"] == pool["a"])
    cid = proposals.act(db, prop["review_item_id"], pool["reviewer"], {"action": "approve"})["cluster_id"]
    db.execute("UPDATE clusters SET members_changed_at = now() - interval '6 weeks' WHERE id = %s", (cid,))
    later = _reviewed(db, _vec(0, 50), pool["people"][4][1])
    batch.run_batch(db)
    grow = [p for p in _items(db) if p["state"] == "open" and p["kind"] == "grow"]
    assert len(grow) == 1 and grow[0]["targets"] == [cid] and grow[0]["members"] == [later]
    out = proposals.act(db, grow[0]["review_item_id"], pool["reviewer2"], {"action": "approve"})
    assert out["cluster_id"] == cid
    assert (
        db.execute("SELECT member_count FROM clusters WHERE id = %s", (cid,)).fetchone()["member_count"] == 4
    )


@pytestmark_stack
def test_a_join_keeps_two_ideas_together(pool: Any) -> None:
    db = pool["db"]
    far = _reviewed(db, _vec(9, 77), pool["people"][2][1])
    db.execute(
        "INSERT INTO idea_links (idea_id, from_idea_id, contributor_code, link_type) VALUES (%s, %s, %s, 'joiner')",
        (pool["lone"], far, pool["people"][2][1]),
    )
    batch.run_batch(db)
    assert sorted([pool["lone"], far]) in [p["members"] for p in _items(db)]


@pytestmark_stack
def test_the_outlier_check_drops_a_different_member(pool: Any) -> None:
    db = pool["db"]
    odd = _reviewed(
        db,
        _vec(0, 4),
        pool["people"][3][1],
        one_line="Canteen seating is cramped at lunch on the fourth floor",
    )
    batch.run_batch(db)
    prop = next(
        p
        for p in _items(db)
        if set(pool["a"]) <= set(p["members"]) or odd in [d["idea_id"] for d in p["dropped"]]
    )
    assert odd not in prop["members"] and odd in [d["idea_id"] for d in prop["dropped"]]
