"""Re-index what changed between the last indexed commit and HEAD (§2.6–2.7).

Reads file content from the commit, never the working tree, so a write in progress cannot be half-indexed.
Ideas are one chunk (title, what it is, who it touches); other concept files are split by `##` section.
Deleting a file removes its chunks, links, terms and read-model row.
"""

from __future__ import annotations

import posixpath
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.config import Settings, get_settings
from core.db import Conn, connect, vector_literal
from core.logging import get_logger
from embeddings import embed
from okf.frontmatter import FrontmatterError, parse
from repo_writer.git import Git

log = get_logger("indexer")

ID_REF = re.compile(
    r"^(?:IDEA-\d{4}-\d{6}|CL-\d{4}|TH-\d{3}|DEC-\d{4}-\d{4}|HO-\d{4}-\d{4}|APL-\d{4}-\d{4}|SOL-\d{4}|WG-\d{4}"
    r"|AREA-[a-z0-9-]+|LOB-[a-z0-9-]+|ROLE-[a-z0-9-]+|GL-[a-z0-9-]+|CLI-[a-z0-9-]+)$"
)
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
IDEA_CARD_SECTIONS = ("What it is", "Who it touches")
RESERVED = {"index.md", "log.md"}


@dataclass
class IndexResult:
    from_commit: str | None
    to_commit: str | None
    upserted: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    rebuilt: bool = False


def _text(value: Any) -> str | None:
    """A scalar from frontmatter as text; anything else (lists, mappings) as None."""
    return str(value) if isinstance(value, str | int | float) and not isinstance(value, bool) else None


def _texts(value: Any) -> list[str]:
    """A list of scalars from frontmatter as text; a lone scalar becomes a one-item list."""
    items = value if isinstance(value, list) else ([value] if value is not None else [])
    return [t for t in (_text(v) for v in items) if t is not None]


def trust_tier(meta: dict[str, Any]) -> str:
    """OKF SPEC §5.3: none ⇒ unverified; non-human verifiers only ⇒ machine; any human: ⇒ human."""
    verified = meta.get("verified")
    if not verified:
        return "unverified"
    entries = verified if isinstance(verified, list) else [verified]
    bys = [str(e.get("by", "")) for e in entries if isinstance(e, dict)]
    if any(b.startswith("human:") for b in bys):
        return "human"
    return "machine" if bys else "unverified"


def split_sections(body: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current, buf = "body", list[str]()
    for line in body.split("\n"):
        if line.startswith("## "):
            if "".join(buf).strip():
                sections.append((current, "\n".join(buf).strip()))
            current, buf = line[3:].strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        sections.append((current, "\n".join(buf).strip()))
    return sections


CARD_TYPES = frozenset({"idea", "cluster", "solution", "decision"})


def card_summary(file_type: str, meta: dict[str, Any], kfin: dict[str, Any]) -> str | None:
    """The one line other employees may see on a match card (BLD-079): an idea's `neutral_summary`, or the
    description of a cluster, solution or decision. Ideas without a neutral summary get none."""
    if file_type not in CARD_TYPES:
        return None
    if file_type == "idea":
        return _text(kfin.get("neutral_summary"))
    return _text(meta.get("description"))


def build_chunks(meta: dict[str, Any], body: str) -> list[tuple[str, str]]:
    title = str(meta.get("title") or "")
    sections = split_sections(body)
    if meta.get("type") == "idea":
        parts = [text for name, text in sections if name in IDEA_CARD_SECTIONS]
        return [("card", "\n\n".join([title, *parts]).strip())]
    chunks = [(name, f"{title}\n\n{text}".strip()) for name, text in sections if name != "History"]
    if not chunks:
        chunks = [("body", "\n".join(filter(None, [title, str(meta.get("description") or "")])))]
    return chunks


def frontmatter_refs(kfin: dict[str, Any], own_id: str | None) -> set[str]:
    refs: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, str) and ID_REF.match(value) and value != own_id:
            refs.add(value)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)

    walk({k: v for k, v in kfin.items() if k != "id"})
    return refs


def markdown_targets(rel: str, body: str) -> set[str]:
    out: set[str] = set()
    base = posixpath.dirname(rel)
    for target in MD_LINK.findall(body):
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue
        target = target.split("#", 1)[0]
        path = target[1:] if target.startswith("/") else posixpath.join(base, target)
        path = posixpath.normpath(path)
        if path.endswith("/") or not path.endswith(".md"):
            path = posixpath.join(path, "index.md")
        out.add(path)
    return out


