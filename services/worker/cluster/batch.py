"""The weekly clustering batch (§4.4 B, job `cluster.batch`, Sunday 22:00 IST). It only proposes: every result is
a `cluster_proposal` item in the review queue, and nothing about a cluster changes until a reviewer approves it
(non-negotiable 5).

1. Pool: org-visible ideas reviewed in the last 26 weeks and not in a cluster, plus the members of clusters that
   changed in the last 4 weeks; approved cluster centroids join as anchors. Committee-only ideas stay out (BLD-205).
2. Vectors: the card embeddings already in `chunks`; nothing is re-embedded.
3. Group: average linkage at `cluster.small_pool_distance` (BLD-202), then the pair pass for ideas on their own.
4. Constraints: must-links merged, cannot-links kept apart.
5. Compare with approved clusters: grow, new, merge or split (`cluster.linkage.classify`).
6. Outlier check (judge, medoid against each member), 7. summary (cluster-summary), 8. proposals, 10. run record.

Model steps run through `run_agent` on cards restored from each idea's scope and tagged again under the
proposal's own scope (`cluster.cards`). If a model step is unavailable the proposal is still made and says which
check was skipped, so the desk knows to look harder.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
from psycopg.types.json import Jsonb

from cluster import cards
from cluster.linkage import (
    Existing,
    Proposal,
    apply_constraints,
    average_linkage,
    centroid,
    classify,
    medoid,
    merges_by_centroid,
    normalise,
    splits,
)
from core import killswitch
from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from gateway import AgentFailed, run_agent
from rules import load_rule
from sla import engine

log = get_logger("cluster.batch")
IST = ZoneInfo("Asia/Kolkata")
POOL_WEEKS = 26
CHANGED_WEEKS = 4
MAX_SUMMARY_MEMBERS = 30
MAX_JUDGE_CANDIDATES = 20
BATCH_LOCK = 4_201_114_201  # pg advisory lock id for "cluster batch"


@dataclass
class PoolIdea:
    idea_id: str
    cluster_id: str | None
    vector: np.ndarray


def thresholds() -> dict[str, Any]:
    return dict(load_rule(get_settings().company_repo_path, "thresholds").data["cluster"])


def run_id_for(conn: Conn, now: dt.datetime) -> str:
    year, week, _ = now.astimezone(IST).isocalendar()
    base = f"RUN-{year}-W{week:02d}"
    taken = {r["id"] for r in conn.execute("SELECT id FROM cluster_runs WHERE id LIKE %s", (base + "%",))}
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def _vec(text: Any) -> np.ndarray:
    return np.asarray(json.loads(str(text)), dtype=np.float64)


def load_pool(conn: Conn, now: dt.datetime) -> tuple[list[PoolIdea], int]:
    """Pool ideas with a card vector, and how many qualifying ideas had none (not indexed yet)."""
    rows = conn.execute(
        """
        SELECT i.idea_id, i.cluster_id, c.embedding::text AS embedding
        FROM ideas i
        LEFT JOIN LATERAL (SELECT embedding FROM chunks ch WHERE ch.repo_path = i.repo_path AND ch.file_type = 'idea'
                           ORDER BY ch.ordinal LIMIT 1) c ON true
        WHERE i.visibility = 'org' AND (
          (i.stage = 'reviewed' AND i.cluster_id IS NULL AND EXISTS (
             SELECT 1 FROM review_items r WHERE r.item_type = 'idea' AND r.ref_id = i.idea_id
             AND r.state = 'decided' AND r.decided_at > %(now)s - make_interval(weeks => %(pool)s)))
          OR (i.stage = 'in_cluster' AND i.cluster_id IN (
             SELECT id FROM clusters WHERE state = 'approved'
             AND members_changed_at > %(now)s - make_interval(weeks => %(changed)s))))
        ORDER BY i.idea_id
        """,
        {"now": now, "pool": POOL_WEEKS, "changed": CHANGED_WEEKS},
    ).fetchall()
    pool = [PoolIdea(r["idea_id"], r["cluster_id"], _vec(r["embedding"])) for r in rows if r["embedding"]]
    return pool, sum(1 for r in rows if not r["embedding"])


def load_clusters(conn: Conn) -> list[Existing]:
    out = []
    for r in conn.execute(
        "SELECT c.id, c.centroid::text AS centroid, coalesce(array_agg(i.idea_id) FILTER (WHERE i.idea_id IS NOT NULL), "
        "'{}') AS members FROM clusters c LEFT JOIN ideas i ON i.cluster_id = c.id "
        "WHERE c.state = 'approved' GROUP BY c.id ORDER BY c.id"
    ).fetchall():
        out.append(Existing(r["id"], set(r["members"]), _vec(r["centroid"]) if r["centroid"] else None))
    return out


def must_links(conn: Conn, ids: list[str]) -> list[tuple[str, str]]:
    """Joins and a reviewer's attach-to-idea between two ideas (§4.4 A)."""
    rows = conn.execute(
        "SELECT idea_id, from_idea_id FROM idea_links WHERE idea_id IS NOT NULL AND from_idea_id IS NOT NULL "
        "AND link_type IN ('joiner', 'plus_one') AND (idea_id = ANY(%s) OR from_idea_id = ANY(%s))",
        (ids, ids),
    ).fetchall()
    return [(r["idea_id"], r["from_idea_id"]) for r in rows if r["idea_id"] != r["from_idea_id"]]


