"""Write synthetic concept files into a temporary company repo and index them (B5 retrieval tests)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from index.indexer import Indexer
from okf.frontmatter import dump
from repo_writer.git import Git
from tests import helpers

AUTHOR = "Ideas Platform Bot <ideas-bot@localhost>"
HUMAN = [{"by": "human:REV-0001", "at": "2026-11-09T10:00:00+05:30"}]


def write(repo: Path, rel: str, meta: dict[str, Any], body: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(meta, body), encoding="utf-8")


def idea(
    repo: Path, n: int, text: str, summary: str, *, systems: list[str] | None = None, visibility: str = "org",
    areas: list[str] | None = None, stage: str = "scanned", human: bool = False,
) -> str:  # fmt: skip
    idea_id = f"IDEA-2026-{n:06d}"
    meta: dict[str, Any] = {
        "type": "idea", "title": text[:60], "description": summary, "tags": ["idea"], "status": "draft",
        "generated": {"by": "process:test", "at": "2026-11-09T10:00:00+05:30"},
    }  # fmt: skip
    if human:
        meta["verified"] = HUMAN
    meta["kfin"] = {
        "id": idea_id, "stage": stage, "kind": "problem", "category": "cost_saving", "contributor": "CTR-0a1b2c",
        "visibility": visibility, "areas": areas or ["AREA-process"], "lobs": ["LOB-mf"], "systems": systems or [],
        "neutral_summary": summary,
    }  # fmt: skip
    write(
        repo,
        f"ideas/2026/11/{idea_id}.md",
        meta,
        f"## What it is\n\n{text}\n\n## Who it touches\n\nOps teams.\n",
    )
    return idea_id


def concept(
    repo: Path, kind: str, n: int, text: str, summary: str, *, systems: list[str] | None = None
) -> str:
    prefix = {"solution": "SOL", "decision": "DEC", "cluster": "CL"}[kind]
    kid = f"{prefix}-{n:04d}"
    folder = {"solution": "solutions", "decision": "decisions", "cluster": "clusters"}[kind]
    meta: dict[str, Any] = {
        "type": kind, "title": text[:60], "description": summary, "tags": [kind], "status": "stable",
        "generated": {"by": "process:test", "at": "2026-11-09T10:00:00+05:30"}, "verified": HUMAN,
        "kfin": {"id": kid, "stage": "shipped" if kind == "solution" else "declined", "lobs": ["LOB-mf"],
                 "areas": ["AREA-process"], "systems": systems or [], "visibility": "org"},
    }  # fmt: skip
    write(repo, f"{folder}/{kid}.md", meta, f"## Summary\n\n{text}\n")
    return kid


def commit_and_index(repo: Path, database: str) -> None:
    Git(repo, AUTHOR).commit_all("Test fixtures\n\nactor: system\nevent: test.fixtures\n")
    Indexer(helpers.settings_for(repo, database, embeddings_mode="hash")).run_once()
