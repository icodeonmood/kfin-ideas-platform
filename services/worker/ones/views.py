"""What people see of the Ones (DEC-068 to DEC-086).

- **Public** (wall, home carousel, office screens): active Ones, newest first. A name shows only for a One who said
  yes to showing their name; otherwise "One No. 17". The idea line is the checked neutral summary of an accepted
  idea everyone may see, or the checked title of a sponsored or founding One. Money shows only once Finance has
  confirmed it. `ones.public` off hides all of it.
- **The One's own dashboard**: their number, tier, swap window, brief, glow-up and story.
- **The Showcase brief**, and **what `/ones/write/:id` asks a writer** for a tier change (both kept, BLD-E042).
- **A manager's team view**: their direct reports' activity, counts only (DEC-079).

The console and the Ones-only leaderboard are retired (DEC-106, BLD-E049): lane A's admin page and the Wall's
leaderboard (`wall.ones.one_cards(order="leaderboard")`) replace them.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from core import killswitch
from core.db import Conn
from core.stage_words import PUBLIC_WORDS
from ones import numbers
from ones.service import SHOWCASE_PARTS
from ones.text import unseal, unseal_json
from ones.tiers import tier_colour, tier_name
from views.common import (
    IN_GARAGE,
    PICKED,
    PUBLIC_STAGES,
    SHIPPED,
    SUMMARY_PENDING,
    checked_summary,
    public_summary,
)

WAY_IN_WORDS = {"accepted_idea": "Accepted idea", "sponsored": "Sponsored", "founding": "Founding One"}


def _iso(ts: Any) -> str | None:
    return ts.isoformat() if ts else None


def _tier(n: int) -> dict[str, Any]:
    return {"tier": n, "tier_name": tier_name(n), "tier_colour": tier_colour(n)}


def _public_measures(m: dict[str, Any] | None) -> dict[str, Any]:
    """Measures everyone may see: money only once Finance has confirmed it (DEC-071)."""
    out = {}
    for key, value in (m or {}).items():
        if key == "money" and not value.get("finance_confirmed"):
            continue
        out[key] = {"value": value.get("value"), "unit": value.get("unit")}
    return out


def _idea_line(conn: Conn, one: dict[str, Any], public: bool) -> tuple[str | None, str | None]:
    """(what they built or are building, its stage in plain words). In public, an idea the review desk or an admin
    took off the Wall gives no line (`idea_off_wall`, DEC-106, BLD-A212)."""
    if one["way_in"] == "accepted_idea" and one["idea_id"]:
        idea = conn.execute(
            "SELECT stage, visibility, canvas, idea_off_wall(id) AS off_wall FROM ideas WHERE idea_id = %s",
            (one["idea_id"],),
        ).fetchone()
        if idea is None:
            return None, None
        if public:
            if idea["visibility"] != "org" or idea["stage"] not in PUBLIC_STAGES or idea["off_wall"]:
                return None, None
            summary = public_summary(conn, idea["canvas"])  # an unsafe one is still left out
        else:
            summary = str((idea["canvas"] or {}).get("neutral_summary") or "").strip() or SUMMARY_PENDING
        return summary, PUBLIC_WORDS.get(idea["stage"])
    title = unseal(one["title_encrypted"], f"one:{one['id']}:title")
    if public:  # checked when it was written; checked again before everyone sees it (Ones review, BLD-111)
        title = checked_summary(conn, title)
    return title, None


# --- Public: wall, home carousel, screens ---------------------------------------------------------------------------


def public(conn: Conn) -> dict[str, Any]:
    if not killswitch.is_on("ones.public", conn):
        return {"paused": True, "ones": []}
    rows = conn.execute(
        "SELECT o.*, u.name, coalesce(s.show_name_on_wall, true) AS shown FROM ones o "
        "JOIN users u ON u.id = o.user_id LEFT JOIN person_settings s ON s.user_id = o.user_id "
        "WHERE o.status = 'active' ORDER BY o.inducted_at DESC, o.id DESC"
    ).fetchall()
    out = []
    for r in rows:
        o = dict(r)
        line, stage = _idea_line(conn, o, public=True)
        brief = unseal(o["brief_encrypted"], f"one:{o['id']}:brief") if o["brief_approved_at"] else None
        brief = checked_summary(conn, brief)  # defence in depth: no name or client reaches the wall (BLD-111)
        out.append(
            {
                "number": o["number"], "induction_no": o["induction_no"], **_tier(o["tier"]),
                "name": o["name"] if o["shown"] else None, "founding": o["way_in"] == "founding",
                "way_in": WAY_IN_WORDS[o["way_in"]], "line": line, "stage": stage, "brief": brief,
                "measures": _public_measures(o["measures"]),
            }
        )  # fmt: skip
    return {"paused": False, "ones": out}


def constellation(conn: Conn) -> dict[str, Any]:
    """Every One's spark (retired Ones keep theirs in the sky), plus the cards the screens alternate with."""
    if not killswitch.is_on("ones.public", conn):
        return {"paused": True, "mode": "static", "sparks": [], "cards": []}
    mode = conn.execute("SELECT mode FROM screen_settings WHERE id").fetchone()
    sparks = [
        {"induction_no": r["induction_no"], **_tier(r["tier"]), "active": r["status"] == "active"}
        for r in conn.execute("SELECT induction_no, tier, status FROM ones ORDER BY induction_no").fetchall()
    ]
    cards = [c for c in public(conn)["ones"] if c["brief"]]
    return {"paused": False, "mode": mode["mode"] if mode else "static", "sparks": sparks, "cards": cards}