def cannot_links(conn: Conn, ids: list[str]) -> set[tuple[str, str]]:
    rows = conn.execute(
        "SELECT idea_a, idea_b FROM cluster_pairs WHERE kind = 'cannot_link' AND idea_a = ANY(%s) AND idea_b = ANY(%s)",
        (ids, ids),
    ).fetchall()
    return {(r["idea_a"], r["idea_b"]) for r in rows}


def _judge_same(conn: Conn, scope: str, card: dict[str, Any], others: list[dict[str, Any]]) -> dict[str, str]:
    """Labels from the judge for `others` against `card`; raises AgentFailed when it cannot run."""
    out = run_agent(
        "judge",
        {
            "card": cards.judge_card(conn, card),
            "candidates": [cards.judge_candidate(conn, o) for o in others],
            "past_corrections": [],
        },
        scope,
        conn=conn,
    )
    return {r["cid"]: r["label"] for r in out.data["results"]} | {
        f"reason:{r['cid']}": r["reason"] for r in out.data["results"]
    }


class Run:
    def __init__(self, conn: Conn, now: dt.datetime, run_id: str) -> None:
        self.conn, self.now, self.run_id = conn, now, run_id
        self.t = thresholds()
        self.counts: dict[str, int] = {
            "new": 0,
            "grow": 0,
            "merge": 0,
            "split": 0,
            "dropped": 0,
            "skipped_checks": 0,
        }
        self.seq = 0

    def scope(self) -> str:
        self.seq += 1
        return f"CLP-{self.run_id}-{self.seq}"

    # -- steps 1–4 ---------------------------------------------------------------------------------------------

    def groups(
        self, pool: list[PoolIdea], clusters: list[Existing]
    ) -> tuple[list[tuple[set[str], set[str]]], int]:
        """(idea IDs, anchor cluster IDs) per group, and the number of pair-pass pairs."""
        anchors = [c for c in clusters if c.centroid is not None]
        n = len(pool)
        vectors = np.vstack(
            [p.vector for p in pool] + [c.centroid for c in anchors if c.centroid is not None]
        )
        raw = average_linkage(vectors, float(self.t["small_pool_distance"]))
        # A must-link to an idea already in an approved cluster pulls the pool idea to that cluster's anchor.
        index = {p.idea_id: i for i, p in enumerate(pool)}
        anchor_index = {c.id: n + j for j, c in enumerate(anchors)}
        member_of = {m: c.id for c in clusters for m in c.members}
        must: list[tuple[int, int]] = []
        for a, b in must_links(self.conn, [p.idea_id for p in pool]):
            ia = index.get(a, anchor_index.get(member_of.get(a, ""), -1))
            ib = index.get(b, anchor_index.get(member_of.get(b, ""), -1))
            if ia >= 0 and ib >= 0 and ia != ib:
                must.append((ia, ib))
        banned = cannot_links(self.conn, [p.idea_id for p in pool])
        cannot = [(index[a], index[b]) for a, b in banned if a in index and b in index]
        order = [p.idea_id for p in pool] + [
            f"~{c.id}" for c in anchors
        ]  # anchors sort last, never moved first
        grouped = apply_constraints(raw, must, cannot, order)
        pairs = self.pair_pass(pool, grouped, banned)
        out: list[tuple[set[str], set[str]]] = []
        for g in grouped + pairs:
            ideas = {pool[i].idea_id for i in g if i < n}
            anchored = {anchors[i - n].id for i in g if i >= n}
            if ideas:
                out.append((ideas, anchored))
        paired = {i for g in pairs for i in g}
        out = [g for g in out if not (len(g[0]) == 1 and not g[1] and index[next(iter(g[0]))] in paired)]
        return out, len(pairs)

    def pair_pass(
        self, pool: list[PoolIdea], grouped: list[list[int]], banned: set[tuple[str, str]]
    ) -> list[list[int]]:
        """Ideas still on their own: mutual nearest neighbours at cosine ≥ `pair_cosine` that the judge calls
        "same" become a two-member group."""
        n = len(pool)
        alone = [g[0] for g in grouped if len(g) == 1 and g[0] < n]
        if len(alone) < 2:
            return []
        v = normalise(np.vstack([pool[i].vector for i in alone]))
        sims = v @ v.T
        np.fill_diagonal(sims, -1.0)
        nearest = sims.argmax(axis=1)
        pairs: list[list[int]] = []
        for a in range(len(alone)):
            b = int(nearest[a])
            if a >= b or int(nearest[b]) != a or sims[a, b] < float(self.t["pair_cosine"]):
                continue
            ia, ib = alone[a], alone[b]
            ida, idb = sorted((pool[ia].idea_id, pool[ib].idea_id))
            if (ida, idb) in banned:
                continue
            rows = cards.ideas(self.conn, [ida, idb])
            try:
                labels = _judge_same(self.conn, self.scope(), rows[ida], [rows[idb]])
            except AgentFailed:
                self.counts["skipped_checks"] += 1
                continue
            if labels.get(idb) == "same":
                pairs.append(sorted([ia, ib]))
        return pairs

    # -- step 5 ------------------------------------------------------------------------------------------------

    def proposals(
        self, groups: list[tuple[set[str], set[str]]], pool: list[PoolIdea], clusters: list[Existing]
    ) -> list[Proposal]:
        vec = {p.idea_id: p.vector for p in pool}
        found: list[Proposal] = []
        with_vectors: list[tuple[set[str], np.ndarray]] = []
        for ideas, anchored in groups:
            cen = centroid(np.vstack([vec[i] for i in sorted(ideas)]))
            with_vectors.append((ideas, cen))
            p = classify(ideas, cen, anchored, clusters, self.t)
            if p is not None:
                found.append(p)
        found += merges_by_centroid(clusters, float(self.t["merge_centroid"]))
        found += splits(clusters, with_vectors, float(self.t["split_between"]))
        seen: set[tuple[str, tuple[str, ...], tuple[str, ...]]] = set()
        unique = []
        for p in found:
            key = (p.kind, tuple(p.targets), tuple(p.members) if p.kind in ("new", "grow") else ())
            if key not in seen and not self.recently_rejected(p):
                seen.add(key)
                unique.append(p)
        return unique

    def recently_rejected(self, p: Proposal) -> bool:
        """A merge or split the desk rejected in the pool window is not proposed again (BLD-206)."""
        if p.kind not in ("merge", "split"):
            return False
        row = self.conn.execute(
            "SELECT 1 FROM cluster_proposals WHERE kind = %s AND targets = %s AND state = 'rejected' "
            "AND decided_at > %s - make_interval(weeks => %s) LIMIT 1",
            (p.kind, sorted(p.targets), self.now, POOL_WEEKS),
        ).fetchone()
        return row is not None

    # -- steps 6–8 ---------------------------------------------------------------------------------------------

    def outliers(
        self, p: Proposal, scope: str, clusters: list[Existing], vec: dict[str, np.ndarray]
    ) -> list[dict[str, Any]]:
        """Judge the medoid against each proposed member; members labelled "different" are dropped."""
        if p.kind not in ("new", "grow"):
            return []
        existing = next((c for c in clusters if c.id in p.targets), None)
        everyone = sorted(set(p.members) | (existing.members if existing else set()))
        known = [i for i in everyone if i in vec]
        if len(known) < 2:
            return []
        centre = known[medoid(np.vstack([vec[i] for i in known]))]
        checked = [i for i in p.members if i != centre][:MAX_JUDGE_CANDIDATES]
        if not checked:
            return []
        rows = cards.ideas(self.conn, [centre, *checked])
        labels = _judge_same(self.conn, scope, rows[centre], [rows[i] for i in checked if i in rows])
        dropped = [
            {"idea_id": i, "reason": labels.get(f"reason:{i}", "")}
            for i in checked
            if labels.get(i) == "different"
        ]
        p.members = [m for m in p.members if m not in {d["idea_id"] for d in dropped}]
        return dropped

    def summary(
        self, p: Proposal, scope: str, clusters: list[Existing]
    ) -> tuple[dict[str, Any] | None, str | None]:
        existing_cluster = (
            next((c for c in clusters if c.id in p.targets), None) if p.kind == "grow" else None
        )
        member_ids = sorted(set(p.members) | (existing_cluster.members if existing_cluster else set()))
        rows = cards.ideas(self.conn, member_ids[:MAX_SUMMARY_MEMBERS])
        members = [
            cards.member_card(self.conn, f"M{n}", rows[i]) for n, i in enumerate(sorted(rows), start=1)
        ]
        existing = None
        if existing_cluster is not None:
            existing = self.existing_text(existing_cluster.id)
        try:
            out = run_agent(
                "cluster-summary",
                {"members": members, "existing": existing, "mode": "cluster"},
                scope,
                conn=self.conn,
            )
        except AgentFailed:
            return None, None
        refs = {f"M{n}": i for n, i in enumerate(sorted(rows), start=1)}
        data = dict(out.data)
        data["refs"] = refs  # member ref → IDEA- ID, for the credits
        return data, f"cluster-summary/{out.version}"

    def existing_text(self, cluster_id: str) -> dict[str, Any] | None:
        from pii import vault
        from pii.restore import restore

        row = self.conn.execute(
            "SELECT title, summary, tag_scope FROM clusters WHERE id = %s", (cluster_id,)
        ).fetchone()
        if not row or not row["title"]:
            return None
        text = {"name": row["title"], "problem": (row["summary"] or {}).get("problem") or ""}
        return (
            dict(restore(text, vault.mapping(self.conn, row["tag_scope"]), "real"))
            if row["tag_scope"]
            else text
        )

    def propose(
        self,
        p: Proposal,
        scope: str,
        summary: dict[str, Any] | None,
        by: str | None,
        dropped: list[dict[str, Any]],
        skipped: list[str],
    ) -> int:
        item = self.conn.execute(
            "INSERT INTO review_items (item_type, ref_id, proposal, reasons) VALUES ('cluster_proposal', %s, %s, %s) "
            "RETURNING id",
            (
                scope,
                Jsonb({"kind": p.kind, "targets": p.targets, "members": p.members, "run_id": self.run_id}),
                Jsonb({"checks_skipped": skipped} if skipped else {}),
            ),
        ).fetchone()
        assert item is not None
        self.conn.execute(
            "INSERT INTO cluster_proposals (run_id, review_item_id, kind, targets, members, dropped, split_groups, "
            "metrics, summary, generated_by, tag_scope) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                self.run_id, item["id"], p.kind, p.targets, p.members, Jsonb(dropped),
                Jsonb(p.groups) if p.kind == "split" else None, Jsonb(p.metrics),
                Jsonb(summary) if summary else None, by, scope,
            ),
        )  # fmt: skip
        engine.start(self.conn, "review_item", str(item["id"]), "cluster_proposal", now=self.now)
        return int(item["id"])


