"""`learning.run`, daily at 05:30 IST: decides which loops are due today and runs them. Every day: autonomy.
Mondays: drift, glossary and friction themes by role (BLD-139). The 1st of the month: the canvas report and area tags. The 1st of a quarter:
calibration for the quarter just ended. Nothing runs while `learning.jobs` is off. An admin can run one by hand."""

from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from core import killswitch
from core.db import Conn
from core.logging import get_logger
from learning import proposals, reports, role_themes

log = get_logger("learning.run")
IST = ZoneInfo("Asia/Kolkata")
KINDS = ("autonomy", "drift", "glossary", "canvas", "area_tags", "calibration", "role_themes")


def due(day: dt.date) -> list[str]:
    out = ["autonomy"]
    if day.weekday() == 0:
        out += ["drift", "glossary", "role_themes"]
    if day.day == 1:
        out += ["canvas", "area_tags"]
        if day.month in (1, 4, 7, 10):
            out.append("calibration")
    return out


def run_one(conn: Conn, kind: str, now: dt.datetime) -> Any:
    day = now.astimezone(IST).date()
    if kind == "autonomy":
        return reports.autonomy(conn, now)
    if kind == "drift":
        return reports.drift(conn, now)
    if kind == "canvas":
        return reports.canvas(conn, now)
    if kind == "calibration":
        return reports.calibration(conn, now)
    if kind == "glossary":
        return proposals.glossary(conn, now, day.strftime("%G-W%V"))
    if kind == "area_tags":
        return proposals.area_tags(conn, now, day.strftime("%Y-%m"))
    if kind == "role_themes":
        return role_themes.propose(conn, now, day.strftime("%G-W%V"))
    raise ValueError(kind)


def run(conn: Conn, now: dt.datetime | None = None, only: str | None = None) -> list[str]:
    now = now or dt.datetime.now(dt.UTC)
    if not killswitch.is_on("learning.jobs", conn):
        log.info("learning.switched_off")
        return []
    kinds = [only] if only else due(now.astimezone(IST).date())
    for kind in kinds:
        run_one(conn, kind, now)
        log.info("learning.ran", loop=kind)
    return kinds


def run_now(conn: Conn, actor: str, body: dict[str, Any]) -> dict[str, Any]:
    """An admin runs one loop by hand (for example, the glossary before a review meeting)."""
    from ones.service import roles
    from ones.text import OnesRefused

    if "admin" not in roles(conn, actor):
        raise OnesRefused(403, "forbidden")
    kind = body.get("kind")
    if kind not in KINDS:
        raise OnesRefused(400, "kind_required")
    if not killswitch.is_on("learning.jobs", conn):
        raise OnesRefused(503, "learning_paused")
    run(conn, only=str(kind))
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'learning.run_now', 'learning', "
        "jsonb_build_object('kind', %s::text))",
        (f"user:{actor}", kind),
    )
    return {"ran": kind}


def overview(conn: Conn) -> dict[str, Any]:
    latest = {
        r["kind"]: {"period": r["period"], "data": r["data"], "built_at": r["built_at"].isoformat()}
        for r in conn.execute(
            "SELECT DISTINCT ON (kind) kind, period, data, built_at FROM learning_reports "
            "ORDER BY kind, built_at DESC"
        ).fetchall()
    }
    autonomy = [
        {"action_type": r["action_type"], "mode": r["mode"], "rate": float(r["window_accept_rate"])
         if r["window_accept_rate"] is not None else None, "window": r["window_size"]}
        for r in conn.execute("SELECT * FROM autonomy ORDER BY action_type").fetchall()
    ]  # fmt: skip
    return {
        "switched_on": killswitch.is_on("learning.jobs", conn),
        "reports": latest,
        "autonomy": autonomy,
        "proposals": proposals.listing(conn),
        "role_themes": role_themes.listing(conn),
    }


def view(conn: Conn, viewer_id: str) -> dict[str, Any]:
    """The product team's learning page: admins only (the web checks `review_learning`; this checks again)."""
    from ones.service import roles
    from ones.text import OnesRefused

    if "admin" not in roles(conn, viewer_id):
        raise OnesRefused(403, "forbidden")
    return overview(conn)
