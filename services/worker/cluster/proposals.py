"""Review desk actions on a cluster proposal (§4.4 B steps 8–9). Each action is one transaction.

- `approve` (with optional edits to the name, description and problem): writes or updates the cluster, moves the
  member ideas to stage `in_cluster`, recomputes the centroid, writes `cluster.approved` and one history line per
  member to the outbox, tells every contributor, and runs the working-group trigger.
- `remove_member` (with a reason code): the idea leaves the proposal and a cannot-link pair keeps it apart.
- `reject` (with a reason code, and a note if wanted): cannot-link pairs for new and grow proposals; a rejected
  merge or split is not proposed again for 26 weeks.
Splitting a cluster, and merging a proposal into a cluster the batch did not name, are not built yet (the screen
says "Coming soon"); the desk can still reject those proposals.
"""

from __future__ import annotations

import datetime as dt
import itertools
from typing import Any

import numpy as np
from psycopg.types.json import Jsonb

from cluster.batch import record_run
from cluster.linkage import centroid
from comms.route import emit
from core import killswitch
from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from pii.detect import detect, directory
from pii.patterns import scan
from pii.tagger import TAG_RE, tag_payload
from review.service import ActionRefused, audited, staff_code
from rules import load_rule
from sla import engine

log = get_logger("cluster.proposals")
REJECT_CODES = ("not_same_problem", "too_broad", "too_narrow", "wrong_cluster", "other")
REMOVE_CODES = ("not_same_problem", "too_broad", "other")
ELIGIBLE_STAGES = ("reviewed", "in_cluster")
LIMITS = {"name": (3, 80), "description": (10, 220), "problem": (20, 1500)}