def supersede_open(conn: Conn, run_id: str) -> int:
    """Open proposals from earlier runs are replaced by this run's view of the pool."""
    rows = conn.execute(
        "UPDATE cluster_proposals SET state = 'superseded' WHERE state = 'open' RETURNING review_item_id"
    ).fetchall()
    for r in rows:
        conn.execute(
            "UPDATE review_items SET state = 'closed', final = %s WHERE id = %s",
            (Jsonb({"superseded_by": run_id}), r["review_item_id"]),
        )
        engine.stop(conn, "review_item", str(r["review_item_id"]), "cluster_proposal")
    return len(rows)


def record_run(conn: Conn, run_id: str) -> None:
    """The run file in `learning/cluster-runs/` is (re)written by the repo writer from `cluster_runs`."""
    conn.execute(
        "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES ('cluster.run_recorded', %s, %s, %s)",
        (run_id, "process:cluster-batch", Jsonb({"run_id": run_id})),
    )


def run_batch(conn: Conn, now: dt.datetime | None = None, *, manual_by: str | None = None) -> dict[str, Any]:
    """One clustering run. Returns the run record. Refuses (returns state "skipped") while `clusters.batch` is off."""
    now = now or dt.datetime.now(dt.UTC)
    if not killswitch.is_on("clusters.batch", conn):
        log.info("cluster.batch_skipped", reason_code="switched_off")
        return {"state": "skipped", "reason": "switched_off"}
    # One run at a time, across workers: a second job (weekly and manual together) skips itself.
    if not conn.execute("SELECT pg_try_advisory_lock(%s) AS ok", (BATCH_LOCK,)).fetchone()["ok"]:  # type: ignore[index]
        log.info("cluster.batch_skipped", reason_code="already_running")
        return {"state": "skipped", "reason": "already_running"}
    try:
        return _run_locked(conn, now, manual_by)
    finally:
        conn.execute("SELECT pg_advisory_unlock(%s)", (BATCH_LOCK,))


