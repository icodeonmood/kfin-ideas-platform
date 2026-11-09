"""What people see of the Ones (DEC-068 to DEC-086).

- **The console** (core committee, CEO, admin): every One and every proposal, with names and reasons.
- **Public** (wall, home carousel, office screens): active Ones, newest first. A name shows only for a One who said
  yes to showing their name; otherwise "One No. 17". The idea line is the checked neutral summary of an accepted
  idea everyone may see, or the checked title of a sponsored or founding One. Money shows only once Finance has
  confirmed it. `ones.public` off hides all of it.
- **The One's own dashboard**: their number, tier, swap window, brief, glow-up and story.
- **The leaderboard**: Ones only (DEC-077), by tier then measured impact (DEC-083).
- **A manager's team view**: their direct reports' activity, counts only (DEC-079).
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
from views.common import IN_GARAGE, PICKED, PUBLIC_STAGES, SHIPPED, checked_summary, taxonomy_names

WAY_IN_WORDS = {"accepted_idea": "Accepted idea", "sponsored": "Sponsored", "founding": "Founding One"}
KIND_WORDS = {
    "include": "Inclusion",
    "remove": "Removal",
    "tier_up": "Tier up",
    "tier_down": "Tier down",
    "impact_brief": "Impact brief",
    "legend": "Legend number",
}
MEMBERSHIP = dt.timedelta(days=365)


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
    """(what they built or are building, its stage in plain words)."""
    if one["way_in"] == "accepted_idea" and one["idea_id"]:
        idea = conn.execute(
            "SELECT stage, visibility, canvas FROM ideas WHERE idea_id = %s", (one["idea_id"],)
        ).fetchone()
        if idea is None:
            return None, None
        summary = (idea["canvas"] or {}).get("neutral_summary")
        if public:
            if idea["visibility"] != "org" or idea["stage"] not in PUBLIC_STAGES:
                return None, None
            summary = checked_summary(conn, summary)
        return summary, PUBLIC_WORDS.get(idea["stage"])
    title = unseal(one["title_encrypted"], f"one:{one['id']}:title")
    return title, None


def _names(conn: Conn, user_ids: list[str]) -> dict[str, str]:
    if not user_ids:
        return {}
    rows = conn.execute("SELECT id, name FROM users WHERE id = ANY(%s::uuid[])", (user_ids,)).fetchall()
    return {str(r["id"]): str(r["name"]) for r in rows}


# --- Console -----------------------------------------------------------------------------------------------------


def console(conn: Conn, now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.UTC)
    ones = [
        dict(r)
        for r in conn.execute(
            "SELECT o.*, u.name, u.email FROM ones o JOIN users u ON u.id = o.user_id "
            "ORDER BY (o.status = 'active') DESC, o.number NULLS LAST, o.induction_no"
        ).fetchall()
    ]
    legends = {
        int(r["one_id"]): int(r["number"])
        for r in conn.execute("SELECT * FROM one_legend_numbers").fetchall()
    }
    showcase = {
        int(r["one_id"]): _iso(r["updated_at"])
        for r in conn.execute("SELECT one_id, updated_at FROM one_showcase_briefs").fetchall()
    }
    roster = []
    for o in ones:
        line, stage = _idea_line(conn, o, public=False)
        lapses = o["inducted_at"] + MEMBERSHIP
        roster.append(
            {
                "id": o["id"], "induction_no": o["induction_no"], "number": o["number"], "name": o["name"],
                "email": o["email"], "status": o["status"], "way_in": WAY_IN_WORDS[o["way_in"]], "idea_id": o["idea_id"],
                **_tier(o["tier"]), "line": line, "stage": stage,
                "brief": unseal(o["brief_encrypted"], f"one:{o['id']}:brief"),
                "measures": o["measures"] or {}, "since": _iso(o["inducted_at"]), "lapses_on": _iso(lapses),
                "lapsed": o["status"] == "active" and now > lapses, "retired_at": _iso(o["retired_at"]),
                "legend_number": legends.get(o["id"]), "announced": o["announced_at"] is not None,
                "showcase_updated": showcase.get(o["id"]),
            }
        )  # fmt: skip
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM one_proposals WHERE state IN ('proposed', 'approved') OR proposed_at > %s "
            "ORDER BY (state IN ('proposed', 'approved')) DESC, proposed_at DESC LIMIT 100",
            (now - dt.timedelta(days=30),),
        ).fetchall()
    ]
    people = _names(
        conn,
        sorted(
            {
                str(p[k])
                for p in rows
                for k in ("subject_user_id", "proposed_by", "decided_by", "carried_out_by")
                if p[k]
            }
        ),
    )
    messages: dict[int, list[dict[str, Any]]] = {}
    for m in conn.execute(
        "SELECT m.proposal_id, m.author_role, u.name FROM one_messages m JOIN users u ON u.id = m.author_user_id "
        "WHERE m.proposal_id = ANY(%s) ORDER BY m.written_at",
        ([p["id"] for p in rows],),
    ).fetchall():
        messages.setdefault(int(m["proposal_id"]), []).append({"from": m["author_role"], "name": m["name"]})
    invites: dict[int, list[str]] = {}
    for i in conn.execute(
        "SELECT i.proposal_id, u.name FROM one_message_invites i JOIN users u ON u.id = i.user_id "
        "WHERE i.proposal_id = ANY(%s)",
        ([p["id"] for p in rows],),
    ).fetchall():
        invites.setdefault(int(i["proposal_id"]), []).append(str(i["name"]))
    tiers = {o["id"]: o["tier"] for o in ones}
    proposals = []
    for p in rows:
        pid = p["id"]
        proposals.append(
            {
                "id": pid, "kind": p["kind"], "kind_words": KIND_WORDS[p["kind"]], "state": p["state"],
                "one_id": p["one_id"], "subject": people.get(str(p["subject_user_id"])),
                "way_in": WAY_IN_WORDS.get(p["way_in"] or ""), "idea_id": p["idea_id"],
                "tier_from": tiers.get(p["one_id"]) if p["one_id"] else None,
                "tier_to": p["tier_to"], "tier_to_name": tier_name(p["tier_to"]) if p["tier_to"] else None,
                "reason": unseal(p["reason_encrypted"], f"one_proposal:{pid}:reason"),
                "text": unseal(p["text_encrypted"], f"one_proposal:{pid}:text"),
                "proposed_by": people.get(str(p["proposed_by"])), "proposed_by_id": str(p["proposed_by"]),
                "proposed_at": _iso(p["proposed_at"]), "approval": p["approval"],
                "meeting_on": p["meeting_on"].isoformat() if p["meeting_on"] else None,
                "decided_by": people.get(str(p["decided_by"])) if p["decided_by"] else None,
                "decided_at": _iso(p["decided_at"]),
                "carried_out_by": people.get(str(p["carried_out_by"])) if p["carried_out_by"] else None,
                "messages": messages.get(pid, []), "invited": invites.get(pid, []),
                "committee_message": any(m["from"] == "committee" for m in messages.get(pid, [])),
            }
        )  # fmt: skip
    counter = conn.execute(
        "SELECT last_value FROM id_counters WHERE kind = 'ONE-NO' AND period = ''"
    ).fetchone()
    mode = conn.execute("SELECT mode FROM screen_settings WHERE id").fetchone()
    awards = [
        {"year": r["year"], "category": r["category"], "one_id": r["one_id"], "name": r["name"]}
        for r in conn.execute(
            "SELECT a.year, a.category, a.one_id, u.name FROM one_awards a JOIN ones o ON o.id = a.one_id "
            "JOIN users u ON u.id = o.user_id ORDER BY a.year DESC, a.category"
        ).fetchall()
    ]
    return {
        "ones": roster,
        "proposals": proposals,
        "resting": numbers.resting(conn, now),
        "legends": [{"number": n, "one_id": i} for i, n in sorted(legends.items(), key=lambda x: x[1])],
        "last_allocated": int(counter["last_value"]) if counter else 0,
        "screen_mode": mode["mode"] if mode else "static",
        "awards": awards,
        "active": sum(1 for o in ones if o["status"] == "active"),
    }


# --- Public: wall, home carousel, screens ---------------------------------------------------------------------------


def public(conn: Conn) -> dict[str, Any]:
    if not killswitch.is_on("ones.public", conn):
        return {"paused": True, "ones": []}
    rows = conn.execute(
        "SELECT o.*, u.name, coalesce(p.public_name_consent, false) AS consent FROM ones o "
        "JOIN users u ON u.id = o.user_id LEFT JOIN comms_prefs p ON p.user_id = o.user_id "
        "WHERE o.status = 'active' ORDER BY o.inducted_at DESC, o.id DESC"
    ).fetchall()
    out = []
    for r in rows:
        o = dict(r)
        line, stage = _idea_line(conn, o, public=True)
        brief = unseal(o["brief_encrypted"], f"one:{o['id']}:brief") if o["brief_approved_at"] else None
        out.append(
            {
                "number": o["number"], "induction_no": o["induction_no"], **_tier(o["tier"]),
                "name": o["name"] if o["consent"] else None, "founding": o["way_in"] == "founding",
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
    consent = conn.execute(
        "SELECT public_name_consent FROM comms_prefs WHERE user_id = %s", (user_id,)
    ).fetchone()
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
        "name_on_wall": bool(consent and consent["public_name_consent"]),
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


# --- Leaderboard (Ones only) and the manager's team view ------------------------------------------------------------


def _hours_a_year(m: dict[str, Any]) -> int:
    t = m.get("time") or {}
    v = int(t.get("value") or 0)
    return v * 12 if t.get("unit") == "hours a month" else v * 8


def _rupees_a_year(m: dict[str, Any]) -> int:
    x = m.get("money") or {}
    if not x.get("finance_confirmed"):
        return 0
    v = int(x.get("value") or 0)
    return v * 12 if x.get("unit") == "rupees a month" else v


def leaderboard(conn: Conn, viewer_id: str) -> dict[str, Any] | None:
    """Visible only to active Ones (DEC-077). People by tier, then measured impact (DEC-083); teams by line of
    business."""
    if not conn.execute(
        "SELECT 1 FROM ones WHERE user_id = %s AND status = 'active'", (viewer_id,)
    ).fetchone():
        return None
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT o.id, o.number, o.tier, o.measures, o.user_id, u.name, u.lob_id, "
            "coalesce(c.public_name_consent, false) AS consent FROM ones o "
            "JOIN users u ON u.id = o.user_id LEFT JOIN comms_prefs c ON c.user_id = o.user_id "
            "WHERE o.status = 'active'"
        ).fetchall()
    ]

    def score(r: dict[str, Any]) -> tuple[int, int, int, int]:
        pm = _public_measures(r["measures"])
        return (r["tier"], len(pm), _rupees_a_year(r["measures"] or {}), _hours_a_year(r["measures"] or {}))

    rows.sort(key=lambda r: (*(-x for x in score(r)), r["number"] or 0))
    _, lobs = taxonomy_names()
    people = [
        {
            "rank": i + 1, "number": r["number"], **_tier(r["tier"]),
            # A name shows only with public-name consent; everyone sees their own (DEC-077, non-negotiable 7).
            "name": r["name"] if r["consent"] or str(r["user_id"]) == viewer_id else None,
            "measures": _public_measures(r["measures"]), "you": str(r["user_id"]) == viewer_id,
        }
        for i, r in enumerate(rows)
    ]  # fmt: skip
    teams: dict[str, dict[str, Any]] = {}
    for r in rows:
        key = r["lob_id"] or "LOB-unknown"
        t = teams.setdefault(
            key, {"lob": lobs.get(key, "Other teams"), "ones": 0, "top_tier": 0, "tiers": 0, "measured": 0}
        )
        t["ones"] += 1
        t["top_tier"] = max(t["top_tier"], r["tier"])
        t["tiers"] += r["tier"]
        t["measured"] += len(_public_measures(r["measures"]))
    team_list = sorted(teams.values(), key=lambda t: (-t["top_tier"], -t["tiers"], -t["measured"], t["lob"]))
    for i, t in enumerate(team_list):
        t["rank"] = i + 1
        t["top_tier_name"] = tier_name(t["top_tier"])
    return {"people": people, "teams": team_list}


def team(conn: Conn, manager_id: str) -> dict[str, Any]:
    """A manager's direct reports: counts of what they shared and built, never the ideas' text (DEC-079)."""
    reports = conn.execute(
        "SELECT u.id, u.name FROM users u WHERE u.manager_user_id = %s AND u.active ORDER BY u.name",
        (manager_id,),
    ).fetchall()
    out = []
    for r in reports:
        counts = conn.execute(
            "SELECT count(*) FILTER (WHERE i.stage <> 'draft') AS shared, "
            "count(*) FILTER (WHERE i.stage = ANY(%s)) AS building, count(*) FILTER (WHERE i.stage = ANY(%s)) AS shipped "
            "FROM ideas i JOIN contributor_map m ON m.contributor_code = i.contributor_code WHERE m.user_id = %s",
            (list(PICKED + IN_GARAGE), list(SHIPPED), r["id"]),
        ).fetchone()
        one = conn.execute(
            "SELECT number, tier FROM ones WHERE user_id = %s AND status = 'active'", (r["id"],)
        ).fetchone()
        out.append(
            {
                "name": r["name"],
                "shared": int(counts["shared"]) if counts else 0,
                "building": int(counts["building"]) if counts else 0,
                "shipped": int(counts["shipped"]) if counts else 0,
                "one": {"number": one["number"], **_tier(one["tier"])} if one else None,
            }
        )
    totals = {k: sum(p[k] for p in out) for k in ("shared", "building", "shipped")}
    return {"people": out, "totals": totals, "ones": sum(1 for p in out if p["one"])}


def invite_view(conn: Conn, proposal_id: int, user_id: str) -> dict[str, Any] | None:
    """What a person is asked to write for a One's tier change, and as whom (DEC-084). None if they may not."""
    from ones.service import roles

    p = conn.execute(
        "SELECT p.*, o.number, u.name, coalesce(c.public_name_consent, false) AS consent FROM one_proposals p "
        "JOIN ones o ON o.id = p.one_id JOIN users u ON u.id = o.user_id "
        "LEFT JOIN comms_prefs c ON c.user_id = o.user_id WHERE p.id = %s AND p.kind IN ('tier_up', 'tier_down')",
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
    display = f"No. {p['number']}, {p['name']}" if p["consent"] else f"One No. {p['number']}"
    return {
        "one_display": display,
        "tier_to_name": tier_name(p["tier_to"]),
        "as": as_role,
        "written": written is not None,
    }
