"""L-SEARCH over a person's own list (lane F, BLD-F039 to BLD-F041): their ideas and drafts and the ideas they
teamed up on (L-SEARCH/1), searched across titles, short summaries, references, their own words (masked copy, their
own ideas only) and the review desk's reasons as they read them (L-SEARCH/2), with filters and live counts
(L-SEARCH/5), the two sentences (L-SEARCH/3) and the no-result state (L-SEARCH/7).

    search(conn, user_id, q, filters=None, *, now=None) -> dict

Reads only the database (DEC-106). Never logs the query or any text; a person who is not found is 404 `not_found`.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping
from typing import Any

from core.db import Conn
from crew.store import viewer
from ideapage.mine import group_of
from ideapage.shape import MY_IDEAS_FILTER_LABEL
from onepc.context import open_text
from search import rules
from search.ask import interpret

LIST_LABEL = {"yours": "Yours", "teamed": "Teamed up"}
SPECS: tuple[rules.Facet, ...] = (
    rules.Facet("list", "List", multi=False, order=("yours", "teamed"), labels=LIST_LABEL),
    rules.Facet(
        "filter", "Status", multi=False, order=tuple(MY_IDEAS_FILTER_LABEL), labels=MY_IDEAS_FILTER_LABEL
    ),
    rules.Facet("area", "Category", multi=True, sort_by_label=True),
)

_COLS = "i.id::text AS uuid, i.idea_id, i.title, i.summary, i.status, i.area, i.shared_at, i.saved_at, i.created_at"


def _rows(conn: Conn, code: str) -> list[dict[str, Any]]:
    """The person's list: their drafts and shared ideas, then the ideas they are on as crew (not their own)."""
    own = conn.execute(
        f"SELECT {_COLS} FROM ideas i WHERE i.contributor_code = %s "  # noqa: S608 (fixed columns)
        "AND (i.status = 'draft' OR i.idea_id IS NOT NULL OR i.status = 'merged')",
        (code,),
    ).fetchall()
    teamed = conn.execute(
        f"SELECT {_COLS} FROM crew_members c JOIN ideas i ON i.id = c.idea_uuid "  # noqa: S608 (fixed columns)
        "WHERE c.contributor_code = %s AND c.left_at IS NULL AND c.role = 'crew' "
        "AND i.contributor_code IS DISTINCT FROM %s AND i.idea_id IS NOT NULL "
        "AND i.status NOT IN ('draft', 'withdrawn')",
        (code, code),
    ).fetchall()
    out = [{**dict(r), "list": "yours"} for r in own]
    seen = {r["uuid"] for r in out}
    out += [{**dict(r), "list": "teamed"} for r in teamed if r["uuid"] not in seen]
    for r in out:
        r["filter"] = group_of(str(r["status"]))
        r["area"] = r["area"] or None
    return out