def _load(conn: Conn, item_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
    item = conn.execute("SELECT * FROM review_items WHERE id = %s FOR UPDATE", (item_id,)).fetchone()
    if item is None or item["item_type"] != "cluster_proposal":
        raise ActionRefused(404, "not_found")
    prop = conn.execute(
        "SELECT * FROM cluster_proposals WHERE review_item_id = %s FOR UPDATE", (item_id,)
    ).fetchone()
    if prop is None:
        raise ActionRefused(404, "not_found")
    if prop["state"] != "open" or item["state"] not in ("open", "in_progress"):
        raise ActionRefused(409, "already_decided")
    return dict(item), dict(prop)


def _refuse_linked(conn: Conn, user_id: str, idea_ids: list[str], action: str, item_id: int) -> None:
    """Nobody decides a group that holds an idea they shared or are linked to (joined, +1, BLD-093); the attempt
    is audited."""
    own = conn.execute(
        "SELECT 1 FROM contributor_map m WHERE m.user_id = %s AND m.contributor_code IN ("
        "SELECT contributor_code FROM ideas WHERE idea_id = ANY(%s) UNION SELECT contributor_code FROM idea_links "
        "WHERE idea_id = ANY(%s) OR from_idea_id = ANY(%s)) LIMIT 1",
        (user_id, idea_ids, idea_ids, idea_ids),
    ).fetchone()
    if own:
        raise ActionRefused(
            409,
            "own_idea",
            (f"user:{user_id}", "review.own_idea_refused", f"cluster_proposal:{item_id}", {"action": action}),
        )


def _members_of(conn: Conn, cluster_ids: list[str]) -> list[str]:
    rows = conn.execute(
        "SELECT idea_id FROM ideas WHERE cluster_id = ANY(%s) ORDER BY idea_id", (cluster_ids,)
    ).fetchall()
    return [r["idea_id"] for r in rows]


def _cannot_link(conn: Conn, pairs: list[tuple[str, str]], source: str, rev: str) -> int:
    n = 0
    for a, b in pairs:
        if a == b:
            continue
        lo, hi = sorted((a, b))
        n += conn.execute(
            "INSERT INTO cluster_pairs (idea_a, idea_b, source, created_by) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT DO NOTHING",
            (lo, hi, source, rev),
        ).rowcount
    return n


def _edited_text(conn: Conn, prop: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    """The summary with the reviewer's edits: pattern-checked, tagged under the proposal's scope; the description
    is shown on match cards to everyone, so it may not hold tags, names or identifiers."""
    summary: dict[str, Any] = dict(prop["summary"] or {})
    edits = {k: body[k] for k in LIMITS if isinstance(body.get(k), str) and body[k].strip()}
    for key, value in edits.items():
        text = " ".join(value.split()) if key != "problem" else value.strip()
        lo, hi = LIMITS[key]
        if not lo <= len(text) <= hi:
            raise ActionRefused(422, f"{key}_length")
        if any(m.action == "block" for m in scan(text, kfin_domains=get_settings().kfin_domains)):
            raise ActionRefused(422, "personal_data")
        # The name and description reach every contributor's inbox and match cards: no tags, names or IDs.
        if key in ("name", "description") and (TAG_RE.search(text) or detect(text, directory(conn))):
            raise ActionRefused(422, f"{key}_not_card_safe")
        if key == "name" and len(text.split()) > 8:
            raise ActionRefused(422, "name_too_long")
        summary[key] = str(tag_payload(conn, prop["tag_scope"], {"t": text}).payload["t"])
    for key in ("name", "description", "problem"):
        if not summary.get(key):
            raise ActionRefused(
                422, f"{key}_required"
            )  # the assistant could not draft it: the desk writes it
    summary.setdefault("variations", [])
    summary.setdefault("solution", [])
    summary.setdefault("open_questions", [])
    summary["edited"] = sorted(set(summary.get("edited") or []) | set(edits))
    return summary


def _vectors(conn: Conn, idea_ids: list[str]) -> list[list[float]]:
    import json

    rows = conn.execute(
        "SELECT c.embedding::text AS e FROM ideas i JOIN chunks c ON c.repo_path = i.repo_path AND c.file_type = 'idea' "
        "WHERE i.idea_id = ANY(%s)",
        (idea_ids,),
    ).fetchall()
    return [json.loads(r["e"]) for r in rows]


def _refresh_cluster(conn: Conn, cid: str) -> dict[str, Any]:
    """Member count, distinct contributors, LOBs, scope and centroid from the cluster's current members."""
    members = _members_of(conn, [cid])
    people = conn.execute(
        "SELECT count(DISTINCT code) AS n FROM (SELECT contributor_code AS code FROM ideas WHERE cluster_id = %s "
        "UNION SELECT contributor_code FROM idea_links WHERE cluster_id = %s AND link_type IN ('originator', 'joiner')) x",
        (cid, cid),
    ).fetchone()
    agg = conn.execute(
        "SELECT coalesce(array_agg(DISTINCT l), '{}') AS lobs, bool_or(scope = 'org-wide') AS org "
        "FROM ideas LEFT JOIN LATERAL unnest(lobs) l ON true WHERE cluster_id = %s",
        (cid,),
    ).fetchone()
    assert people is not None and agg is not None
    lobs = sorted(x for x in agg["lobs"] if x)
    scope = "org-wide" if agg["org"] else ("cross-lob" if len(lobs) > 1 else "lob")
    vecs = _vectors(conn, members)
    cen = centroid(np.asarray(vecs, dtype=np.float64)).tolist() if vecs else None
    conn.execute(
        "UPDATE clusters SET member_count = %s, distinct_contributors = %s, lobs = %s, scope = %s, "
        "centroid = %s::vector, members_changed_at = now() WHERE id = %s",
        (len(members), int(people["n"]), lobs, scope, str(cen) if cen else None, cid),
    )
    return {"members": members, "contributors": int(people["n"]), "lobs": lobs}


def _working_group_trigger(conn: Conn, cid: str) -> bool:
    """§4.4 B step 9: 3+ distinct contributors from 2+ LOBs → an admin item "Form a working group". The people
    view's suggestions arrive with the lenses (§4.14); until then the item lists the contributors only."""
    t = load_rule(get_settings().company_repo_path, "thresholds").data["working_group_trigger"]
    rows = conn.execute(
        "SELECT DISTINCT x.code, u.lob_id FROM (SELECT contributor_code AS code FROM ideas WHERE cluster_id = %s "
        "UNION SELECT contributor_code FROM idea_links WHERE cluster_id = %s AND link_type IN ('originator', 'joiner')) x "
        "LEFT JOIN contributor_map m ON m.contributor_code = x.code LEFT JOIN users u ON u.id = m.user_id",
        (cid, cid),
    ).fetchall()
    codes = sorted({r["code"] for r in rows})
    lobs = sorted({r["lob_id"] for r in rows if r["lob_id"]})
    if len(codes) < int(t["min_contributors"]) or len(lobs) < int(t["min_lobs"]):
        return False
    if conn.execute(
        "SELECT 1 FROM review_items WHERE item_type = 'working_group_trigger' AND ref_id = %s", (cid,)
    ).fetchone():
        return False
    conn.execute(
        "INSERT INTO review_items (item_type, ref_id, proposal) VALUES ('working_group_trigger', %s, %s)",
        (cid, Jsonb({"contributors": codes, "lobs": lobs, "suggested": []})),
    )
    return True


def _approve(
    conn: Conn,
    item: dict[str, Any],
    prop: dict[str, Any],
    reviewer: str,
    rev: str,
    body: dict[str, Any],
    now: dt.datetime,
) -> dict[str, Any]:
    kind = prop["kind"]
    if kind == "split":
        raise ActionRefused(409, "split_coming_soon")
    targets: list[str] = list(prop["targets"] or [])
    live = conn.execute(
        "SELECT id FROM clusters WHERE id = ANY(%s) AND state = 'approved' FOR UPDATE", (targets,)
    ).fetchall()
    if len(live) != len(targets):
        raise ActionRefused(409, "cluster_changed")  # a target was merged or retired since the run
    # Still open, still visible to everyone, and not taken into another cluster since the run (a new group takes
    # only ideas on their own; grow and merge also keep their targets' own members).
    eligible = [
        r["idea_id"]
        for r in conn.execute(
            "SELECT idea_id FROM ideas WHERE idea_id = ANY(%s) AND visibility = 'org' AND stage = ANY(%s) "
            "AND (cluster_id IS NULL OR cluster_id = ANY(%s)) ORDER BY idea_id FOR UPDATE",
            (list(prop["members"]), list(ELIGIBLE_STAGES), targets),
        ).fetchall()
    ]
    if kind == "new" and len(eligible) < 2:
        raise ActionRefused(409, "too_few_members")
    if kind == "grow" and not eligible:
        raise ActionRefused(409, "too_few_members")
    summary = _edited_text(conn, prop, body)
    title = summary.pop("name")
    if kind == "new":
        n = conn.execute("SELECT next_number('CL', '') AS n").fetchone()
        assert n is not None
        cid = f"CL-{int(n['n']):04d}"
        conn.execute("INSERT INTO clusters (id, stage) VALUES (%s, 'in_cluster')", (cid,))
        retired: list[str] = []
    else:
        cid, retired = sorted(targets)[0], sorted(targets)[1:]  # merge: the oldest group keeps its ID (§4.4)
    moved = _members_of(conn, retired) if retired else []
    for old in retired:
        conn.execute(
            "UPDATE clusters SET state = 'retired', merged_into = %s, members_changed_at = now() WHERE id = %s",
            (cid, old),
        )
        conn.execute(
            "UPDATE idea_links SET cluster_id = %s WHERE cluster_id = %s AND NOT EXISTS (SELECT 1 FROM idea_links x "
            "WHERE x.cluster_id = %s AND x.contributor_code = idea_links.contributor_code AND x.link_type = idea_links.link_type)",
            (cid, old, cid),
        )
    joined = sorted(set(eligible) | set(moved))
    conn.execute(
        "UPDATE ideas SET cluster_id = %s, stage = 'in_cluster' WHERE idea_id = ANY(%s)", (cid, joined)
    )
    for idea in conn.execute(
        "SELECT idea_id, contributor_code FROM ideas WHERE idea_id = ANY(%s)", (eligible,)
    ).fetchall():
        conn.execute(
            "INSERT INTO idea_links (cluster_id, from_idea_id, contributor_code, link_type) VALUES (%s, %s, %s, 'originator') "
            "ON CONFLICT DO NOTHING",
            (cid, idea["idea_id"], idea["contributor_code"]),
        )
        conn.execute(
            "INSERT INTO idea_links (cluster_id, from_idea_id, contributor_code, link_type) "
            "SELECT %s, from_idea_id, contributor_code, 'joiner' FROM idea_links WHERE idea_id = %s AND link_type = 'joiner' "
            "ON CONFLICT DO NOTHING",
            (cid, idea["idea_id"]),
        )
    conn.execute(
        "UPDATE clusters SET title = %s, summary = %s, tag_scope = %s, generated_by = %s, approved_by = %s, "
        "approved_at = %s, state = 'approved' WHERE id = %s",
        (title, Jsonb(summary), prop["tag_scope"], prop["generated_by"], rev, now, cid),
    )
    facts = _refresh_cluster(conn, cid)
    final = {"action": "approve", "cluster_id": cid, "members": joined, "edited": summary.get("edited") or []}
    conn.execute(
        "UPDATE review_items SET state = 'decided', decided_by = %s, decided_at = %s, final = %s WHERE id = %s",
        (reviewer, now, Jsonb(final), item["id"]),
    )
    conn.execute(
        "UPDATE cluster_proposals SET state = 'approved', decided_by = %s, decided_at = %s, cluster_id = %s, "
        "members = %s WHERE id = %s",
        (rev, now, cid, eligible, prop["id"]),
    )
    engine.stop(conn, "review_item", str(item["id"]), "cluster_proposal")
    outbox = "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES (%s, %s, %s, %s)"
    for old in retired:
        conn.execute(outbox, ("cluster.retired", old, rev, Jsonb({"note": f"merged into {cid}"})))
    conn.execute(
        outbox, ("cluster.approved", cid, rev, Jsonb({"verified_by": rev, "proposal_id": prop["id"]}))
    )
    for idea_id in joined:
        conn.execute(
            outbox,
            (
                "idea.stage_changed",
                idea_id,
                rev,
                Jsonb({"history": [{"event": "clustered", "by": rev, "note": cid}]}),
            ),
        )
    emit(conn, "cluster.approved", {"cluster_id": cid, "member_count": len(facts["members"])})
    wg = _working_group_trigger(conn, cid)
    if killswitch.is_on("committee.flow", conn):  # §4.5 trigger: an approved cluster goes to qualify
        from jobs.runner import enqueue

        # A job, after commit: the pre-check calls a model and must never fail or hold the approval (BLD-221).
        # Groups approved while the switch is off are picked up by `qualify.backfill` once it is on.
        enqueue(conn, "qualify.start", {"cluster_id": cid}, dedupe_key=f"qualify:{cid}")
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'cluster.approved', %s, %s)",
        (rev, f"cluster:{cid}", Jsonb({"proposal": prop["id"], "kind": kind, "members": len(joined)})),
    )
    record_run(conn, prop["run_id"])
    log.info("cluster.approved", cluster_id=cid, proposal_id=prop["id"], member_count=len(joined))
    return {"state": "decided", "cluster_id": cid, "members": joined, "working_group_item": wg}


