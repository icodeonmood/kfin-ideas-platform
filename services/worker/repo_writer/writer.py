"""The repo writer: the only process allowed to commit to the company repo (§2.7).

It reads `outbox` rows in ID order and turns each into exactly one commit:

    [IDEA-2026-000142] submitted
    actor: CTR-7f3a91
    event: idea.submitted
    outbox: 88213

Exactly once, even across crashes: the `outbox:` trailer is the idempotency key. If the process dies after
`git commit` but before the database records it, the next run finds the trailer and records that SHA
instead of committing again. A half-written working tree is discarded (the writer owns it) and re-rendered
from the database. A Postgres advisory lock keeps it to one writer at a time.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from core.config import Settings, get_settings
from core.db import Conn, connect
from core.logging import get_logger
from okf.frontmatter import parse
from okf.validate import check_concept_meta
from pii.patterns import scan
from repo_writer.git import Git, GitError, seed_in_progress, seed_marker_age
from repo_writer.render import (
    HistoryRow,
    existing_state,
    index_line,
    ist,
    render_idea,
    repo_path_for,
)
from repo_writer.render_appeal import appeal_index_line, appeals_index, render_appeal
from repo_writer.render_cluster import cluster_index_line, render_cluster, render_run, run_index_line
from repo_writer.render_decision import cluster_sections, decision_index_line, render_decision
from repo_writer.render_docs import doc_index_line, doc_problem, solution_doc, taxonomy_doc

log = get_logger("repo_writer")

WRITER_LOCK_KEY = 4_201_108_001  # pg advisory lock id for "repo writer"
IDEA_EVENTS = {"idea.submitted", "idea.updated", "idea.scanned", "idea.reviewed", "idea.stage_changed"}
CLUSTER_EVENTS = {"cluster.approved", "cluster.retired", "cluster.updated"}
RUN_EVENT = "cluster.run_recorded"
# `make demo-reset` takes the demo's own idea files out of the local dev repo (Ones review). Refused anywhere but
# APP_ENV=dev, and only for a path the event names exactly.
DEMO_REMOVED = "idea.demo_removed"
# Documents written from approved records (BLD-133, BLD-136): payloads carry IDs only; text comes from the database.
SOLUTION_EVENT = "solution.published"
GLOSSARY_EVENT = "taxonomy.glossary_added"
AREA_EVENT = "taxonomy.area_added"
DOC_EVENTS = {SOLUTION_EVENT, GLOSSARY_EVENT, AREA_EVENT}
DEMO_PATH = re.compile(r"ideas/[0-9]{4}/[0-9]{2}/(IDEA-[0-9]{4}-[0-9]{6})\.md")
DECISION_EVENT = "decision.recorded"
APPEAL_EVENTS = {"appeal.filed", "appeal.decided"}
NOTE_MAX = 120
PUSH_BACKOFF_S = (2, 5, 15, 60)
RETRY_BACKOFF_S = (1, 5, 15, 60)
STUCK_AFTER_ATTEMPTS = 5
PUSH_ALERT_AFTER_S = 15 * 60
SEED_SLOW_S = 60  # a seed holding the marker longer than this is worth a warning (BLD-A167)


class LockLost(RuntimeError):
    """The single-writer lock is not held; continuing could commit an event twice."""


class EventError(Exception):
    """An event that cannot be written. `code` goes to outbox.last_error (codes only, never text)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class DeadLetter(EventError):
    """An event that can never be written as it stands (a hand-added file, personal data that slipped through). It
    leaves the head of the queue: dead-lettered, alerted, retried only by hand (RUNBOOK §4.8, BLD-143)."""


@dataclass(frozen=True)
class Outcome:
    outbox_id: int
    commit_sha: str
    recovered: bool


def _fault_after_commits() -> int | None:
    """Test-only fault injection (AT-B1-05). Ignored outside dev and test."""
    spec = os.environ.get("REPO_WRITER_FAULT", "")
    if os.environ.get("APP_ENV", "dev") not in {"dev", "test"} or not spec.startswith("crash_after_commit:"):
        return None
    return int(spec.split(":", 1)[1])


def _safe_note(note: Any) -> str:
    """History notes are written by our code ("proposed CL-0012 (high)"), never by people. Enforce it."""
    text = str(note or "").strip()
    if len(text) > NOTE_MAX or "\n" in text or "|" in text or scan(text):
        raise EventError("note_rejected")
    return text