# --- The One's own dashboard -----------------------------------------------------------------------------------------


def _story(conn: Conn, one: dict[str, Any], user_id: str) -> dict[str, Any]:
    codes = [r["contributor_code"] for r in conn.execute(
        "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (user_id,)).fetchall()]  # fmt: skip
    counts = conn.execute(
        "SELECT count(*) FILTER (WHERE stage <> 'draft') AS shared, "
        "count(*) FILTER (WHERE stage = ANY(%s)) AS picked, count(*) FILTER (WHERE stage = ANY(%s)) AS shipped "
        "FROM ideas WHERE contributor_code = ANY(%s)",
        (list(PICKED + IN_GARAGE), list(SHIPPED), codes),
    ).fetchone()
    milestones = [{"on": _iso(one["inducted_at"]), "what": "Became a One"}]
    for g in conn.execute(
        "SELECT g.tier_to, p.carried_out_at FROM one_glow_ups g JOIN one_proposals p ON p.id = g.proposal_id "
        "WHERE g.one_id = %s ORDER BY p.carried_out_at",
        (one["id"],),
    ).fetchall():
        milestones.append({"on": _iso(g["carried_out_at"]), "what": f"Reached {tier_name(g['tier_to'])}"})
    for a in conn.execute(
        "SELECT year, category, awarded_at FROM one_awards WHERE one_id = %s", (one["id"],)
    ).fetchall():
        milestones.append(
            {"on": _iso(a["awarded_at"]), "what": f"The Ones Night {a['year']}: {a['category']} award"}
        )
    milestones.sort(key=lambda m: m["on"] or "")
    return {
        "ideas_shared": int(counts["shared"]) if counts else 0,
        "ideas_picked": int(counts["picked"]) if counts else 0,
        "ideas_shipped": int(counts["shipped"]) if counts else 0,
        "milestones": milestones,
        "measures": one["measures"] or {},
    }


def my_one(conn: Conn, user_id: str, now: dt.datetime | None = None) -> dict[str, Any] | None:
    now = now or dt.datetime.now(dt.UTC)
    row = conn.execute("SELECT * FROM ones WHERE user_id = %s", (user_id,)).fetchone()
    if row is None:
        return None
    one = dict(row)
    line, stage = _idea_line(conn, one, public=False)
    pending = conn.execute(
        "SELECT id FROM one_proposals WHERE subject_user_id = %s AND kind = 'impact_brief' AND state = 'proposed'",
        (user_id,),
    ).fetchone()
    pref = conn.execute(
        "SELECT show_name_on_wall FROM person_settings WHERE user_id = %s", (user_id,)
    ).fetchone()
    shown = pref is None or bool(pref["show_name_on_wall"])  # shown unless hidden (DEC-104)
    glow = conn.execute(
        "SELECT * FROM one_glow_ups WHERE one_id = %s AND seen_at IS NULL ORDER BY id DESC LIMIT 1",
        (one["id"],),
    ).fetchone()
    glow_up = None
    if glow is not None:
        msgs = conn.execute(
            "SELECT m.id, m.author_role, m.text_encrypted, u.name FROM one_messages m "
            "JOIN users u ON u.id = m.author_user_id WHERE m.proposal_id = %s "
            "ORDER BY array_position(ARRAY['committee', 'ceo', 'peer'], m.author_role), m.written_at",
            (glow["proposal_id"],),
        ).fetchall()
        glow_up = {
            "id": glow["id"],
            "from": _tier(glow["tier_from"]),
            "to": _tier(glow["tier_to"]),
            "up": glow["tier_to"] > glow["tier_from"],
            "story": _story(conn, one, user_id),
            "messages": [
                {
                    "from": m["author_role"],
                    "name": "The 1% Club core committee" if m["author_role"] == "committee" else m["name"],
                    "text": unseal(m["text_encrypted"], f"one_message:{m['id']}"),
                }
                for m in msgs
            ],
        }
    showcase = conn.execute(
        "SELECT updated_at FROM one_showcase_briefs WHERE one_id = %s", (one["id"],)
    ).fetchone()
    return {
        "active": one["status"] == "active",
        "number": one["number"],
        "induction_no": one["induction_no"],
        **_tier(one["tier"]),
        "way_in": WAY_IN_WORDS[one["way_in"]],
        "line": line,
        "stage": stage,
        "since": _iso(one["inducted_at"]),
        "swap_until": _iso(one["swap_until"]),
        "can_swap": one["status"] == "active" and now <= one["swap_until"],
        "brief": unseal(one["brief_encrypted"], f"one:{one['id']}:brief")
        if one["brief_approved_at"]
        else None,
        "brief_pending": pending is not None,
        "name_on_wall": shown,
        "measures": one["measures"] or {},
        "glow_up": glow_up,
        "showcase_updated": _iso(showcase["updated_at"]) if showcase else None,
    }


def number_free(conn: Conn, user_id: str, number: int, now: dt.datetime | None = None) -> bool:
    now = now or dt.datetime.now(dt.UTC)
    one = conn.execute("SELECT id FROM ones WHERE user_id = %s", (user_id,)).fetchone()
    if one is None:
        return False
    return numbers.is_free(conn, number, int(one["id"]), now)


# --- The Showcase brief (DEC-086) ---------------------------------------------------------------------------------


def showcase(conn: Conn, one_id: int) -> dict[str, Any] | None:
    """The seven parts, each the One's own words if they wrote them, else what their record says."""
    row = conn.execute(
        "SELECT o.*, u.name FROM ones o JOIN users u ON u.id = o.user_id WHERE o.id = %s", (one_id,)
    ).fetchone()
    if row is None:
        return None
    one = dict(row)
    line, stage = _idea_line(conn, one, public=False)
    saved = conn.execute("SELECT * FROM one_showcase_briefs WHERE one_id = %s", (one_id,)).fetchone()
    own = (unseal_json(saved["parts_encrypted"], f"one:{one_id}:showcase") if saved else None) or {}
    from_record = {
        "idea": line,
        "proposed_impact": unseal(one["brief_encrypted"], f"one:{one_id}:brief")
        if one["brief_approved_at"]
        else None,
        "progress": stage,
        "impact_so_far": None,  # the web app writes the measures out in words
        "timelines": None,
        "team": None,
        "help": None,
    }
    return {
        "one_id": one_id,
        "number": one["number"],
        "name": one["name"],
        **_tier(one["tier"]),
        "measures": one["measures"] or {},
        "updated_at": _iso(saved["updated_at"]) if saved else None,
        "parts": [
            {"key": k, "own": own.get(k) or "", "from_record": from_record.get(k)} for k in SHOWCASE_PARTS
        ],
    }


def showcase_for_user(conn: Conn, user_id: str) -> dict[str, Any] | None:
    one = conn.execute("SELECT id FROM ones WHERE user_id = %s AND status = 'active'", (user_id,)).fetchone()
    return showcase(conn, int(one["id"])) if one else None


# --- The manager's team view ------------------------------------------------------------------------------------


def team(conn: Conn, manager_id: str) -> dict[str, Any]:
    """A manager's direct reports: counts of what they shared and built, never the ideas' text (DEC-079).

    Only people who allow manager notes are counted or listed; anyone who opted out is left out entirely, with no
    count that could point to them (BLD-113). Only ideas everyone can see count: `visibility = 'org'` in a public
    stage, so committee-only, blocked, withdrawn and draft ideas never show. One query, not one per person."""
    rows = conn.execute(
        "SELECT u.id, u.name, o.number, o.tier, "
        "count(i.id) FILTER (WHERE i.stage = ANY(%s)) AS shared, "
        "count(i.id) FILTER (WHERE i.stage = ANY(%s)) AS building, "
        "count(i.id) FILTER (WHERE i.stage = ANY(%s)) AS shipped "
        "FROM users u LEFT JOIN comms_prefs c ON c.user_id = u.id "
        "LEFT JOIN ones o ON o.user_id = u.id AND o.status = 'active' "
        "LEFT JOIN contributor_map m ON m.user_id = u.id "
        "LEFT JOIN ideas i ON i.contributor_code = m.contributor_code AND i.visibility = 'org' "
        "WHERE u.manager_user_id = %s AND u.active AND coalesce(c.manager_notes, true) "
        "GROUP BY u.id, u.name, o.number, o.tier ORDER BY u.name",
        (list(PUBLIC_STAGES), list(PICKED + IN_GARAGE), list(SHIPPED), manager_id),
    ).fetchall()
    out = [
        {
            "name": r["name"],
            "shared": int(r["shared"]),
            "building": int(r["building"]),
            "shipped": int(r["shipped"]),
            "one": {"number": r["number"], **_tier(r["tier"])} if r["number"] is not None else None,
        }
        for r in rows
    ]
    totals = {k: sum(p[k] for p in out) for k in ("shared", "building", "shipped")}
    return {"people": out, "totals": totals, "ones": sum(1 for p in out if p["one"])}


def invite_view(conn: Conn, proposal_id: int, user_id: str) -> dict[str, Any] | None:
    """What a person is asked to write for a One's tier change, and as whom (DEC-084). None if they may not."""
    from ones.service import roles

    p = conn.execute(
        "SELECT p.*, o.number, u.name, coalesce(s.show_name_on_wall, true) AS shown FROM one_proposals p "
        "JOIN ones o ON o.id = p.one_id JOIN users u ON u.id = o.user_id "
        "LEFT JOIN person_settings s ON s.user_id = o.user_id WHERE p.id = %s AND p.kind IN ('tier_up', 'tier_down')",
        (proposal_id,),
    ).fetchone()
    if p is None or p["state"] not in ("proposed", "approved") or str(p["subject_user_id"]) == user_id:
        return None
    have = roles(conn, user_id)
    invited = conn.execute(
        "SELECT 1 FROM one_message_invites WHERE proposal_id = %s AND user_id = %s", (proposal_id, user_id)
    ).fetchone()
    as_role = (
        "committee"
        if have & {"core_committee", "core_chair"}
        else "ceo"
        if "ceo" in have
        else "peer"
        if invited
        else None
    )
    if as_role is None:
        return None
    written = conn.execute(
        "SELECT 1 FROM one_messages WHERE proposal_id = %s AND author_user_id = %s", (proposal_id, user_id)
    ).fetchone()
    display = f"No. {p['number']}, {p['name']}" if p["shown"] else f"One No. {p['number']}"
    return {
        "one_display": display,
        "tier_to_name": tier_name(p["tier_to"]),
        "as": as_role,
        "written": written is not None,
    }
