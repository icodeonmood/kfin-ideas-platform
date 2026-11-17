"""The Wall's ideas: Kindling by stage and Just in (L-WALL.kindling, L-WALL.justin, S-WALL, V-ACC.browse/3, /4, /6).

What a row carries is what everyone may see (P-PRODUCT.privacy, DEC-104): the reference, the title and short
summary (masked when stored, re-checked here), kind, area, figures, and the sharer only if they let their name show.
Never their own words, never points. Every query goes through `on_wall_sql`.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Any

from core.db import Conn
from onepc.enums import KIND, values
from wall.common import (
    IST,
    KIND_LABEL,
    SHARER_COLS,
    SHARER_JOIN,
    Refused,
    ago_label,
    indian,
    on_wall_sql,
    plural,
    public_text,
    sharer_ref,
    wall_kind_sql,
    wall_to,
)

STAGES: tuple[str, ...] = values("wall_stage")  # picked, being_built, shipped (each is also an idea status)
SORTS: tuple[str, ...] = values("wall_sort")  # popular, newest, crew, ones
WITH_THE_DESK = ("with_review_desk", "needs_you")  # needs_you is with_review_desk as the sharer sees it
KINDLING_ITEMS = 3  # S-WALL.kindling: up to three ideas a stage
PAGE = 5  # L-WALL.justin/5: five rows, then "Show 5 more"
MAX_PAGE = 50
OPENED_DAYS = 7  # L-WALL.justin/4

CACHE_S = 20.0  # the same for everyone; a name hidden in Profile shows hidden within a minute (S-H6.rules/2)
_cache: dict[tuple[Any, ...], tuple[float, Any]] = {}


def clear_cache() -> None:
    _cache.clear()


def _cached(key: tuple[Any, ...], build: Any) -> Any:
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_S:
        return hit[1]
    out = build()
    if len(_cache) > 500:
        _cache.clear()
    _cache[key] = (time.monotonic(), out)
    return out


def _kind(kind: str | None) -> str | None:
    if kind in (None, "", "all"):
        return None
    if kind not in KIND:
        raise Refused(400, "bad_kind", field="kind")
    return kind


_CREW = "greatest(1, (SELECT count(*) FROM crew_members c WHERE c.idea_uuid = i.id AND c.left_at IS NULL))"
_ONES_ON_CREW = (
    "(SELECT count(DISTINCT o.user_id) FROM crew_members c JOIN contributor_map m ON m.contributor_code = "
    "c.contributor_code JOIN ones o ON o.user_id = m.user_id AND o.status = 'active' "
    "WHERE c.idea_uuid = i.id AND c.left_at IS NULL)"
)
# Distinct signed-in colleagues who opened the idea in the last 7 days, never its sharer or a reviewer.
_OPENED = (
    "(SELECT count(DISTINCT op.user_id) FROM idea_opens op WHERE op.idea_uuid = i.id AND op.day >= %(since)s "
    "AND op.user_id IS DISTINCT FROM scm.user_id AND NOT EXISTS (SELECT 1 FROM role_grants g "
    "WHERE g.user_id = op.user_id AND g.role = 'reviewer' AND g.valid_from <= now() "
    "AND (g.valid_to IS NULL OR g.valid_to > now())))"
)


def _item(r: dict[str, Any], back: str) -> dict[str, Any] | None:
    title = public_text(r["title"])
    if title is None:
        return None
    kind, area = str(r["wkind"]), str(r["area"] or "")
    return {
        "id": r["idea_id"],
        "title": title,
        "summary": public_text(r["summary"]) or "",
        "kind": kind,
        "area": area,
        "crew_count": int(r["crew_count"]),
        "sharer": sharer_ref(r),
        # "Problem, Investor service" (S-WALL.justin; Kindling adds ", 4 colleagues on it")
        "meta": ", ".join(x for x in (KIND_LABEL.get(kind, ""), area) if x),
        "to": wall_to(str(r["idea_id"]), back),
    }


def _back(kind: str | None, sort: str | None = None) -> str:
    """The Wall's own address with the state the server knows (kind chip, sort), for the idea's Back link."""
    q = "&".join(f"{k}={v}" for k, v in (("kind", kind), ("sort", sort)) if v and v != "newest")
    return "/wall" + (f"?{q}" if q else "")


def kindling(conn: Conn, kind: str | None = None) -> list[dict[str, Any]]:
    """`WallStage[3]` (A-API.wall): Picked, Being built, Shipped, each with its count and up to three ideas, newest
    move first. The kind chip filters the counts and the ideas together (V-ACC.browse/6)."""
    k = _kind(kind)
    return list(_cached(("kindling", conn.info.dsn, k), lambda: _kindling(conn, k)))


def _kindling(conn: Conn, kind: str | None) -> list[dict[str, Any]]:
    sql = (
        "WITH base AS (SELECT i.id, i.idea_id, i.title, i.summary, i.area, i.status, "  # noqa: S608 (fragments are this package's own)
        f"{wall_kind_sql('i')} AS wkind, coalesce(i.status_changed_at, i.shared_at) AS moved_at, "
        f"{_CREW} AS crew_count, {SHARER_COLS} FROM ideas i {SHARER_JOIN.format(a='i')} "
        f"WHERE i.status = ANY(%(stages)s) AND i.idea_id IS NOT NULL AND {on_wall_sql('i')}), "
        "kinded AS (SELECT * FROM base WHERE %(kind)s::text IS NULL OR wkind = %(kind)s) "
        "SELECT *, count(*) OVER (PARTITION BY status) AS stage_count, row_number() OVER (PARTITION BY status "
        "ORDER BY moved_at DESC NULLS LAST, idea_id DESC) AS rn FROM kinded"
    )
    rows = conn.execute(sql, {"stages": list(STAGES), "kind": kind}).fetchall()
    out = []
    back = _back(kind)
    for stage in STAGES:
        mine = sorted((dict(r) for r in rows if r["status"] == stage), key=lambda r: r["rn"])
        items = [x for x in (_item(r, back) for r in mine) if x is not None][:KINDLING_ITEMS]
        for x in items:  # "Problem, Distributor experience, 4 colleagues on it" (S-WALL.kindling)
            x["meta"] = ", ".join(y for y in (x["meta"], f"{plural(x['crew_count'], 'colleague')} on it") if y)
        out.append({"stage": stage, "count": int(mine[0]["stage_count"]) if mine else 0, "items": items})
    return out


def figure_label(sort: str, row: dict[str, Any]) -> str:
    """The figure for the current sort, as the phone's second line says it (L-WALL.justin/5, S-WALL.phone):
    "Opened by 233 this week", "Shared 2h ago", "3 on the crew", "1 One on the crew"."""
    if sort == "popular":
        return f"Opened by {indian(row['opened_7d'])} this week"
    if sort == "crew":
        return f"{indian(row['crew_count'])} on the crew"
    if sort == "ones":
        return f"{plural(row['ones_count'], 'One')} on the crew"
    label = str(row["shared_label"])
    return f"Shared {label[:1].lower() + label[1:] if label in ('Yesterday', 'Just now') else label}"


def _order(sort: str) -> str:
    key = {"popular": "opened_7d", "newest": "shared_at", "crew": "crew_count", "ones": "ones_count"}[sort]
    return f"{key} DESC NULLS LAST, shared_at DESC NULLS LAST, idea_id DESC"  # ties go to the newest


def just_in(
    conn: Conn,
    kind: str | None = None,
    sort: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """`{ items: JustInRow[], total, counts }` (A-API.wall): ideas with the review desk, sorted one way at a time
    (Popular, Newest by default, Crew size, Ones; ties to the newest), five at a time. `counts` per kind chip."""
    k = _kind(kind)
    s = sort or "newest"
    if s not in SORTS:
        raise Refused(400, "bad_sort", field="sort")
    lim = PAGE if limit is None else limit
    off = offset or 0
    if not 1 <= lim <= MAX_PAGE or off < 0:
        raise Refused(400, "bad_page", field="limit")
    now = now or dt.datetime.now(dt.UTC)
    since = (now.astimezone(IST).date()) - dt.timedelta(days=OPENED_DAYS - 1)
    return dict(
        _cached(
            ("just_in", conn.info.dsn, k, s, lim, off, since),
            lambda: _just_in(conn, k, s, lim, off, since, now),
        )
    )


def _just_in(
    conn: Conn, kind: str | None, sort: str, limit: int, offset: int, since: dt.date, now: dt.datetime
) -> dict[str, Any]:
    base = (
        "SELECT i.id, i.idea_id, i.title, i.summary, i.area, i.shared_at, "  # noqa: S608 (fragments are this package's own)
        f"{wall_kind_sql('i')} AS wkind, {_CREW} AS crew_count, {_ONES_ON_CREW} AS ones_count, "
        f"{_OPENED} AS opened_7d, {SHARER_COLS} FROM ideas i {SHARER_JOIN.format(a='i')} "
        f"WHERE i.status = ANY(%(desk)s) AND i.idea_id IS NOT NULL AND {on_wall_sql('i')}"
    )
    params: dict[str, Any] = {"desk": list(WITH_THE_DESK), "since": since, "kind": kind}
    counts = {
        str(r["wkind"]): int(r["n"])
        for r in conn.execute(
            f"SELECT wkind, count(*) AS n FROM ({base}) b GROUP BY wkind",  # noqa: S608 (fragments are this package's own)
            params,
        ).fetchall()
    }
    counts["all"] = sum(counts.values())
    rows = conn.execute(
        f"SELECT * FROM ({base}) b WHERE %(kind)s::text IS NULL OR wkind = %(kind)s "  # noqa: S608
        f"ORDER BY {_order(sort)} LIMIT %(limit)s OFFSET %(offset)s",
        {**params, "limit": limit, "offset": offset},
    ).fetchall()
    items = []
    back = _back(kind, sort)
    for r in rows:
        item = _item(dict(r), back)
        if item is None:
            continue
        shared = r["shared_at"]
        item.update(
            {
                "shared_at": shared.isoformat() if shared else None,
                "shared_label": ago_label(shared, now) if shared else "",
                "opened_7d": int(r["opened_7d"]),
                "ones_count": int(r["ones_count"]),
            }
        )
        item["figure_label"] = figure_label(sort, item)
        items.append(item)
    total = counts["all"] if kind is None else counts.get(kind, 0)
    nxt = offset + limit
    more = min(limit, total - nxt) if nxt < total else 0
    return {
        "items": items,
        "total": total,
        "counts": {key: counts.get(key, 0) for key in ("all", *KIND)},
        "sort": sort,
        "next": str(nxt) if nxt < total else None,
        # "12 with the review desk" (L-WALL.justin/1); "Show 5 more", "Show 2 more", then "Show fewer"
        # (L-WALL.justin/5, V-ACC.browse/3). The page asks for its own page size: 5 on desktop, 3 on the phone.
        "sub": f"{indian(total)} with the review desk",
        "more": more,
        "more_label": f"Show {more} more" if more else ("Show fewer" if offset > 0 else None),
    }