class RepoWriter:
    def __init__(self, settings: Settings | None = None, database_url: str | None = None) -> None:
        self.settings = settings or get_settings()
        self.database_url = database_url or self.settings.database_url
        self.repo = Path(self.settings.company_repo_path)
        self.git = Git(self.repo, self.settings.repo_writer_author)
        self._lock_conn: Conn | None = None
        self._commits_this_run = 0
        self._crash_after = _fault_after_commits()
        self._next_push_at = 0.0
        self._retry_at: dict[int, float] = {}
        self._push_failures = 0
        self._push_failing_since: float | None = None

    # ---- single-writer lock ----------------------------------------------------------------------
    def acquire(self) -> bool:
        if self._lock_conn is None:
            self._lock_conn = connect(self.database_url, autocommit=True)
        row = self._lock_conn.execute("SELECT pg_try_advisory_lock(%s) AS ok", (WRITER_LOCK_KEY,)).fetchone()
        return bool(row and row["ok"])

    def release(self) -> None:
        if self._lock_conn is not None:
            self._lock_conn.close()
            self._lock_conn = None

    # ---- main loop -------------------------------------------------------------------------------
    def _assert_lock(self) -> None:
        """Exactly-once depends on being the only writer: refuse to run unless our lock session is alive."""
        if self._lock_conn is None:
            raise LockLost("acquire() the writer lock before run_once()")
        try:
            self._lock_conn.execute("SELECT 1")
        except Exception as exc:
            self._lock_conn = None
            raise LockLost("writer lock session dropped") from exc

    def run_once(self, limit: int = 100) -> list[Outcome]:
        """Commit up to `limit` pending events in order. Stops at the first event that fails."""
        self._assert_lock()
        if not self.git.is_repo():
            raise GitError("company repo not found; run `make seed` first")
        if seed_in_progress(self.git.path):  # a seed is writing the repo: never reset it (BLD-A167)
            age = seed_marker_age(self.git.path) or 0.0
            (log.warning if age > SEED_SLOW_S else log.info)("repo_writer.waiting_for_seed", seconds=int(age))
            return []
        if (
            self.git.head() is None
        ):  # initialised but never committed: a seed's first moments, or a bad restore
            log.warning("repo_writer.repo_has_no_commit")
            return []
        self.git.clear_stale_locks()  # safe: we hold the only writer lock
        if self.git.is_dirty():
            log.warning("repo_writer.dirty_tree_reset")
            self.git.reset_hard()
        done: list[Outcome] = []
        recovered = self.git.outbox_commits()
        # autocommit: each event's `conn.transaction()` below is a real commit, not a savepoint.
        with connect(self.database_url, autocommit=True) as conn:
            pending = conn.execute(
                "SELECT id, event_type, aggregate_id, actor, payload, created_at, attempts "
                "FROM outbox WHERE committed_at IS NULL AND dead_lettered_at IS NULL ORDER BY id LIMIT %s",
                (limit,),
            ).fetchall()
            for event in pending:
                if time.monotonic() < self._retry_at.get(int(event["id"]), 0.0):
                    break  # still backing off on the event at the head of the queue
                if seed_in_progress(self.git.path):
                    break  # a seed started during this round; the rest wait for the next one (BLD-A167)
                try:
                    outcome = self._one(conn, event, recovered)
                except DeadLetter as exc:
                    self._dead_letter(conn, event, exc.code)
                    continue  # never blocks the events behind it
                except EventError as exc:
                    self._record_failure(conn, event, exc.code)
                    break
                except GitError:
                    self.git.reset_hard()
                    self._record_failure(conn, event, "git_error")
                    break
                except Exception as exc:  # anything else: record the type, never the message
                    self._record_failure(conn, event, type(exc).__name__)
                    break
                self._retry_at.pop(outcome.outbox_id, None)
                done.append(outcome)
        if done or self._push_failures:
            self._push()
        return done

    def run_forever(self, stop: Any = None) -> None:
        while not self.acquire():
            log.info("repo_writer.waiting_for_lock")
            time.sleep(5)
        log.info("repo_writer.started")
        try:
            while stop is None or not stop.is_set():
                try:
                    outcomes = self.run_once()
                except LockLost:
                    log.error("repo_writer.lock_lost")
                    raise  # the service exits and restarts with a fresh lock
                except Exception:
                    log.exception("repo_writer.loop_error")
                    outcomes = []
                if not outcomes:
                    time.sleep(self.settings.repo_writer_poll_seconds)
        finally:
            self.release()

    # ---- one event -------------------------------------------------------------------------------
    def _one(self, conn: Conn, event: dict[str, Any], recovered: dict[int, str]) -> Outcome:
        outbox_id = int(event["id"])
        sha = recovered.get(outbox_id)
        if sha is not None:
            # Committed before a crash: record the SHA. The idea row is optional here, so a row deleted since
            # (erasure) cannot block the queue.
            log.warning("repo_writer.recovered_commit", outbox_id=outbox_id, commit_sha=sha)
            idea_id = (event["payload"] or {}).get("idea_id") or event["aggregate_id"]
            with conn.transaction():
                self._mark_committed(conn, outbox_id, sha)
                if event["event_type"] in DOC_EVENTS:  # documents keep where they went too (BLD-146)
                    table, key, rel = self._doc_target(event)
                    conn.execute(
                        f"UPDATE {table} SET repo_path = %s, repo_commit = %s WHERE id = %s",  # noqa: S608 (fixed names)
                        (rel, sha, key),
                    )
                if event["event_type"] in IDEA_EVENTS:
                    row = conn.execute(
                        "SELECT idea_id, submitted_at FROM ideas WHERE idea_id = %s", (idea_id,)
                    ).fetchone()
                    if row is not None and row["submitted_at"] is not None:
                        conn.execute(
                            "UPDATE ideas SET repo_path = %s, repo_commit = %s WHERE idea_id = %s",
                            (repo_path_for(row["idea_id"], row["submitted_at"]), sha, idea_id),
                        )
            return Outcome(outbox_id, sha, True)

        if (
            event["event_type"] in CLUSTER_EVENTS
            or event["event_type"] in (RUN_EVENT, DECISION_EVENT)
            or event["event_type"] in APPEAL_EVENTS
        ):
            return self._one_cluster(conn, event)
        if event["event_type"] == DEMO_REMOVED:
            message = self._remove_demo_file(event)
            sha = self.git.commit_all(message)
            with conn.transaction():
                self._mark_committed(conn, outbox_id, sha)
            log.info("repo_writer.committed", outbox_id=outbox_id, commit_sha=sha, event_type=DEMO_REMOVED)
            return Outcome(outbox_id, sha, True)
        if event["event_type"] in DOC_EVENTS:
            return self._one_doc(conn, event)
        if event["event_type"] not in IDEA_EVENTS:
            raise EventError("unknown_event")
        idea_row = self._load_idea(conn, event)
        rel = repo_path_for(idea_row["idea_id"], idea_row["submitted_at"])
        message = self._write_idea_files(event, idea_row, rel)
        sha = self.git.commit_all(message)
        self._commits_this_run += 1
        if self._crash_after is not None and self._commits_this_run >= self._crash_after:
            os._exit(137)  # simulate a crash after the commit, before the database knows
        with conn.transaction():
            self._mark_committed(conn, outbox_id, sha)
            conn.execute(
                "UPDATE ideas SET repo_path = %s, repo_commit = %s WHERE id = %s", (rel, sha, idea_row["id"])
            )
        log.info("repo_writer.committed", outbox_id=outbox_id, commit_sha=sha, event_type=event["event_type"])
        return Outcome(outbox_id, sha, False)

    # ---- clusters and clustering runs (§4.4 B) -----------------------------------------------------
    def _one_cluster(self, conn: Conn, event: dict[str, Any]) -> Outcome:
        outbox_id = int(event["id"])
        if event["event_type"] == RUN_EVENT:
            rel, message = self._write_run(conn, event)
        elif event["event_type"] == DECISION_EVENT:
            rel, message = self._write_decision(conn, event)
        elif event["event_type"] in APPEAL_EVENTS:
            rel, message = self._write_appeal(conn, event)
        else:
            rel, message = self._write_cluster(conn, event)
        sha = self.git.commit_all(message)
        with conn.transaction():
            self._mark_committed(conn, outbox_id, sha)
            if event["event_type"] in CLUSTER_EVENTS:
                conn.execute(
                    "UPDATE clusters SET repo_path = %s, repo_commit = %s WHERE id = %s",
                    (rel, sha, event["aggregate_id"]),
                )
            elif event["event_type"] == DECISION_EVENT:
                conn.execute(
                    "UPDATE decisions SET repo_path = %s, repo_commit = %s WHERE id = %s",
                    (rel, sha, event["aggregate_id"]),
                )
            elif event["event_type"] in APPEAL_EVENTS:
                conn.execute(
                    "UPDATE appeals SET repo_path = %s, repo_commit = %s WHERE id = %s",
                    (rel, sha, event["aggregate_id"]),
                )
        log.info("repo_writer.committed", outbox_id=outbox_id, commit_sha=sha, event_type=event["event_type"])
        return Outcome(outbox_id, sha, False)

    def _write_cluster(self, conn: Conn, event: dict[str, Any]) -> tuple[str, str]:
        cid = str(event["aggregate_id"])
        if not re.fullmatch(r"CL-[0-9]{4}", cid):
            raise EventError("cluster_id_invalid")
        cluster = conn.execute("SELECT * FROM clusters WHERE id = %s", (cid,)).fetchone()
        if cluster is None:
            raise EventError("cluster_not_found")
        members = [
            r["idea_id"]
            for r in conn.execute(
                "SELECT idea_id FROM ideas WHERE cluster_id = %s ORDER BY idea_id", (cid,)
            ).fetchall()
        ]
        summary = cluster["summary"] or {}
        refs: dict[str, str] = summary.get("refs") or {}
        owners = {
            r["idea_id"]: r["contributor_code"]
            for r in conn.execute(
                "SELECT idea_id, contributor_code FROM ideas WHERE idea_id = ANY(%s)", (list(refs.values()),)
            ).fetchall()
        }
        credits = {ref: owners[i] for ref, i in refs.items() if i in owners}
        rel = f"clusters/{cid}.md"
        path = self.repo / rel
        previous = path.read_text(encoding="utf-8") if path.exists() else None
        history, verified = existing_state(previous)
        payload: dict[str, Any] = event["payload"] or {}
        when = ist(event["created_at"]).strftime("%Y-%m-%d %H:%M")
        word = {"cluster.approved": "approved", "cluster.retired": "merged", "cluster.updated": "updated"}[
            event["event_type"]
        ]
        by = str(event["actor"])
        if not re.fullmatch(r"[A-Za-z0-9:@/._-]+", by):
            raise EventError("history_actor_invalid")
        history.append(HistoryRow(when, word, by, _safe_note(payload.get("note"))))
        reviewer = payload.get("verified_by")
        if reviewer:
            if not re.fullmatch(r"REV-[0-9]{4}", str(reviewer)):
                raise EventError("verified_by_invalid")
            verified.append(
                {"by": f"human:{reviewer}", "at": ist(event["created_at"]).isoformat(timespec="seconds")}
            )
        gates = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM cluster_gates WHERE cluster_id = %s ORDER BY array_position("
                "ARRAY['evidence','not_solved','not_planned','no_conflict'], gate)",
                (cid,),
            ).fetchall()
        ]
        impact = conn.execute("SELECT * FROM impact_estimates WHERE cluster_id = %s", (cid,)).fetchone()
        round_ = conn.execute(
            "SELECT * FROM scoring_rounds WHERE cluster_id = %s ORDER BY created_at DESC LIMIT 1", (cid,)
        ).fetchone()
        sections = cluster_sections(gates, dict(impact) if impact else None, dict(round_) if round_ else None)
        text = render_cluster(
            dict(cluster), members, credits, history=history, verified=verified, sections=sections
        )
        doc = parse(text)
        if [i for i in check_concept_meta(doc.meta or {}, rel) if i.level == "error"]:
            raise EventError("invalid_cluster_file")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._upsert_index_line(
            self.repo / "clusters" / "index.md",
            "# Clusters",
            cid,
            cluster_index_line(cid, str((doc.meta or {}).get("description", ""))),
        )
        message = f"[{cid}] {word}\n\nactor: {by}\nevent: {event['event_type']}\noutbox: {event['id']}\n"
        return rel, message

    def _write_decision(self, conn: Conn, event: dict[str, Any]) -> tuple[str, str]:
        did = str(event["aggregate_id"])
        if not re.fullmatch(r"DEC-[0-9]{4}-[0-9]{4}", did):
            raise EventError("decision_id_invalid")
        d = conn.execute("SELECT * FROM decisions WHERE id = %s", (did,)).fetchone()
        if d is None:
            raise EventError("decision_not_found")
        sheet = conn.execute(
            "SELECT * FROM decision_sheets WHERE presentation_id = %s", (d["presentation_id"],)
        ).fetchone()
        round_ = conn.execute(  # the presentation's round, or the round of a preliminary decision
            "SELECT r.* FROM scoring_rounds r WHERE r.id = coalesce(%s, "
            "(SELECT p.round_id FROM presentations p WHERE p.id = %s))",
            (d["round_id"], d["presentation_id"]),
        ).fetchone()
        appeal = conn.execute(
            "SELECT id, state, outcome FROM appeals WHERE decision_id = %s", (did,)
        ).fetchone()
        year = did.split("-")[1]
        rel = f"decisions/{year}/{did}.md"
        text = render_decision(
            dict(d),
            dict(sheet) if sheet else None,
            dict(round_) if round_ else None,
            dict(appeal) if appeal else None,
        )
        doc = parse(text)
        if [i for i in check_concept_meta(doc.meta or {}, rel) if i.level == "error"]:
            raise EventError("invalid_decision_file")
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._upsert_index_line(
            self.repo / "decisions" / year / "index.md",
            f"# Decisions, {year}",
            did,
            decision_index_line(did, str((doc.meta or {}).get("description", ""))),
        )
        self._upsert_index_line(
            self.repo / "decisions" / "index.md",
            "# Decisions",
            f"]({year}/)",
            f"* [{year}]({year}/) - decisions taken in {year}",
        )
        return (
            rel,
            f"[{did}] {d['outcome']}\n\nactor: {event['actor']}\nevent: {event['event_type']}\noutbox: {event['id']}\n",
        )

    def _write_appeal(self, conn: Conn, event: dict[str, Any]) -> tuple[str, str]:
        aid = str(event["aggregate_id"])
        if not re.fullmatch(r"APL-[0-9]{4}-[0-9]{4}", aid):
            raise EventError("appeal_id_invalid")
        a = conn.execute("SELECT * FROM appeals WHERE id = %s", (aid,)).fetchone()
        if a is None:
            raise EventError("appeal_not_found")
        d = conn.execute("SELECT body, outcome FROM decisions WHERE id = %s", (a["decision_id"],)).fetchone()
        year = aid.split("-")[1]
        rel = f"appeals/{year}/{aid}.md"
        text = render_appeal(dict(a), dict(d) if d else {})
        doc = parse(text)
        if [i for i in check_concept_meta(doc.meta or {}, rel) if i.level == "error"]:
            raise EventError("invalid_appeal_file")
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._upsert_index_line(
            self.repo / "appeals" / year / "index.md",
            f"# Appeals, {year}",
            aid,
            appeal_index_line(aid, str((doc.meta or {}).get("description", ""))),
        )
        stats = conn.execute(
            "SELECT d.body, count(*) AS filed, count(*) FILTER (WHERE a.state = 'open') AS open, "
            "count(*) FILTER (WHERE a.outcome = 'upheld') AS upheld, "
            "count(*) FILTER (WHERE a.outcome = 're_score') AS re_score, "
            "count(*) FILTER (WHERE a.outcome = 'overturned') AS overturned "
            "FROM appeals a JOIN decisions d ON d.id = a.decision_id GROUP BY d.body ORDER BY d.body"
        ).fetchall()
        years = sorted(
            {r["y"] for r in conn.execute("SELECT DISTINCT split_part(id, '-', 2) AS y FROM appeals")}
        )
        (self.repo / "appeals" / "index.md").write_text(
            appeals_index([dict(s) for s in stats], years), encoding="utf-8"
        )
        return (
            rel,
            f"[{aid}] {a['outcome'] or 'filed'}\n\nactor: {event['actor']}\nevent: {event['event_type']}\noutbox: {event['id']}\n",
        )

    def _write_run(self, conn: Conn, event: dict[str, Any]) -> tuple[str, str]:
        run_id = str(event["aggregate_id"])
        if not re.fullmatch(r"RUN-[0-9]{4}-W[0-9]{2}(-[0-9]+)?", run_id):
            raise EventError("run_id_invalid")
        run = conn.execute("SELECT * FROM cluster_runs WHERE id = %s", (run_id,)).fetchone()
        if run is None:
            raise EventError("run_not_found")
        decisions = [
            dict(r)
            for r in conn.execute(
                "SELECT p.kind, p.state, ri.final->>'reason_code' AS reject_code FROM cluster_proposals p "
                "LEFT JOIN review_items ri ON ri.id = p.review_item_id WHERE p.run_id = %s ORDER BY p.id",
                (run_id,),
            ).fetchall()
        ]
        rel = f"learning/cluster-runs/{run_id}.md"
        text = render_run(dict(run), decisions)
        doc = parse(text)
        if [i for i in check_concept_meta(doc.meta or {}, rel) if i.level == "error"]:
            raise EventError("invalid_run_file")
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._upsert_index_line(
            self.repo / "learning" / "cluster-runs" / "index.md",
            "# Clustering runs",
            run_id,
            run_index_line(run_id, str((doc.meta or {}).get("description", ""))),
        )
        self._upsert_index_line(
            self.repo / "learning" / "index.md",
            "# Learning",
            "](cluster-runs/)",
            "* [Clustering runs](cluster-runs/) - one file per weekly clustering run",
        )
        message = f"[{run_id}] recorded\n\nactor: {event['actor']}\nevent: {event['event_type']}\noutbox: {event['id']}\n"
        return rel, message

    # ---- documents from approved records (BLD-133, BLD-136) ------------------------------------------
    def _one_doc(self, conn: Conn, event: dict[str, Any]) -> Outcome:
        outbox_id = int(event["id"])
        if event["event_type"] == SOLUTION_EVENT:
            rel, message, table, key = self._write_solution(conn, event)
        else:
            rel, message, table, key = self._write_taxonomy(conn, event)
        sha = self.git.commit_all(message)
        with conn.transaction():
            self._mark_committed(conn, outbox_id, sha)
            conn.execute(
                f"UPDATE {table} SET repo_path = %s, repo_commit = %s WHERE id = %s",  # noqa: S608 (fixed names)
                (rel, sha, key),
            )
        log.info("repo_writer.committed", outbox_id=outbox_id, commit_sha=sha, event_type=event["event_type"])
        return Outcome(outbox_id, sha, False)

    @staticmethod
    def _doc_target(event: dict[str, Any]) -> tuple[str, Any, str]:
        payload, doc_id = event["payload"] or {}, str(event["aggregate_id"])
        if event["event_type"] == SOLUTION_EVENT:
            return "solution_writeups", payload.get("writeup_id"), f"solutions/{doc_id}.md"
        folder = "glossary" if event["event_type"] == GLOSSARY_EVENT else "areas"
        return "learning_proposals", payload.get("proposal_id"), f"taxonomy/{folder}/{doc_id}.md"

    def _checked_doc(self, text: str, rel: str) -> None:
        """The same check approve and publish ran (BLD-143). Failing here means the record changed since: it can
        never succeed as it stands, so it is dead-lettered rather than retried."""
        problem = doc_problem(text, rel, list(self.settings.kfin_domains))
        if problem:
            raise DeadLetter(problem)

    def _dead_letter(self, conn: Conn, event: dict[str, Any], code: str) -> None:
        outbox_id = int(event["id"])
        code = re.sub(r"[^A-Za-z0-9_.:-]", "_", code)[:120] or "error"
        with conn.transaction():
            conn.execute(
                "UPDATE outbox SET dead_lettered_at = now(), last_error = %s, attempts = attempts + 1 WHERE id = %s",
                (code, outbox_id),
            )
            conn.execute(
                "INSERT INTO audit_log (actor, action, entity, after) VALUES ('process:repo-writer', "
                "'alert.repo_writer_dead_letter', %s, %s)",
                (f"outbox:{outbox_id}", Jsonb({"event_type": event["event_type"], "error_code": code})),
            )
        self._retry_at.pop(outbox_id, None)
        log.error(
            "repo_writer.dead_lettered", outbox_id=outbox_id, event_type=event["event_type"], error_code=code
        )

    def _write_solution(self, conn: Conn, event: dict[str, Any]) -> tuple[str, str, str, int]:
        sol = str(event["aggregate_id"])
        if not re.fullmatch(r"SOL-[0-9]{4}", sol):
            raise DeadLetter("solution_id_invalid")
        w = conn.execute(
            "SELECT * FROM solution_writeups WHERE id = %s", ((event["payload"] or {}).get("writeup_id"),)
        ).fetchone()
        if w is None or w["state"] != "approved" or w["solution_id"] != sol:
            raise DeadLetter("writeup_not_approved")
        rel, text, title = solution_doc(conn, dict(w), sol, w["approved_at"])
        if (self.repo / rel).exists():
            raise DeadLetter("doc_exists")  # never overwrite a file the product team wrote by hand (BLD-146)
        self._checked_doc(text, rel)
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._upsert_index_line(
            self.repo / "solutions" / "index.md",
            '# Solutions — "Already running"',
            f"{sol}.md",
            doc_index_line(sol, title),
        )
        message = f"[{sol}] published\n\nactor: {event['actor']}\nevent: {event['event_type']}\noutbox: {event['id']}\n"
        return rel, message, "solution_writeups", int(w["id"])

    def _write_taxonomy(self, conn: Conn, event: dict[str, Any]) -> tuple[str, str, str, int]:
        from ones.text import unseal_json

        p = conn.execute(
            "SELECT * FROM learning_proposals WHERE id = %s", ((event["payload"] or {}).get("proposal_id"),)
        ).fetchone()
        if p is None or p["state"] != "approved" or not p["publish_encrypted"]:
            raise DeadLetter("proposal_not_approved")
        doc_id = str(event["aggregate_id"])
        wanted = ("glossary_term", r"GL-[a-z0-9-]{2,60}") if event["event_type"] == GLOSSARY_EVENT else (
            "area_tag", r"AREA-[a-z0-9-]{2,60}")  # fmt: skip
        if p["kind"] != wanted[0] or not re.fullmatch(wanted[1], doc_id):
            raise DeadLetter("doc_id_invalid")
        doc = unseal_json(p["publish_encrypted"], f"learning-publish:{p['id']}")
        rel, text, title, line = taxonomy_doc(str(p["kind"]), doc_id, doc, p["decided_at"])
        if (self.repo / rel).exists():
            raise DeadLetter("doc_exists")  # never overwrite a file the product team wrote by hand
        self._checked_doc(text, rel)
        (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / rel).write_text(text, encoding="utf-8")
        self._upsert_index_line(self.repo / Path(rel).parent / "index.md", title, f"{doc_id}.md", line)
        message = f"[{doc_id}] added\n\nactor: {event['actor']}\nevent: {event['event_type']}\noutbox: {event['id']}\n"
        return rel, message, "learning_proposals", int(p["id"])

    @staticmethod
    def _mark_committed(conn: Conn, outbox_id: int, sha: str) -> None:
        conn.execute(
            "UPDATE outbox SET committed_at = now(), commit_sha = %s, attempts = attempts + 1, last_error = NULL "
            "WHERE id = %s AND committed_at IS NULL",
            (sha, outbox_id),
        )

    def _load_idea(self, conn: Conn, event: dict[str, Any]) -> dict[str, Any]:
        idea_id = (event["payload"] or {}).get("idea_id") or event["aggregate_id"]
        row = conn.execute("SELECT * FROM ideas WHERE idea_id = %s", (idea_id,)).fetchone()
        if row is None:
            raise EventError("idea_not_found")
        if row["submitted_at"] is None or row["stage"] == "draft":
            raise EventError("idea_not_submitted")  # drafts never reach the repo
        if row["canvas"] is None:
            raise EventError("idea_has_no_card")
        co = conn.execute(
            "SELECT DISTINCT contributor_code FROM idea_links WHERE idea_id = %s AND link_type IN ('joiner','originator') "
            "AND contributor_code <> %s ORDER BY 1",
            (idea_id, row["contributor_code"]),
        ).fetchall()
        row["co_contributors"] = [r["contributor_code"] for r in co]
        return dict(row)

    def _write_idea_files(self, event: dict[str, Any], idea: dict[str, Any], rel: str) -> str:
        payload: dict[str, Any] = event["payload"] or {}
        path = self.repo / rel
        previous = path.read_text(encoding="utf-8") if path.exists() else None
        history, verified = existing_state(previous)
        when = ist(event["created_at"]).strftime("%Y-%m-%d %H:%M")
        rows = payload.get("history") or [{"event": event["event_type"].split(".", 1)[1], "note": ""}]
        for r in rows:
            by = str(r.get("by") or event["actor"])
            if not re.fullmatch(r"[A-Za-z0-9:@/._-]+", by):
                raise EventError("history_actor_invalid")
            word = str(r.get("event", ""))
            if not re.fullmatch(r"[a-z_]+", word):
                raise EventError("history_event_invalid")
            history.append(HistoryRow(when, word, by, _safe_note(r.get("note"))))
        reviewer = payload.get("verified_by")
        if reviewer:
            if not re.fullmatch(r"REV-[0-9]{4}", str(reviewer)):
                raise EventError("verified_by_invalid")
            verified.append(
                {"by": f"human:{reviewer}", "at": ist(event["created_at"]).isoformat(timespec="seconds")}
            )
        canvas = idea.get("canvas") or {}
        assisted = any(v in ("suggested", "accepted") for v in (canvas.get("provenance") or {}).values())
        generated_by = (
            str(canvas.get("generated_by") or "canvas-assist/unknown")
            if assisted
            else f"human:{idea['contributor_code']}"
        )

        text = render_idea(idea, history=history, verified=verified, generated_by=generated_by)
        doc = parse(text)
        problems = [i for i in check_concept_meta(doc.meta or {}, rel) if i.level == "error"]
        if problems:
            log.error(
                "repo_writer.invalid_file", outbox_id=event["id"], error_codes=[i.code for i in problems]
            )
            raise EventError("invalid_idea_file")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._update_indexes(rel, idea["idea_id"], str((doc.meta or {}).get("description", "")))

        stage_word = rows[-1].get("event") or event["event_type"].split(".", 1)[1]
        note = rows[-1].get("note") or ""
        subject = f"[{idea['idea_id']}] {stage_word}" + (f" — {note}" if note else "")
        return f"{subject}\n\nactor: {event['actor']}\nevent: {event['event_type']}\noutbox: {event['id']}\n"

    def _remove_demo_file(self, event: dict[str, Any]) -> str:
        payload: dict[str, Any] = event["payload"] or {}
        rel = str(payload.get("path") or "")
        m = DEMO_PATH.fullmatch(rel)
        if (
            self.settings.app_env != "dev"
            or payload.get("demo") is not True
            or not m
            or m.group(1) != event["aggregate_id"]
        ):
            raise EventError("demo_remove_refused")
        path = self.repo / rel
        if path.exists():
            path.unlink()
        index = path.parent / "index.md"
        if index.exists():
            kept = [ln for ln in index.read_text(encoding="utf-8").split("\n") if f"[{m.group(1)}]" not in ln]
            index.write_text("\n".join(kept), encoding="utf-8")
        return f"[{m.group(1)}] demo_removed\n\nactor: {event['actor']}\nevent: {DEMO_REMOVED}\noutbox: {event['id']}\n"

    def _update_indexes(self, rel: str, idea_id: str, description: str) -> None:
        """Keep ideas/index.md → YYYY/index.md → MM/index.md listing every file (§2.1)."""
        _, year, month, _ = rel.split("/")
        month_name = datetime(int(year), int(month), 1, tzinfo=UTC).strftime("%B %Y")
        self._upsert_index_line(
            self.repo / "ideas" / year / month / "index.md",
            f"# Ideas, {month_name}",
            idea_id,
            index_line(idea_id, description),
        )
        self._upsert_index_line(
            self.repo / "ideas" / year / "index.md",
            f"# Ideas, {year}",
            f"]({month}/)",
            f"* [{month_name}]({month}/) - ideas submitted in {month_name}",
        )
        self._upsert_index_line(
            self.repo / "ideas" / "index.md",
            None,
            f"]({year}/)",
            f"* [{year}]({year}/) - ideas submitted in {year}",
        )

    @staticmethod
    def _upsert_index_line(path: Path, title: str | None, key: str, line: str) -> None:
        if path.exists():
            lines = path.read_text(encoding="utf-8").rstrip("\n").split("\n")
        else:
            lines = [title or "# Ideas", ""]
        lines = [ln for ln in lines if ln.strip() != "No entries yet."]
        match_key = f"[{key}]" if not key.startswith("]") else key
        for i, ln in enumerate(lines):
            if match_key in ln:
                lines[i] = line
                break
        else:
            lines.append(line)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- failures and push -----------------------------------------------------------------------
    def _record_failure(self, conn: Conn, event: dict[str, Any], code: str) -> None:
        """Record the code, back off before retrying this event, and alert once it looks stuck. Later events
        wait behind it: the repo is written in order (BLD-031)."""
        outbox_id = int(event["id"])
        attempts = int(event["attempts"]) + 1
        code = re.sub(r"[^A-Za-z0-9_.:-]", "_", code)[:120] or "error"
        with conn.transaction():
            conn.execute(
                "UPDATE outbox SET attempts = %s, last_error = %s WHERE id = %s", (attempts, code, outbox_id)
            )
        delay = RETRY_BACKOFF_S[min(attempts - 1, len(RETRY_BACKOFF_S) - 1)]
        self._retry_at[outbox_id] = time.monotonic() + delay
        if attempts >= STUCK_AFTER_ATTEMPTS:
            log.error("repo_writer.event_stuck", outbox_id=outbox_id, error_code=code, attempts=attempts)
        else:
            log.error("repo_writer.event_failed", outbox_id=outbox_id, error_code=code, retry_in_s=delay)

    def _push(self) -> None:
        """Push without ever blocking the commit loop (§2.7): one attempt per loop when due, backing off
        2, 5, 15, then 60 seconds between attempts; an alert once pushes have failed for 15 minutes."""
        if not self.settings.company_repo_remote or time.monotonic() < self._next_push_at:
            return
        try:
            self.git.push()
        except GitError:
            self._push_failures += 1
            if self._push_failing_since is None:
                self._push_failing_since = time.monotonic()
            delay = PUSH_BACKOFF_S[min(self._push_failures - 1, len(PUSH_BACKOFF_S) - 1)]
            self._next_push_at = time.monotonic() + delay
            failing_for = time.monotonic() - self._push_failing_since
            if failing_for >= PUSH_ALERT_AFTER_S:
                log.error("repo_writer.push_failing", failing_for_s=int(failing_for), retry_in_s=delay)
            else:
                log.warning("repo_writer.push_failed", retry_in_s=delay)
            return
        if self._push_failures:
            log.info("repo_writer.push_recovered", failed_attempts=self._push_failures)
        self._push_failures, self._push_failing_since, self._next_push_at = 0, None, 0.0


def commits_for(repo: Path) -> list[tuple[str, str]]:
    """(sha, subject) for every commit, oldest first. Used by tests and `reconcile`."""
    git = Git(repo)
    out = git.run("log", "--reverse", "--format=%H%x09%s")
    return [tuple(line.split("\t", 1)) for line in out.split("\n") if "\t" in line]  # type: ignore[misc]