def _reject(
    conn: Conn,
    item: dict[str, Any],
    prop: dict[str, Any],
    reviewer: str,
    rev: str,
    body: dict[str, Any],
    now: dt.datetime,
) -> dict[str, Any]:
    code = body.get("reason_code")
    if code not in REJECT_CODES:
        raise ActionRefused(400, "reason_code_required")
    note = str(body.get("note") or "").strip()
    tagged_note = None
    if note:
        if len(note) > 1000:
            raise ActionRefused(422, "note_length")
        if any(m.action == "block" for m in scan(note, kfin_domains=get_settings().kfin_domains)):
            raise ActionRefused(422, "personal_data")
        tagged_note = str(tag_payload(conn, prop["tag_scope"], {"t": note}).payload["t"])
    members: list[str] = list(prop["members"])
    pairs: list[tuple[str, str]] = []
    if prop["kind"] == "new":
        pairs = list(itertools.combinations(members, 2))
    elif prop["kind"] == "grow":
        pairs = [(m, e) for m in members for e in _members_of(conn, list(prop["targets"]))]
    added = _cannot_link(conn, pairs, "proposal_rejected", rev)
    final = {"action": "reject", "reason_code": code, "note": tagged_note, "cannot_links": added}
    conn.execute(
        "UPDATE review_items SET state = 'decided', decided_by = %s, decided_at = %s, final = %s WHERE id = %s",
        (reviewer, now, Jsonb(final), item["id"]),
    )
    conn.execute(
        "UPDATE cluster_proposals SET state = 'rejected', decided_by = %s, decided_at = %s WHERE id = %s",
        (rev, now, prop["id"]),
    )
    engine.stop(conn, "review_item", str(item["id"]), "cluster_proposal")
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'cluster.proposal_rejected', %s, %s)",
        (rev, f"cluster_proposal:{prop['id']}", Jsonb({"reason_code": code, "kind": prop["kind"]})),
    )
    record_run(conn, prop["run_id"])
    return {"state": "decided", "cannot_links": added}