def _run_locked(conn: Conn, now: dt.datetime, manual_by: str | None) -> dict[str, Any]:
    run_id = run_id_for(conn, now)
    params = {
        **thresholds(),
        "method": "average_linkage",
        "pool_weeks": POOL_WEEKS,
        "changed_weeks": CHANGED_WEEKS,
    }
    conn.execute(
        "INSERT INTO cluster_runs (id, params) VALUES (%s, %s)",
        (run_id, Jsonb(params | ({"manual_by": manual_by} if manual_by else {}))),
    )
    try:
        with conn.transaction():
            run = Run(conn, now, run_id)
            pool, unindexed = load_pool(conn, now)
            clusters = load_clusters(conn)
            superseded = supersede_open(conn, run_id)
            groups, pairs = run.groups(pool, clusters) if pool else ([], 0)
            vec = {p.idea_id: p.vector for p in pool}
            made = 0
            for p in run.proposals(groups, pool, clusters):
                scope = run.scope()
                skipped: list[str] = []
                try:
                    dropped = run.outliers(p, scope, clusters, vec)
                except AgentFailed:
                    dropped, skipped = [], ["outlier_check"]
                if (p.kind == "new" and len(p.members) < 2) or (p.kind == "grow" and not p.members):
                    run.counts["dropped"] += len(dropped)
                    continue
                summary, by = (
                    run.summary(p, scope, clusters) if p.kind in ("new", "grow", "merge") else (None, None)
                )
                if summary is None and p.kind in ("new", "grow", "merge"):
                    skipped.append("summary")
                run.counts["skipped_checks"] += len(skipped)
                run.counts["dropped"] += len(dropped)
                run.propose(p, scope, summary, by, dropped, skipped)
                run.counts[p.kind] += 1
                made += 1
            counts = run.counts | {
                "pairs": pairs,
                "unindexed": unindexed,
                "superseded": superseded,
                "proposals": made,
            }
            conn.execute(
                "UPDATE cluster_runs SET state = 'done', pool_size = %s, anchors = %s, counts = %s, finished_at = now() "
                "WHERE id = %s",
                (len(pool), sum(1 for c in clusters if c.centroid is not None), Jsonb(counts), run_id),
            )
            record_run(conn, run_id)
    except Exception as exc:
        conn.execute(
            "UPDATE cluster_runs SET state = 'failed', error_code = %s, finished_at = now() WHERE id = %s",
            (type(exc).__name__, run_id),
        )
        log.error("cluster.batch_failed", run_id=run_id, error_type=type(exc).__name__)
        raise
    log.info("cluster.batch_done", run_id=run_id, pool_size=len(pool), proposal_count=made)
    return {"state": "done", "run_id": run_id, "pool_size": len(pool), "counts": counts}
