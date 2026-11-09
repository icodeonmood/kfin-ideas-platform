"""Nightly `reconcile` (§3.5, §2 "The read model and repo disagree"): compare the company repo at its head with
the read model, fix the index, and log the drift.

Fixed here (the index is derived from the repo, so the repo wins):
- files at the head that are missing from the index, or indexed with a different stage, visibility or ID;
- index rows for files that are no longer in the repo;
- an index still behind the repo's head after 15 seconds (the live indexer catches up within seconds) is reported.

Reported, not fixed (the database is the source for ideas; the repo writer rewrites files from it):
- ideas whose file is missing from the repo;
- ideas whose file shows a different visibility than the database (logged as an error: the index would show a
  committee-only idea as open, or the reverse), once the writer has nothing pending for them.

Counted apart, not as drift: ideas whose file shows an older stage. Some steps (a question asked, an answer given)
change the stage without a repo event, so the file catches up at the next event.

Logs carry counts and repo paths (IDs only), never text.
"""

from __future__ import annotations

import posixpath
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.config import Settings, get_settings
from core.db import connect
from core.logging import get_logger
from index.indexer import RESERVED, Indexer
from okf.frontmatter import FrontmatterError, parse
from repo_writer.git import Git

log = get_logger("reconcile")


@dataclass
class Drift:
    missing_in_index: list[str] = field(default_factory=list)
    stale_in_index: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)
    index_behind: bool = False
    idea_files_missing: list[str] = field(default_factory=list)
    idea_visibility_mismatch: list[str] = field(default_factory=list)
    idea_stage_mismatch: list[str] = field(default_factory=list)
    fixed: int = 0
    unfixable: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "missing_in_index": len(self.missing_in_index),
            "stale_in_index": len(self.stale_in_index),
            "mismatched": len(self.mismatched),
            "index_behind": int(self.index_behind),
            "idea_files_missing": len(self.idea_files_missing),
            "idea_visibility_mismatch": len(self.idea_visibility_mismatch),
        }

    @property
    def total(self) -> int:
        return sum(self.counts().values())


def _expected(git: Git, head: str) -> dict[str, tuple[str | None, str | None, str]]:
    """path -> (id, stage, visibility) for every file at the head that the indexer would index."""
    out: dict[str, tuple[str | None, str | None, str]] = {}
    for rel in git.ls_files(head):
        if not rel.endswith(".md") or posixpath.basename(rel) in RESERVED:
            continue
        try:
            meta = parse(git.show(head, rel)).meta or {}
        except (FrontmatterError, UnicodeDecodeError):
            continue
        if not meta.get("type"):
            continue
        kfin: dict[str, Any] = meta.get("kfin") if isinstance(meta.get("kfin"), dict) else {}  # type: ignore[assignment]
        vis = "org" if kfin.get("visibility", "org") == "org" else "committee"
        kid = kfin.get("id")
        stage = kfin.get("stage")
        out[rel] = (str(kid) if kid else None, str(stage) if stage else None, vis)
    return out


def _wait_for_index(conn: Any, head: str, wait_s: float) -> str | None:
    """The commit the index reflects, after giving the live indexer up to `wait_s` to reach the head."""
    deadline = time.monotonic() + wait_s
    while True:
        row = conn.execute("SELECT last_commit FROM index_state WHERE id = 1").fetchone()
        last = row["last_commit"] if row else None
        if last == head or time.monotonic() >= deadline:
            return last
        time.sleep(1)


def run(settings: Settings | None = None, *, fix: bool = True, wait_s: float = 15.0) -> Drift:
    """Compare the index with the repo at the commit the index says it reflects (`index_state.last_commit`), so
    the live indexer moving on meanwhile is never mistaken for drift; fixes apply only if that commit is still
    the index's under a row lock, one savepoint per file (B8 review)."""
    s = settings or get_settings()
    git = Git(Path(s.company_repo_path), s.repo_writer_author)
    drift = Drift()
    head = git.head() if git.is_repo() else None
    if head is None:
        log.error("reconcile.no_repo")
        return drift
    indexer = Indexer(s)
    with connect(s.database_url, autocommit=True) as conn:
        last = _wait_for_index(conn, head, wait_s)
        drift.index_behind = last != head
        if last is None or not git.has_commit(last):
            log.warning("reconcile.index_unknown_commit")  # the indexer rebuilds in full on its own
            drift.index_behind = True
            return _finish(drift, 0)
        expected = _expected(git, last)
        indexed = {
            r["repo_path"]: (r["kfin_id"], r["stage"], r["visibility"])
            for r in conn.execute("SELECT repo_path, kfin_id, stage, visibility FROM repo_files").fetchall()
        }
        drift.missing_in_index = sorted(set(expected) - set(indexed))
        drift.stale_in_index = sorted(set(indexed) - set(expected))
        drift.mismatched = sorted(p for p in set(expected) & set(indexed) if expected[p] != indexed[p])

        if not drift.index_behind:  # idea files are checked at the head only; behind, the writer may be ahead
            pending = {
                r["aggregate_id"]
                for r in conn.execute(
                    "SELECT DISTINCT aggregate_id FROM outbox WHERE committed_at IS NULL AND dead_lettered_at IS NULL "
                    "AND aggregate_id LIKE 'IDEA-%%'"
                ).fetchall()
            }
            for idea in conn.execute(
                "SELECT idea_id, stage, visibility, repo_path FROM ideas WHERE repo_path IS NOT NULL"
            ).fetchall():
                if idea["idea_id"] in pending:
                    continue  # the writer has not caught up yet: not drift
                file = expected.get(idea["repo_path"])
                if file is None:
                    drift.idea_files_missing.append(idea["idea_id"])
                    continue
                if file[2] != idea["visibility"]:
                    drift.idea_visibility_mismatch.append(idea["idea_id"])
                if file[1] != idea["stage"]:
                    drift.idea_stage_mismatch.append(idea["idea_id"])

        if fix and (drift.missing_in_index or drift.stale_in_index or drift.mismatched):
            with conn.transaction():
                locked = conn.execute(
                    "SELECT last_commit FROM index_state WHERE id = 1 FOR UPDATE"
                ).fetchone()
                if (locked["last_commit"] if locked else None) != last:
                    log.warning("reconcile.raced")  # the indexer moved on: tomorrow's run looks again
                else:
                    for rel in drift.stale_in_index + drift.missing_in_index + drift.mismatched:
                        try:
                            with (
                                conn.transaction()
                            ):  # one savepoint per file: an odd file never blocks the rest
                                if rel in drift.stale_in_index:
                                    indexer._delete(conn, rel)
                                    drift.fixed += 1
                                elif indexer._upsert(conn, rel, last):
                                    drift.fixed += 1
                        except Exception as exc:
                            drift.unfixable.append(rel)
                            log.error("reconcile.file_failed", repo_path=rel, error_type=type(exc).__name__)
                    Indexer._resolve_links(conn)
    return _finish(drift, len(expected))


def _finish(drift: Drift, file_count: int) -> Drift:
    counts = drift.counts()
    if drift.idea_visibility_mismatch:
        log.error("reconcile.visibility_drift", idea_ids=drift.idea_visibility_mismatch[:50])
    if drift.total:
        log.warning(
            "reconcile.drift", fixed_count=drift.fixed, **{f"{k}_count": v for k, v in counts.items()}
        )
    else:
        log.info("reconcile.clean", file_count=file_count)
    return drift