class Indexer:
    def __init__(self, settings: Settings | None = None, database_url: str | None = None) -> None:
        self.settings = settings or get_settings()
        self.database_url = database_url or self.settings.database_url
        self.git = Git(Path(self.settings.company_repo_path), self.settings.repo_writer_author)

    def run_once(self, *, rebuild: bool = False) -> IndexResult:
        head = self.git.head() if self.git.is_repo() else None
        with connect(self.database_url, autocommit=True) as conn:
            state = conn.execute("SELECT last_commit FROM index_state WHERE id = 1").fetchone()
            last = state["last_commit"] if state else None
            result = IndexResult(from_commit=last, to_commit=head)
            if head is None or (head == last and not rebuild):
                return result
            full = rebuild or last is None or not self.git.has_commit(last)
            if full:
                result.rebuilt = True
                paths = [(p, "A") for p in self.git.ls_files(head)]
            else:
                assert last is not None
                paths = [(c.path, c.status) for c in self.git.diff(last, head)]
            with conn.transaction():
                if full:
                    for table in ("chunks", "links", "terms", "repo_files"):
                        conn.execute(f"DELETE FROM {table}")  # noqa: S608 - fixed table names
                for rel, status in paths:
                    if not rel.endswith(".md") or posixpath.basename(rel) in RESERVED:
                        continue
                    try:
                        # One savepoint per file: an odd file is skipped and logged, never blocks the rest.
                        with conn.transaction():
                            if status == "D":
                                self._delete(conn, rel)
                                result.deleted.append(rel)
                            elif self._upsert(conn, rel, head):
                                result.upserted.append(rel)
                    except Exception as exc:
                        result.failed.append(rel)
                        log.error("indexer.file_failed", repo_path=rel, error_type=type(exc).__name__)
                self._resolve_links(conn)
                conn.execute(
                    "UPDATE index_state SET last_commit = %s, updated_at = now() WHERE id = 1", (head,)
                )
        log.info(
            "indexer.indexed",
            commit_sha=head,
            upserted_count=len(result.upserted),
            deleted_count=len(result.deleted),
            failed_count=len(result.failed),
            rebuilt=result.rebuilt,
        )
        return result

    def run_forever(self, stop: Any = None) -> None:
        log.info("indexer.started")
        while stop is None or not stop.is_set():
            try:
                self.run_once()
            except Exception:
                log.exception("indexer.failed")
            time.sleep(self.settings.index_poll_seconds)

    # ---- per file ----------------------------------------------------------------------------------
    def _delete(self, conn: Conn, rel: str) -> None:
        # Links that had resolved to this file go back to their `id:<ID>` form, so they re-resolve if the
        # concept returns under another path and never point at a file that no longer exists.
        conn.execute(
            "INSERT INTO links (from_path, to_path, link_type) "
            "SELECT l.from_path, 'id:' || f.kfin_id, l.link_type FROM links l JOIN repo_files f "
            "ON f.repo_path = l.to_path WHERE l.to_path = %s AND l.link_type = 'frontmatter' "
            "AND f.kfin_id IS NOT NULL ON CONFLICT DO NOTHING",
            (rel,),
        )
        conn.execute("DELETE FROM links WHERE to_path = %s AND link_type = 'frontmatter'", (rel,))
        conn.execute("DELETE FROM chunks WHERE repo_path = %s", (rel,))
        conn.execute("DELETE FROM links WHERE from_path = %s", (rel,))
        conn.execute("DELETE FROM terms WHERE repo_path = %s", (rel,))
        conn.execute("DELETE FROM repo_files WHERE repo_path = %s", (rel,))

    def _upsert(self, conn: Conn, rel: str, commit: str) -> bool:
        try:
            doc = parse(self.git.show(commit, rel))
        except (FrontmatterError, UnicodeDecodeError):
            log.warning("indexer.unparseable", repo_path=rel)
            return False
        meta = doc.meta or {}
        file_type = str(meta.get("type") or "")
        if not file_type:
            return False
        kfin: dict[str, Any] = meta.get("kfin") if isinstance(meta.get("kfin"), dict) else {}  # type: ignore[assignment]
        own_id = _text(kfin.get("id"))
        trust = trust_tier(meta)
        visibility = kfin.get("visibility") if kfin.get("visibility") in ("org", "committee") else "org"
        stage = _text(kfin.get("stage"))
        self._delete(conn, rel)
        conn.execute(
            "INSERT INTO repo_files (repo_path, kfin_id, file_type, trust, stage, visibility, commit_sha, summary, "
            "area_ids, lobs) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                rel, own_id, file_type, trust, stage, visibility, commit, card_summary(file_type, meta, kfin),
                _texts(kfin.get("areas")), _texts(kfin.get("lobs")),
            ),
        )  # fmt: skip
        chunks = build_chunks(meta, doc.body)
        vectors = embed([text for _, text in chunks])
        for ordinal, ((section, text), vec) in enumerate(zip(chunks, vectors, strict=True)):
            conn.execute(
                "INSERT INTO chunks (repo_path, file_type, section, ordinal, text, embedding, trust, stage, lobs, "
                "category, area_ids, visibility, commit_sha) "
                "VALUES (%s, %s, %s, %s, %s, %s::vector, %s, %s, %s, %s, %s, %s, %s)",
                (
                    rel, file_type, section, ordinal, text, vector_literal(vec), trust, stage,
                    _texts(kfin.get("lobs")), _text(kfin.get("category")), _texts(kfin.get("areas")),
                    visibility, commit,
                ),
            )  # fmt: skip
        for target in markdown_targets(rel, doc.body):
            conn.execute(
                "INSERT INTO links (from_path, to_path, link_type) VALUES (%s, %s, 'markdown') ON CONFLICT DO NOTHING",
                (rel, target),
            )
        for ref in frontmatter_refs(kfin, own_id):
            conn.execute(
                "INSERT INTO links (from_path, to_path, link_type) VALUES (%s, %s, 'frontmatter') ON CONFLICT DO NOTHING",
                (rel, f"id:{ref}"),
            )
        if file_type == "glossary-term" and own_id:
            term = str(kfin.get("term") or meta.get("title") or own_id)
            for alias in dict.fromkeys([term, *_texts(kfin.get("aliases"))]):
                conn.execute(
                    "INSERT INTO terms (glossary_id, term, alias, repo_path) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (glossary_id, alias) DO NOTHING",
                    (own_id, term, alias, rel),
                )
        return True

    @staticmethod
    def _resolve_links(conn: Conn) -> None:
        """Turn `id:<ID>` link targets into repo paths once the target file exists."""
        conn.execute(
            "INSERT INTO links (from_path, to_path, link_type) "
            "SELECT l.from_path, f.repo_path, l.link_type FROM links l "
            "JOIN repo_files f ON l.to_path = 'id:' || f.kfin_id ON CONFLICT DO NOTHING"
        )
        conn.execute("DELETE FROM links l USING repo_files f WHERE l.to_path = 'id:' || f.kfin_id")