def _texts(conn: Conn, rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Per idea: the person's own words (masked copy, their own ideas only) and the latest decision's reason."""
    out: dict[str, dict[str, str]] = {r["uuid"]: {} for r in rows}
    own = [r["uuid"] for r in rows if r["list"] == "yours"]
    if own:
        words: dict[str, list[str]] = {}
        for m in conn.execute(
            "SELECT idea_uuid::text AS idea, id::text AS id, text_encrypted FROM idea_messages "
            "WHERE idea_uuid = ANY(%s::uuid[]) ORDER BY idea_uuid, seq",
            (own,),
        ).fetchall():
            text = open_text("idea_messages", "text_encrypted", m["id"], m["text_encrypted"])
            if text:
                words.setdefault(m["idea"], []).append(text)
        for idea, parts in words.items():
            out[idea]["words"] = " ".join(parts)
    all_ids = [r["uuid"] for r in rows if r["status"] != "draft"]
    if all_ids:
        for d in conn.execute(
            "SELECT DISTINCT ON (idea_uuid) idea_uuid::text AS idea, id::text AS id, reason_encrypted "
            "FROM idea_decisions WHERE idea_uuid = ANY(%s::uuid[]) ORDER BY idea_uuid, at DESC, id",
            (all_ids,),
        ).fetchall():
            reason = open_text("idea_decisions", "reason_encrypted", d["id"], d["reason_encrypted"])
            if reason:
                out[d["idea"]]["reasons"] = reason
    return out


def _when(r: Mapping[str, Any]) -> float:
    at = r.get("shared_at") or r.get("saved_at") or r.get("created_at")
    return at.timestamp() if isinstance(at, dt.datetime) else 0.0


def search(
    conn: Conn,
    user_id: str,
    q: str | None,
    filters: Mapping[str, Iterable[str] | str | None] | None = None,
    *,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """The person's list searched by `q` and narrowed by `filters` (`list`: yours or teamed; `filter`: a My ideas
    status group; `area`: one or more categories).

    Returns `items` (each `{id, uuid, title, status, list, filter, area, score, matched_on, snippet}`, closest
    first with a query, newest first without), `total`, `filters` (every option with its live count among the rows
    the query matched), flat `counts` as "<key>:<value>", `active` (the chips), `interpreted` (None until "ask" is
    built), and with a query `search` (`sentence`, `matched_on`, `matched_line`, `closest`). With nothing to show,
    `empty` (L-SEARCH/7). `now` is accepted for callers that pin time; ordering does not depend on it."""
    del now
    me = viewer(conn, user_id)
    query = " ".join((q or "").split())[: rules.QUERY_MAX]
    active = rules.normalise(filters, SPECS)
    rows = _rows(conn, me.code) if me.code else []
    texts = _texts(conn, rows) if query and rows else {}
    ts = rules.terms(query)

    hits: list[tuple[dict[str, Any], rules.Match | None]] = []
    for r in rows:
        if not ts:
            hits.append((r, None))
            continue
        fields = {
            "title": r["title"],
            "reference": r["idea_id"],
            "summary": r["summary"],
            **texts.get(r["uuid"], {}),
        }
        m = rules.score(fields, query, ts)
        if m is not None:
            hits.append((r, m))

    shown = [(r, m) for r, m in hits if rules.matches(r, active)]
    shown.sort(key=lambda rm: ((rm[1].score if rm[1] else 0.0), _when(rm[0])), reverse=True)
    groups = rules.facets([r for r, _ in hits], active, SPECS)
    body: dict[str, Any] = {
        "q": query,
        "terms": ts,
        "interpreted": interpret(query) if query else None,
        "items": [
            {
                "id": r["idea_id"],
                "uuid": r["uuid"],
                "title": r["title"] or "",
                "status": r["status"],
                "list": r["list"],
                "filter": r["filter"],
                "area": r["area"],
                "score": round(m.score, 3) if m else None,
                "matched_on": list(m.matched_on) if m else [],
                "snippet": m.snippet if m else "",
            }
            for r, m in shown
        ],
        "total": len(shown),
        "filters": groups,
        "counts": {f"{g['key']}:{o['value']}": o["count"] for g in groups for o in g["options"]},
        "active": rules.chips(active, SPECS),
    }
    if query:
        mine = sum(1 for r, _ in shown if r["list"] == "yours")
        teamed = len(shown) - mine
        best = shown[0][0] if shown else None
        fields_hit = {f for _, m in shown if m for f in m.matched_on}
        body["search"] = {
            "sentence": rules.sentence(query, mine, teamed, best["title"] if best else None),
            "matched_on": [k for k, _, _ in rules.FIELDS if k in fields_hit],
            "matched_line": rules.matched_line(fields_hit),
            "closest": {"id": best["idea_id"], "uuid": best["uuid"], "title": best["title"]}
            if best
            else None,
        }
    if not shown and (query or active):
        body["empty"] = rules.empty(query)
    return body
