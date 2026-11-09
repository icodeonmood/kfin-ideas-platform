"""Learning proposals that wait for the product team (§5.2, §5.3). Nothing changes the taxonomy or the glossary
until a person approves it; writing an approved change into the company repo (with a drafted name, definition or
aliases) is coming soon, and until then the product team adds it by hand.

- **Glossary (weekly):** all-caps tokens of 2 to 8 letters and CamelCase words found in at least 3 distinct ideas'
  checked text (the neutral summary and the canvas's tagged fields, never raw text), that are not in the glossary.
  A candidate that the personal-data patterns or the colleague and client detector flag is dropped.
- **Area tags (monthly):** ideas from the last 90 days whose area fit was poor (confidence under 0.6, the desk
  changed the tags, or `AREA-other`). With at least 15, they are grouped by average linkage (distance 0.30) on
  their card vectors; each group of 3 or more becomes a proposal with its size, the ideas' IDs and current tags.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from psycopg.types.json import Jsonb

from core.config import get_settings
from core.db import Conn
from ones.text import OnesRefused, checked, seal, seal_json, unseal
from pii.detect import detect, directory
from pii.patterns import scan
from pii.tagger import TAG_RE
from repo_writer.render_docs import doc_problem, taxonomy_doc
from scan.inputs import _taxonomy

TERM_RE = re.compile(r"(?<![A-Za-z0-9])(?:[A-Z]{2,8}|[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+)(?![A-Za-z0-9])")
MIN_IDEAS = 3
AREA_POOL_MIN = 15
AREA_DISTANCE = 0.30
AREA_GROUP_MIN = 3
COMMON = {"OK", "AM", "PM", "US", "UK", "IT", "HR", "CEO", "FAQ", "ID", "NO", "TO", "IN", "ON", "AND", "THE"}


def candidate_terms(texts_by_idea: dict[str, list[str]], known: set[str]) -> dict[str, set[str]]:
    """Terms found in at least 3 distinct ideas and not already known. Pure, for tests."""
    seen: dict[str, set[str]] = {}
    for idea_id, texts in texts_by_idea.items():
        for text in texts:
            clean = TAG_RE.sub(" ", text or "")
            for m in TERM_RE.finditer(clean):
                term = m.group(0)
                if term.upper() in COMMON or term.lower() in known:
                    continue
                seen.setdefault(term, set()).add(idea_id)
    return {t: ids for t, ids in seen.items() if len(ids) >= MIN_IDEAS}


def _known_terms(conn: Conn) -> set[str]:
    tax = _taxonomy(get_settings().company_repo_path)
    known = {str(t).lower() for g in tax["glossary"] for t in [g["name"], *g["aliases"]] if t}
    known |= {str(r["alias"]).lower() for r in conn.execute("SELECT alias FROM terms").fetchall()}
    return known


def _key(kind: str, value: str) -> str:
    return f"{kind}:{hashlib.sha256(value.lower().encode()).hexdigest()[:16]}"


def glossary(conn: Conn, now: dt.datetime, period: str) -> int:
    rows = conn.execute(
        "SELECT idea_id, canvas FROM ideas WHERE idea_id IS NOT NULL AND submitted_at >= %s",
        (now - dt.timedelta(days=90),),
    ).fetchall()
    texts: dict[str, list[str]] = {}
    for r in rows:
        card = r["canvas"] or {}
        texts[r["idea_id"]] = [str(card.get(k) or "") for k in ("neutral_summary", "one_line", "details")]
    found = candidate_terms(texts, _known_terms(conn))
    people = directory(conn)
    added = 0
    with conn.transaction():
        for term, ids in sorted(found.items()):
            if scan(term, kfin_domains=[]) or detect(term, people):
                continue  # never propose something that reads as personal data or a name
            key = _key("term", term)
            row = conn.execute(
                "INSERT INTO learning_proposals (kind, period, payload) VALUES ('glossary_term', %s, %s) "
                "ON CONFLICT DO NOTHING RETURNING id",
                (period, Jsonb({"key": key, "ideas": len(ids), "idea_ids": sorted(ids)[:20]})),
            ).fetchone()
            if row is None:
                continue
            conn.execute(
                "UPDATE learning_proposals SET text_encrypted = %s WHERE id = %s",
                (seal(term, f"learning:{row['id']}"), row["id"]),
            )
            added += 1
    return added


def area_tags(conn: Conn, now: dt.datetime, period: str) -> int:
    from cluster.linkage import average_linkage

    rows = conn.execute(
        """
        SELECT i.idea_id, i.area_ids, i.lobs, c.embedding::text AS embedding
        FROM ideas i
        LEFT JOIN LATERAL (SELECT embedding FROM chunks ch WHERE ch.repo_path = i.repo_path AND ch.file_type = 'idea'
                           ORDER BY ch.ordinal LIMIT 1) c ON true
        WHERE i.idea_id IS NOT NULL AND i.submitted_at >= %s AND i.stage <> 'draft' AND (
          'AREA-other' = ANY(i.area_ids)
          OR EXISTS (SELECT 1 FROM review_items r WHERE r.ref_id = i.idea_id AND r.item_type = 'idea'
                     AND (r.confidence ->> 'system.areas')::numeric < 0.6)
          OR EXISTS (SELECT 1 FROM review_items r JOIN corrections k ON k.review_item_id = r.id
                     WHERE r.ref_id = i.idea_id AND k.field = 'system.areas'))
        """,
        (now - dt.timedelta(days=90),),
    ).fetchall()
    pool = [r for r in rows if r["embedding"]]
    if len(pool) < AREA_POOL_MIN:
        return 0
    vectors = np.asarray([json.loads(r["embedding"]) for r in pool], dtype=np.float64)
    groups = [g for g in average_linkage(vectors, AREA_DISTANCE) if len(g) >= AREA_GROUP_MIN]
    added = 0
    with conn.transaction():
        for g in groups:
            ids = sorted(pool[i]["idea_id"] for i in g)
            tags = Counter(a for i in g for a in (pool[i]["area_ids"] or []))
            lobs = Counter(x for i in g for x in (pool[i]["lobs"] or []))
            payload = {
                "key": _key("area", period + ",".join(ids)), "ideas": len(ids), "idea_ids": ids[:30],
                "current_tags": dict(tags.most_common(5)), "lobs": dict(lobs.most_common(5)),
            }  # fmt: skip
            row = conn.execute(
                "INSERT INTO learning_proposals (kind, period, payload) VALUES ('area_tag', %s, %s) "
                "ON CONFLICT DO NOTHING RETURNING id",
                (period, Jsonb(payload)),
            ).fetchone()
            added += row is not None
    return added


def decide(
    conn: Conn, actor: str, proposal_id: Any, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    """The product team (an admin) approves or declines a proposal. Recorded and audited; nothing else moves."""
    from ones.service import roles

    now = now or dt.datetime.now(dt.UTC)
    try:
        pid = int(proposal_id)
    except (TypeError, ValueError):
        raise OnesRefused(404, "not_found") from None
    verdict = body.get("verdict")
    if verdict not in ("approve", "decline"):
        raise OnesRefused(400, "verdict_required")
    if "admin" not in roles(conn, actor):
        raise OnesRefused(403, "forbidden")
    with conn.transaction():
        p = conn.execute("SELECT * FROM learning_proposals WHERE id = %s FOR UPDATE", (pid,)).fetchone()
        if p is None:
            raise OnesRefused(404, "not_found")
        if p["state"] != "proposed":
            raise OnesRefused(409, "not_open")
        state = "approved" if verdict == "approve" else "declined"
        conn.execute(
            "UPDATE learning_proposals SET state = %s, decided_by = %s, decided_at = %s WHERE id = %s",
            (state, actor, now, pid),
        )
        conn.execute(
            "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, %s, %s, %s)",
            (f"user:{actor}", f"learning.{state}", f"learning_proposal:{pid}", Jsonb({"kind": p["kind"]})),
        )
    return {"id": pid, "state": state}


# --- Writing an approved term or tag into the company repo (BLD-136) --------------------------------------------------
PUBLISH_EVENTS = {"glossary_term": "taxonomy.glossary_added", "area_tag": "taxonomy.area_added"}
MAX_ALIASES = 8


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60].strip("-")


def _doc_file(doc_id: str) -> Path:
    folder = "glossary" if doc_id.startswith("GL-") else "areas"
    return Path(get_settings().company_repo_path) / "taxonomy" / folder / f"{doc_id}.md"


def publish(
    conn: Conn, actor: str, proposal_id: Any, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    """An admin writes an approved proposal into the company repo: a glossary term with its definition and aliases,
    or an area tag with its title and description. Everything is checked like text everyone reads, stored sealed,
    and queued for the repo writer with IDs only. Nothing is written to the repo here. Audited."""
    from ones.service import roles

    now = now or dt.datetime.now(dt.UTC)
    if "admin" not in roles(conn, actor):
        raise OnesRefused(403, "forbidden")
    try:
        pid = int(proposal_id)
    except (TypeError, ValueError):
        raise OnesRefused(404, "not_found") from None
    p = conn.execute("SELECT * FROM learning_proposals WHERE id = %s", (pid,)).fetchone()
    if p is None:
        raise OnesRefused(404, "not_found")
    if p["state"] != "approved":
        raise OnesRefused(409, "not_approved")
    if p["doc_id"]:
        raise OnesRefused(409, "already_published")
    # Checked before the transaction: the gatekeeper is a model call.
    if p["kind"] == "glossary_term":
        # The term itself goes on a page everyone reads: patterns, colleague and client names, gatekeeper (BLD-144).
        term = checked(
            conn, unseal(p["text_encrypted"], f"learning:{pid}"), min_chars=2, max_chars=60, public=True
        )
        definition = checked(
            conn, body.get("definition"), min_chars=20, max_chars=400, max_words=70, public=True
        )
        raw = body.get("aliases") or []
        if isinstance(raw, str):
            raw = raw.split(",")
        aliases = sorted({str(a).strip() for a in raw if str(a).strip()})
        if len(aliases) > MAX_ALIASES or any(len(a) > 40 for a in aliases):
            raise OnesRefused(422, "aliases_not_valid")
        if aliases:
            checked(conn, "; ".join(aliases), min_chars=1, max_chars=400, public=True)
        doc: dict[str, Any] = {"term": term, "definition": definition, "aliases": aliases}
        doc_id = f"GL-{slug(term)}"
    else:
        title = checked(conn, body.get("title"), min_chars=3, max_chars=40, max_words=6, public=True)
        description = checked(
            conn, body.get("description"), min_chars=20, max_chars=300, max_words=50, public=True
        )
        doc = {"title": title, "description": description}
        doc_id = f"AREA-{slug(title)}"
    if not re.fullmatch(r"(GL|AREA)-[a-z0-9-]{2,60}", doc_id):
        raise OnesRefused(422, "name_not_valid")
    if _doc_file(doc_id).exists():
        raise OnesRefused(409, "doc_exists")  # the product team already has it; never overwritten
    # The repo writer's exact check, now: anything it would refuse is refused here instead (BLD-143).
    rel, text, _title, _line = taxonomy_doc(str(p["kind"]), doc_id, doc, p["decided_at"])
    if doc_problem(text, rel, list(get_settings().kfin_domains)):
        raise OnesRefused(422, "doc_needs_changes")
    with conn.transaction():
        locked = conn.execute("SELECT * FROM learning_proposals WHERE id = %s FOR UPDATE", (pid,)).fetchone()
        if locked is None or locked["state"] != "approved" or locked["doc_id"]:
            raise OnesRefused(409, "already_published")
        if conn.execute("SELECT 1 FROM learning_proposals WHERE doc_id = %s", (doc_id,)).fetchone():
            raise OnesRefused(409, "doc_exists")
        conn.execute(
            "UPDATE learning_proposals SET publish_encrypted = %s, doc_id = %s, published_by = %s, published_at = %s "
            "WHERE id = %s",
            (seal_json(doc, f"learning-publish:{pid}"), doc_id, actor, now, pid),
        )
        conn.execute(
            "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES (%s, %s, 'process:learning-approval', "
            "%s)",  # who published is in audit_log; the outbox (and the git history) names the process only
            (PUBLISH_EVENTS[str(p["kind"])], doc_id, Jsonb({"proposal_id": pid})),
        )
        conn.execute(
            "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'learning.published', %s, %s)",
            (f"user:{actor}", f"learning_proposal:{pid}", Jsonb({"kind": p["kind"], "doc_id": doc_id})),
        )
    return {"id": pid, "doc_id": doc_id}


def listing(conn: Conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM learning_proposals ORDER BY (state = 'proposed') DESC, created_at DESC LIMIT 200"
    ).fetchall()
    out = []
    for r in rows:
        payload = dict(r["payload"] or {})
        out.append(
            {
                "id": r["id"], "kind": r["kind"], "period": r["period"], "state": r["state"],
                "term": unseal(r["text_encrypted"], f"learning:{r['id']}") if r["kind"] == "glossary_term" else None,
                "ideas": payload.get("ideas"), "idea_ids": payload.get("idea_ids", [])[:10],
                "current_tags": payload.get("current_tags"), "lobs": payload.get("lobs"),
                "decided_at": r["decided_at"].isoformat() if r["decided_at"] else None,
                "doc_id": r["doc_id"], "in_repo": bool(r["repo_commit"]),
                "can_publish": r["state"] == "approved" and not r["doc_id"],
            }
        )  # fmt: skip
    return out