def _remove(
    conn: Conn,
    item: dict[str, Any],
    prop: dict[str, Any],
    reviewer: str,
    rev: str,
    body: dict[str, Any],
    now: dt.datetime,
) -> dict[str, Any]:
    idea_id = str(body.get("idea_id") or "")
    code = body.get("reason_code")
    if code not in REMOVE_CODES:
        raise ActionRefused(400, "reason_code_required")
    if prop["kind"] not in ("new", "grow"):
        raise ActionRefused(409, "remove_not_available")
    members: list[str] = list(prop["members"])
    if idea_id not in members:
        raise ActionRefused(400, "not_a_member")
    rest = [m for m in members if m != idea_id]
    others = rest + (_members_of(conn, list(prop["targets"])) if prop["kind"] == "grow" else [])
    added = _cannot_link(conn, [(idea_id, o) for o in others], "member_removed", rev)
    dropped = [
        *list(prop["dropped"] or []),
        {"idea_id": idea_id, "reason": "", "removed_by": rev, "code": code},
    ]
    conn.execute(
        "UPDATE cluster_proposals SET members = %s, dropped = %s WHERE id = %s",
        (rest, Jsonb(dropped), prop["id"]),
    )
    conn.execute(
        "UPDATE review_items SET proposal = jsonb_set(proposal, '{members}', %s), state = 'in_progress', "
        "assigned_to = coalesce(assigned_to, %s) WHERE id = %s",
        (Jsonb(rest), reviewer, item["id"]),
    )
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'cluster.member_removed', %s, %s)",
        (rev, f"cluster_proposal:{prop['id']}", Jsonb({"idea_id": idea_id, "reason_code": code})),
    )
    return {"state": "in_progress", "members": rest, "cannot_links": added}


def act(
    conn: Conn, item_id: int, reviewer: str, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.UTC)
    action = body.get("action")
    if action not in ("approve", "reject", "remove_member"):
        raise ActionRefused(400, "unknown_action")
    with audited(conn), conn.transaction():
        item, prop = _load(conn, item_id)
        _refuse_linked(
            conn,
            reviewer,
            [*prop["members"], *_members_of(conn, list(prop["targets"]))],
            str(action),
            item_id,
        )
        rev = staff_code(conn, reviewer)
        if action == "approve":
            return _approve(conn, item, prop, reviewer, rev, body, now)
        if action == "reject":
            return _reject(conn, item, prop, reviewer, rev, body, now)
        return _remove(conn, item, prop, reviewer, rev, body, now)
