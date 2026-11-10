"""The points sync and a person's own view (BLD-130). Values come from `rules/points.md` in the company repo."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from rules import load_rule

log = get_logger("points")
IST = ZoneInfo("Asia/Kolkata")

# Stages an idea or group passes on its way (the decision flow, then delivery). Reaching a later one counts as
# having reached the earlier milestones on the usual path.
SHORTLISTED = ("shortlisted", "presenting", "picked", "handover", "in_garage", "in_fix_track", "shipped",
               "resolved", "measuring", "closed")  # fmt: skip
ACCEPTED = ("picked", "handover", "in_garage", "in_fix_track", "shipped", "resolved", "measuring", "closed")
SHIPPED = ("shipped", "resolved", "measuring", "closed")

WORDS = {
    "submission": "You shared an idea",
    "joined_with_context": "You teamed up and said why",
    "strong_canvas": "A strong canvas",
    "accepted_into_cluster": "Your idea joined a group",
    "shortlisted": "Shortlisted",
    "accepted": "Picked",
    "shipped_or_resolved": "Shipped",
    "presented": "You presented to the core committee",
    "working_group_member_shipped": "Your working group shipped",
}
# Read as "Points for …" on the screen (Ember review: plain words). Nothing is waiting any more (BLD-148).
COMING_SOON: list[str] = []
# `appeal_overturned: restore_forfeited` (§4.13, BLD-148). The ledger is append-only and never deducts, so what a
# decline "forfeits" is the milestones it withheld: members of a declined or parked group earn no group milestones
# while it stays there (NO_MILESTONES, stage lists below). An overturned appeal moves the group and its member ideas
# back above the line (lane B's `committee.appeals._apply`); the next sync then awards every milestone the decision
# had withheld, once, dated when the group reached it again (the stage history row the overturn writes). A person's
# own view says which awards came back this way.
RESTORED = ", restored after an appeal"
# The overturn's stage-history row and decided_at share one transaction.
RESTORE_SLACK = dt.timedelta(minutes=5)
CODE = re.compile(r"^CTR-[0-9a-f]{6,8}$")  # the ledger's own check: anything else is skipped, never inserted
HELD = ("held", "decided")  # a session that took place; 'decided' always follows 'held'
GROUP_SHIPPED = ("shipped", "resolved", "closed")  # a delivery closes only after it shipped or was resolved
LOCK = "SELECT pg_advisory_xact_lock(hashtext('points.sync'))"  # the sync and single awards, one at a time
# A member that left its group, or whose group is declined, parked or under appeal, earns the group nothing; an
# appeal pending pays nothing the decline withheld (review fix, BLD-152).
NO_MILESTONES = ("withdrawn", "declined", "parked", "appealed")
# A re-score is not a win (§4.13 restores only on an overturn): the group waits in scoring again and earns nothing
# withheld until the new round lifts it above the line.
RESCORE_PENDING = ("ready_for_scoring", "scored")
NOT_SUBMITTED = ("draft", "scanning", "blocked")  # not shared yet: no submission point


def rules() -> dict[str, Any]:
    return dict(load_rule(get_settings().company_repo_path, "points").data)


def rule_points(rule: Any, role: str | None = None) -> Decimal | None:
    """A rule's points from `rules/points.md`: a plain number (`working_group_member_shipped: 15`) or the value for
    `role` (`presented: {presenter: 3}`). None when the rule or role is missing or not a number."""
    if rule is None or isinstance(rule, bool):
        return None
    if isinstance(rule, dict):
        if role is None or role not in rule:
            return None
        rule = rule[role]
    try:
        return Decimal(str(rule))
    except (InvalidOperation, ValueError):
        return None


def contributor_codes(values: Iterable[Any] | None) -> list[str]:
    """Contributor codes as they appear on a presentation or a working group's members, de-duplicated, in order.
    Members may be `{"contributor_code": …}` objects or bare codes; anything that is not a code is skipped."""
    out: list[str] = []
    for value in values or []:
        code = value.get("contributor_code") if isinstance(value, dict) else value
        if isinstance(code, str) and CODE.match(code) and code not in out:
            out.append(code)
    return out


def _month_key(ts: dt.datetime) -> tuple[int, int]:
    local = ts.astimezone(IST)
    return local.year, local.month


def _reached(conn: Conn) -> dict[str, dict[str, dt.datetime]]:
    """When each idea, and each group through its members, first reached each stage (`idea_stage_history`)."""
    out: dict[str, dict[str, dt.datetime]] = {}
    for row in conn.execute(
        "SELECT i.idea_id, i.cluster_id, h.to_stage, min(h.at) AS at FROM idea_stage_history h "
        "JOIN ideas i ON i.id = h.idea_uuid GROUP BY i.idea_id, i.cluster_id, h.to_stage"
    ).fetchall():
        for subject in (row["idea_id"], row["cluster_id"]):
            if subject:
                seen = out.setdefault(str(subject), {})
                stage = str(row["to_stage"])
                if stage not in seen or row["at"] < seen[stage]:
                    seen[stage] = row["at"]
    return out


def _rescoring(conn: Conn) -> set[str]:
    """Groups an appeal sent back for a re-score that have not been decided again yet."""
    return {
        str(x["id"])
        for x in conn.execute(
            "SELECT c.id FROM clusters c JOIN LATERAL (SELECT a.outcome FROM appeals a WHERE a.cluster_id = c.id "
            "AND a.decided_at IS NOT NULL ORDER BY a.decided_at DESC LIMIT 1) last ON true "
            "WHERE last.outcome = 're_score' AND c.stage = ANY(%s)",
            (list(RESCORE_PENDING),),
        ).fetchall()
    }


def _back(conn: Conn) -> dict[str, dt.datetime]:
    """When each idea last came back above the line after being withheld (declined, parked or under appeal), not
    counting the wait in a re-score. Ideas never withheld are not listed."""
    held, waiting = list(NO_MILESTONES), list(NO_MILESTONES + RESCORE_PENDING)
    return {
        str(x["idea_id"]): x["at"]
        for x in conn.execute(
            "SELECT i.idea_id, max(h.at) AS at FROM idea_stage_history h JOIN ideas i ON i.id = h.idea_uuid "
            "WHERE h.from_stage = ANY(%(waiting)s) AND NOT (h.to_stage = ANY(%(waiting)s)) "
            "AND h.at > (SELECT min(x.at) FROM idea_stage_history x WHERE x.idea_uuid = h.idea_uuid "
            "            AND x.to_stage = ANY(%(held)s)) "
            "GROUP BY i.idea_id",
            {"held": held, "waiting": waiting},
        ).fetchall()
    }


def _candidates(
    conn: Conn, r: dict[str, Any], now: dt.datetime | None = None
) -> list[tuple[str, str, Decimal, str, dt.datetime]]:
    """(contributor_code, event, points, ref_id, when) for everything that has happened. Milestones are dated when
    the stage was reached (falling back to now when that is not on record); strong canvases are awarded only by the
    reviewer who confirms them (review `_award`), never here."""
    now = now or dt.datetime.now(dt.UTC)
    out: list[tuple[str, str, Decimal, str, dt.datetime]] = []
    reached = _reached(conn)

    def pts(value: Any) -> Decimal:
        return Decimal(str(value))

    def first(subject: str, stages: tuple[str, ...]) -> dt.datetime:
        times = [t for s, t in reached.get(subject, {}).items() if s in stages]
        return min(times) if times else now

    for row in conn.execute(
        "SELECT idea_id, contributor_code, submitted_at FROM ideas WHERE NOT (stage = ANY(%s)) "
        "AND submitted_at IS NOT NULL",
        (list(NOT_SUBMITTED),),
    ).fetchall():
        out.append((str(row["contributor_code"]), "submission", pts(r["submission"]["points"]),
                    str(row["idea_id"]), row["submitted_at"]))  # fmt: skip
    for row in conn.execute(
        "SELECT id, contributor_code, created_at FROM idea_links WHERE link_type = 'joiner' "
        "AND coalesce(btrim(context_text), '') <> ''"
    ).fetchall():
        out.append((str(row["contributor_code"]), "joined_with_context",
                    pts(r["joined_with_context"]["points"]), f"link:{row['id']}", row["created_at"]))  # fmt: skip

    # Groups and later milestones: originators are the ideas' own authors; joiners teamed up after a match.
    people: list[tuple[str, str, str, str, dt.datetime]] = []  # (code, role, subject, stage, when)
    rescoring = _rescoring(conn)
    back = _back(conn)
    for row in conn.execute(
        "SELECT i.idea_id, i.cluster_id, i.contributor_code, i.stage, c.stage AS cluster_stage, "
        "coalesce(i.submitted_at, i.created_at) AS at FROM ideas i LEFT JOIN clusters c ON c.id = i.cluster_id "
        "WHERE i.stage <> 'draft'"
    ).fetchall():
        subject = str(row["cluster_id"] or row["idea_id"])
        stage = str(row["cluster_stage"] or row["stage"]) if row["cluster_id"] else str(row["stage"])
        if row["cluster_id"] and (row["stage"] in NO_MILESTONES or str(row["cluster_id"]) in rescoring):
            continue
        people.append((str(row["contributor_code"]), "originator", subject, stage, row["at"]))
        if row["cluster_id"]:
            # Withheld by a decline and back again: dated when the idea left the withheld stage (BLD-148).
            when = max(row["at"], back.get(str(row["idea_id"]), row["at"]))
            out.append((str(row["contributor_code"]), "accepted_into_cluster",
                        pts(r["accepted_into_cluster"]["originator"]), str(row["cluster_id"]), when))  # fmt: skip
    for row in conn.execute(
        "SELECT l.contributor_code, coalesce(l.idea_id, l.cluster_id) AS subject, l.created_at, "
        "coalesce(c.stage, i.stage) AS stage, l.cluster_id FROM idea_links l "
        "LEFT JOIN ideas i ON i.idea_id = l.idea_id LEFT JOIN clusters c ON c.id = l.cluster_id "
        "WHERE l.link_type = 'joiner' AND (l.idea_id IS NOT NULL OR l.cluster_id IS NOT NULL)"
    ).fetchall():
        people.append((str(row["contributor_code"]), "joiner", str(row["subject"]), str(row["stage"] or ""),
                       row["created_at"]))  # fmt: skip
        if row["cluster_id"]:
            out.append((str(row["contributor_code"]), "accepted_into_cluster",
                        pts(r["accepted_into_cluster"]["joiner"]), str(row["cluster_id"]), row["created_at"]))  # fmt: skip
    for code, role, subject, stage, joined in people:
        for event, stages in (("shortlisted", SHORTLISTED), ("accepted", ACCEPTED),
                              ("shipped_or_resolved", SHIPPED)):  # fmt: skip
            if stage in stages:  # dated at the event (Ember review), never before the person joined
                out.append((code, event, pts(r[event][role]), subject, max(first(subject, stages), joined)))

    # Committee flow (lane B, §4.7), read from state like everything above so a missed hour catches up (BLD-147).
    presented = rule_points(r.get("presented"), "presenter")
    if presented is not None:
        for row in conn.execute(
            "SELECT id, presenters, held_at FROM presentations WHERE state = ANY(%s) AND held_at IS NOT NULL",
            (list(HELD),),
        ).fetchall():
            for code in contributor_codes(row["presenters"]):
                out.append((code, "presented", presented, str(row["id"]), row["held_at"]))
    group = rule_points(r.get("working_group_member_shipped"))
    if group is not None:
        for row in conn.execute(
            "SELECT w.id, w.members, coalesce(d.shipped_at, d.resolved_at, d.closed_at) AS at "
            "FROM working_groups w JOIN deliveries d ON d.subject_type = 'cluster' AND d.subject_id = w.cluster_id "
            "WHERE d.state = ANY(%s)",
            (list(GROUP_SHIPPED),),
        ).fetchall():
            for code in contributor_codes(row["members"]):
                out.append((code, "working_group_member_shipped", group, str(row["id"]), row["at"] or now))
    return out


def _used(conn: Conn, code: str, event: str, when: dt.datetime) -> Decimal:
    """Points already given for this rule to this person in the IST month of `when`."""
    row = conn.execute(
        "SELECT coalesce(sum(points), 0) AS p FROM points_ledger WHERE contributor_code = %s AND event = %s "
        "AND date_trunc('month', created_at AT TIME ZONE 'Asia/Kolkata') = "
        "date_trunc('month', %s::timestamptz AT TIME ZONE 'Asia/Kolkata')",
        (code, event, when),
    ).fetchone()
    return Decimal(str(row["p"])) if row else Decimal(0)


def award(conn: Conn, code: str, event: str, ref_id: str, when: dt.datetime | None = None) -> bool:
    """One award outside the sync (a reviewer confirming a strong canvas). Same rules, same lock: `monthly_cap` is
    points per rule per person per month (BLD-134); each award is recorded once. True if it was added."""
    rule = rules()[event]
    points = Decimal(str(rule["points"]))
    when = when or dt.datetime.now(dt.UTC)
    with conn.transaction():
        conn.execute(LOCK)
        cap = rule.get("monthly_cap")
        if cap is not None and _used(conn, code, event, when) + points > Decimal(str(cap)):
            return False
        row = conn.execute(
            "INSERT INTO points_ledger (contributor_code, event, points, ref_id, created_at) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING id",
            (code, event, points, ref_id, when),
        ).fetchone()
    return row is not None


def sync(conn: Conn, now: dt.datetime | None = None) -> int:
    """Record every award not yet in the ledger, oldest first, within each monthly cap (points per rule per person
    per month, BLD-134). Idempotent."""
    r = rules()
    caps = {
        k: Decimal(str(v["monthly_cap"])) for k, v in r.items() if isinstance(v, dict) and "monthly_cap" in v
    }
    added = 0
    with conn.transaction():
        conn.execute(LOCK)
        have = {
            (str(x["contributor_code"]), str(x["event"]), str(x["ref_id"]))
            for x in conn.execute(
                "SELECT contributor_code, event, ref_id FROM points_ledger WHERE ref_id IS NOT NULL"
            )
        }
        used: dict[tuple[str, str, int, int], Decimal] = {}
        for x in conn.execute(
            "SELECT contributor_code, event, points, created_at FROM points_ledger WHERE event = ANY(%s)",
            (list(caps),),
        ).fetchall():
            key = (str(x["contributor_code"]), str(x["event"]), *_month_key(x["created_at"]))
            used[key] = used.get(key, Decimal(0)) + Decimal(str(x["points"]))
        for code, event, points, ref, when in sorted(_candidates(conn, r, now), key=lambda c: (c[4], c[3])):
            if (code, event, ref) in have:
                continue
            if event in caps:
                key = (code, event, *_month_key(when))
                if used.get(key, Decimal(0)) + points > caps[event]:
                    continue
                used[key] = used.get(key, Decimal(0)) + points
            conn.execute(
                "INSERT INTO points_ledger (contributor_code, event, points, ref_id, created_at) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (code, event, points, ref, when),
            )
            have.add((code, event, ref))
            added += 1
    if added:
        log.info("points.synced", rows_added=added)  # a count only, never who or what
    return added


def overturned(conn: Conn) -> dict[str, dt.datetime]:
    """Groups whose decision an appeal overturned, with when (lane B's `appeals`, §4.12)."""
    return {
        str(r["cluster_id"]): r["decided_at"]
        for r in conn.execute(
            "SELECT cluster_id, max(decided_at) AS decided_at FROM appeals "
            "WHERE outcome = 'overturned' AND decided_at IS NOT NULL GROUP BY cluster_id"
        ).fetchall()
    }


def label(event: str, ref_id: str | None, when: dt.datetime, restored: dict[str, dt.datetime]) -> str:
    """The plain words for one award. Only what the overturn itself brought back says so: awards dated at the
    overturn (its stage-history row and decided_at share a transaction), not later milestones of the same group."""
    words = WORDS.get(event, "Points")
    decided = restored.get(str(ref_id)) if ref_id else None
    if decided is not None and abs(when - decided) <= RESTORE_SLACK:
        return words + RESTORED
    return words


def mine(conn: Conn, user_id: str, now: dt.datetime | None = None) -> dict[str, Any]:
    """A person's own points: the total, the last 12 months and the latest awards. Never anyone else's."""
    now = now or dt.datetime.now(dt.UTC)
    codes = [str(x["contributor_code"]) for x in conn.execute(
        "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (user_id,)).fetchall()]  # fmt: skip
    if not codes:
        return {"total": 0, "last_12_months": 0, "recent": [], "coming_soon": COMING_SOON}
    totals = conn.execute(
        "SELECT coalesce(sum(points), 0) AS total, coalesce(sum(points) FILTER (WHERE created_at >= %s), 0) AS year "
        "FROM points_ledger WHERE contributor_code = ANY(%s)",
        (now - dt.timedelta(days=365), codes),
    ).fetchone()
    restored = overturned(conn)
    recent = [
        {
            "what": label(str(x["event"]), x["ref_id"], x["created_at"], restored),
            "points": float(x["points"]),
            "on": x["created_at"].isoformat(),
        }
        for x in conn.execute(
            "SELECT event, points, ref_id, created_at FROM points_ledger WHERE contributor_code = ANY(%s) "
            "ORDER BY created_at DESC, id DESC LIMIT 10",
            (codes,),
        ).fetchall()
    ]
    return {
        "total": float(totals["total"]) if totals else 0,
        "last_12_months": float(totals["year"]) if totals else 0,
        "recent": recent,
        "coming_soon": COMING_SOON,
    }
