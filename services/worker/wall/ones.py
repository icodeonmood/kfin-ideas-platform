"""The Ones (L-ONES, S-ONE, S-WALL.ones, C-ONES-FAN data, the office screen's cards).

- **Cards** (`one_cards`): number, the person (or None when they hid their name from the Wall, DEC-104), tier,
  flag and the approved brief. The Wall, Home's fan (inside each post) and the office screen read this one shape.
- **Posts** (`posts`, `like`): what Ones post about what shipped, with likes and the idea's comment count.
- **The One's own dashboard** (`dashboard`, `set_number`, `propose_brief`, `glow_up_seen`): theirs alone.
- **Becoming a One** (`induct_for_idea`): automatic once a shipped idea's impact is measured and confirmed
  (L-ONES.rules/1, DEC-102). Lane A's admin path calls it after a measurement is entered or Finance confirms one.
  `mark_founding`, `remove_one`, `approve_brief` and `decline_brief` are the admin path's other calls (DEC-106).

Numbers reuse `ones.numbers` (1 to 999, next free on induction, any free number for the window after it). Every
change is written to `audit_log` with IDs and numbers only (non-negotiables 3, 9); no text is ever logged.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from core.config import get_settings
from core.db import Conn
from gateway import AgentSwitchedOff, run_agent
from onepc.context import open_text
from onepc.enums import TIER_NAME
from ones import numbers
from ones.text import OnesRefused, _draft_scope, _verdict, seal, unseal
from pii.patterns import scan
from wall.common import (
    MSG_BRIEF,
    MSG_OUT_OF_RANGE,
    MSG_TAKEN,
    MSG_YOURS,
    Refused,
    day_label,
    person_ref,
    promise,
    public_text,
    short_ago,
    tier_label,
)
from wall.impact import (
    as_impact,
    figures_from_measures,
    hours_a_month,
    idea_impact,
    latest_figures,
    measurement_rows,
)

FLAG_LABEL = {"founding": "Founding One", "one": "One"}  # E-ENUMS.tier flags
BRIEF_MIN, BRIEF_MAX = 20, 140  # V-FIELDS.one/4
NEAR = 3  # V-FIELDS.one/2: "Free numbers near it: 6, 8, 11."
# S-ONE.layout/3, reference/copy/OneDashboard.md
MSG_KEEP = (
    "Keep No. {n}, or choose any free number from 1 to 999 until {until}. First come, first served. "
    "After that, it's yours."
)
POSTS = 12
# NOT DRAWN: the pack has no line for a brief that holds a customer's details; listed for HR's sign-off.
MSG_BRIEF_DETAILS = "Keep customers' details out of your brief."

_ONE_COLS = (
    "o.id, o.number, o.tier, o.way_in, o.status, o.idea_id, o.inducted_at, o.swap_until, o.brief_encrypted, "
    "o.brief_approved_at, o.brief_proposed_at, o.measures, o.title_encrypted, u.id AS user_id, u.name, "
    "u.first_name, u.area, u.location AS city, coalesce(ps.show_name_on_wall, true) AS shown"
)
_ONE_FROM = "FROM ones o JOIN users u ON u.id = o.user_id AND u.active LEFT JOIN person_settings ps ON ps.user_id = u.id"


def _audit(conn: Conn, actor: str, action: str, entity: str, after: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, %s, %s, %s)",
        (f"user:{actor}", action, entity, Jsonb(after)),
    )


def _flag(way_in: str) -> str:
    return "founding" if way_in == "founding" else "one"


def approved_brief(row: dict[str, Any]) -> str | None:
    if row.get("brief_approved_at") is None:
        return None
    return public_text(unseal(row["brief_encrypted"], f"one:{row['id']}:brief"))


def card(row: dict[str, Any], *, self_view: bool = False) -> dict[str, Any]:
    """E-ENTITIES OneCard, with the labels the screens show ("Tier 4, Blaze", "Founding One")."""
    shown = bool(row["shown"]) or self_view
    flag = _flag(str(row["way_in"]))
    return {
        "number": row["number"],
        "person": person_ref(row["user_id"], row["name"], row["first_name"], row["area"], row["city"])
        if shown
        else None,
        "tier": int(row["tier"]),
        "tier_name": TIER_NAME[int(row["tier"])],
        "tier_label": tier_label(int(row["tier"])),
        "flag": flag,
        "flag_label": FLAG_LABEL[flag],
        "brief": approved_brief(row) or "",
    }


def one_cards(conn: Conn, order: str = "wall") -> list[dict[str, Any]]:
    """Every active One as a card. `wall`: in the order they became Ones (Founding Ones first, as the board
    draws). `leaderboard`: by tier, then measured hours saved (the L-ONES.open default), then number."""
    rows = [
        dict(r)
        for r in conn.execute(
            f"SELECT {_ONE_COLS} {_ONE_FROM} WHERE o.status = 'active' AND o.number IS NOT NULL "
            "ORDER BY o.inducted_at, o.number"
        ).fetchall()
    ]
    if order == "leaderboard":
        hours = _hours_by_one(conn, rows)
        rows.sort(key=lambda r: (-int(r["tier"]), -hours.get(int(r["id"]), 0.0), int(r["number"])))
    elif order != "wall":
        raise Refused(400, "bad_order", field="order")
    return [card(r) for r in rows]


def _hours_by_one(conn: Conn, rows: list[dict[str, Any]]) -> dict[int, float]:
    out: dict[int, float] = {}
    for r in rows:
        figs = figures_from_measures(r["measures"])
        if r["idea_id"]:
            idea = conn.execute("SELECT id FROM ideas WHERE idea_id = %s", (r["idea_id"],)).fetchone()
            if idea is not None:
                figs = latest_figures(measurement_rows(conn, [idea["id"]]).get(str(idea["id"]), [])) or figs
        out[int(r["id"])] = hours_a_month(figs["time"]) if "time" in figs else 0.0
    return out


# --- Posts (L-ONES.rules/7, C-ONES-FAN, A-API.ones-posts) -----------------------------------------------------------


def posts(conn: Conn, viewer_id: str, now: dt.datetime, limit: int = POSTS) -> list[dict[str, Any]]:
    """`OnePost[]` for Home, newest first: the One's card, what changed, the headline figure, likes (and whether
    the viewer liked it), the idea's comment count and where its thread is."""
    rows = conn.execute(
        f"SELECT {_ONE_COLS}, p.id AS post_id, p.text_encrypted, p.figure_value, p.figure_line, p.shipped, "  # noqa: S608
        "p.adopted_by, p.posted_at, i.idea_id AS idea_ref, "
        "(SELECT count(*) FROM one_post_likes l WHERE l.post_id = p.id) AS likes, "
        "EXISTS (SELECT 1 FROM one_post_likes l WHERE l.post_id = p.id AND l.user_id = %(viewer)s) AS liked, "
        "(SELECT count(*) FROM conversation_entries e WHERE e.idea_uuid = p.idea_uuid AND e.type = 'message' "
        "AND e.deleted_at IS NULL) AS comments "
        f"FROM one_posts p JOIN ones o ON o.id = p.one_id AND o.status = 'active' AND o.number IS NOT NULL "
        "JOIN users u ON u.id = o.user_id AND u.active LEFT JOIN person_settings ps ON ps.user_id = u.id "
        "LEFT JOIN ideas i ON i.id = p.idea_uuid WHERE p.removed_at IS NULL "
        "ORDER BY p.posted_at DESC, p.id LIMIT %(limit)s",
        {"viewer": viewer_id, "limit": limit},
    ).fetchall()
    out = []
    for r in rows:
        row = dict(r)
        text = public_text(
            open_text("one_posts", "text_encrypted", str(row["post_id"]), row["text_encrypted"])
        )
        if text is None:
            continue
        post: dict[str, Any] = {
            "id": str(row["post_id"]),
            "one": card(row, self_view=str(row["user_id"]) == viewer_id),
            "text": text,
            "ago": short_ago(row["posted_at"], now),
            "shipped": bool(row["shipped"]),
            "figure": {
                "value": public_text(row["figure_value"]) or "",
                "line": public_text(row["figure_line"]) or "",
            },
            "likes": int(row["likes"]),
            "liked": bool(row["liked"]),
            "comments": int(row["comments"]),
            "thread_to": f"/ideas/{row['idea_ref']}" if row["idea_ref"] else "/wall",
        }
        if row["adopted_by"]:
            post["adopted_by"] = int(row["adopted_by"])
        out.append(post)
    return out


def like(conn: Conn, viewer_id: str, post_id: str, liked: Any) -> dict[str, Any]:
    """Like or unlike a One's post (C-ONES-FAN.card's like count). Saying the same twice changes nothing."""
    if not isinstance(liked, bool):
        raise Refused(422, "liked_required", field="liked")
    try:
        found = conn.execute(
            "SELECT p.id FROM one_posts p JOIN ones o ON o.id = p.one_id AND o.status = 'active' "
            "WHERE p.id = %s::uuid AND p.removed_at IS NULL",
            (post_id,),
        ).fetchone()
    except psycopg.errors.InvalidTextRepresentation:
        found = None
    if found is None:
        raise Refused(404, "not_found")
    if liked:
        conn.execute(
            "INSERT INTO one_post_likes (post_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (post_id, viewer_id),
        )
    else:
        conn.execute("DELETE FROM one_post_likes WHERE post_id = %s AND user_id = %s", (post_id, viewer_id))
    n = conn.execute("SELECT count(*) AS n FROM one_post_likes WHERE post_id = %s", (post_id,)).fetchone()
    return {"id": post_id, "liked": liked, "likes": int(n["n"]) if n else 0}


# --- The One's own dashboard (S-ONE) ---------------------------------------------------------------------------------


def _own(conn: Conn, user_id: str, *, lock: bool = False) -> dict[str, Any]:
    """The signed-in person's active One record, or 403 `not_a_one` (S-ONE.rules/1: others go to Profile).
    Membership is checked before anything else, so a non-One never learns what a valid request looks like."""
    row = conn.execute(
        f"SELECT {_ONE_COLS} {_ONE_FROM} WHERE o.user_id = %s AND o.status = 'active' "
        "AND o.number IS NOT NULL" + (" FOR UPDATE OF o" if lock else ""),
        (user_id,),
    ).fetchone()
    if row is None:
        raise Refused(403, "not_a_one")
    return dict(row)


def _closed(one: dict[str, Any], now: dt.datetime) -> bool:
    """After the window (30 days from becoming a One, L-ONES.rules/2) the number is theirs for good."""
    return one["swap_until"] is None or now > one["swap_until"]


def _window(one: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    """The number card (S-ONE.layout/3): open with its end date ("until 1 Dec 2026"), or closed with the line that
    replaces the field ("No. 1 is yours for good.", V-FIELDS.one/3)."""
    until = one["swap_until"]
    open_ = not _closed(one, now)
    out = {
        "open": open_,
        "until": until.isoformat() if until else None,
        "until_label": day_label(until) if until else "",
        "number": one["number"],
    }
    if open_:
        out["keep_label"] = MSG_KEEP.format(n=one["number"], until=out["until_label"])
    else:
        out["locked_label"] = MSG_YOURS.format(n=one["number"])
    return out


def _story(conn: Conn, user_id: str) -> dict[str, int]:
    row = conn.execute(
        "SELECT count(*) FILTER (WHERE i.shared_at IS NOT NULL AND i.status <> 'draft') AS shared, "
        "count(*) FILTER (WHERE i.status IN ('picked', 'being_built')) AS picked, "
        "count(*) FILTER (WHERE i.status = 'shipped') AS shipped FROM ideas i "
        "JOIN contributor_map m ON m.contributor_code = i.contributor_code WHERE m.user_id = %s",
        (user_id,),
    ).fetchone()
    return {k: int(row[k]) if row else 0 for k in ("shared", "picked", "shipped")}


def _tier_moment(conn: Conn, one: dict[str, Any], user_id: str) -> dict[str, Any] | None:
    """The glow-up waiting to play once (S-ONE.states showGlowUp): the latest unseen step up."""
    glow = conn.execute(
        "SELECT id, tier_from, tier_to, proposal_id FROM one_glow_ups WHERE one_id = %s AND seen_at IS NULL "
        "AND tier_to > tier_from ORDER BY id DESC LIMIT 1",
        (one["id"],),
    ).fetchone()
    if glow is None:
        return None
    messages = []
    if glow["proposal_id"] is not None:
        for m in conn.execute(
            "SELECT m.id, m.text_encrypted, u.name FROM one_messages m JOIN users u ON u.id = m.author_user_id "
            "WHERE m.proposal_id = %s AND m.author_role = 'committee' ORDER BY m.written_at",
            (glow["proposal_id"],),
        ).fetchall():
            text = unseal(m["text_encrypted"], f"one_message:{m['id']}")
            if text:
                messages.append({"text": text, "from_label": f"From the core committee: {m['name']}"})
    return {
        "id": int(glow["id"]),
        "from": int(glow["tier_from"]),
        "to": int(glow["tier_to"]),
        "from_label": tier_label(int(glow["tier_from"])),
        "to_label": tier_label(int(glow["tier_to"])),
        # "No. 17, your spark is hotter" / "From Tier 1, Spark to Tier 2, Glow" (L-ONES.rules/3, S-ONE.states)
        "title": f"No. {one['number']}, your spark is hotter",
        "line": f"From {tier_label(int(glow['tier_from']))} to {tier_label(int(glow['tier_to']))}",
        "story": _story(conn, user_id),
        "messages": messages,
    }


def _idea(conn: Conn, one: dict[str, Any]) -> tuple[dict[str, Any] | None, Any]:
    if one["idea_id"]:
        row = conn.execute(
            "SELECT id, idea_id, title, status FROM ideas WHERE idea_id = %s", (one["idea_id"],)
        ).fetchone()
        if row is not None:
            return {"id": row["idea_id"], "title": row["title"] or "", "status": row["status"]}, row["id"]
    title = unseal(one["title_encrypted"], f"one:{one['id']}:title")
    return ({"id": None, "title": title, "status": None} if title else None), None


def dashboard(conn: Conn, user_id: str, now: dt.datetime | None = None) -> dict[str, Any]:
    """`GET /one` (A-API.wall): the One's card, idea, impact (four measures), number window, brief and any tier
    moment waiting to play. Reading it changes nothing (the moment is marked seen by its own call)."""
    now = now or dt.datetime.now(dt.UTC)
    one = _own(conn, user_id)
    idea, idea_uuid = _idea(conn, one)
    impact = idea_impact(conn, idea_uuid) if idea_uuid is not None else {}
    if not impact:
        impact = as_impact(figures_from_measures(one["measures"]))
    proposed = one["brief_proposed_at"] is not None
    c = card(one, self_view=True)
    since = day_label(one["inducted_at"])
    return {
        "one": c,
        "since": one["inducted_at"].isoformat(),
        "since_label": since,
        # "You're No. 1" / "Tier 4, Blaze. Founding One since 1 Nov 2026." (S-ONE.layout/2)
        "headline": f"You're No. {one['number']}",
        "since_line": f"{c['tier_label']}. {c['flag_label']} since {since}.",
        "idea": idea,
        "impact": impact,
        "number_window": _window(one, now),
        "brief": {"text": approved_brief(one), "pending": proposed},
        "tier_moment": _tier_moment(conn, one, user_id),
    }


def _whole(value: Any) -> int:
    """A whole number from 1 to 999, or 422 out_of_range (V-FIELDS.one/1)."""
    if isinstance(value, bool):
        raise Refused(422, "out_of_range", MSG_OUT_OF_RANGE, field="number")
    if isinstance(value, str) and re.fullmatch(r"\s*\d{1,3}\s*", value):
        value = int(value)
    if not isinstance(value, int) or not numbers.LOW <= value <= numbers.HIGH:
        raise Refused(422, "out_of_range", MSG_OUT_OF_RANGE, field="number")
    return value


def nearest_free(conn: Conn, n: int, one_id: int, now: dt.datetime, count: int = NEAR) -> list[int]:
    """The free numbers nearest `n`, smallest first ("Free numbers near it: 6, 8, 11"). Free as `ones.numbers`
    says: nobody wears it (this One's own number counts as worn), it is not resting for someone else."""
    rows = conn.execute(
        "SELECT g FROM generate_series(%(low)s::int, %(high)s::int) AS g "
        "WHERE g NOT IN (SELECT number FROM ones WHERE number IS NOT NULL) "
        "AND g NOT IN (SELECT number FROM one_number_history WHERE rests_until > %(now)s AND one_id <> %(one)s) "
        "AND g NOT IN (SELECT number FROM one_legend_numbers WHERE one_id <> %(one)s) "
        "ORDER BY abs(g - %(n)s), g LIMIT %(count)s",
        {"low": numbers.LOW, "high": numbers.HIGH, "now": now, "one": one_id, "n": n, "count": count},
    ).fetchall()
    return sorted(int(r["g"]) for r in rows)


def _taken(conn: Conn, n: int, one_id: int, now: dt.datetime) -> Refused:
    near = nearest_free(conn, n, one_id, now)
    return Refused(
        409, "taken", MSG_TAKEN.format(n=n, near=", ".join(str(x) for x in near)), field="number", near=near
    )


def set_number(conn: Conn, user_id: str, number: Any, now: dt.datetime | None = None) -> dict[str, Any]:
    """`PUT /one/number` (L-ONES.rules/2, V-FIELDS.one/1–3): any free number 1 to 999 inside the window after
    becoming a One, first come first served; after that the field is locked. Returns the number window."""
    now = now or dt.datetime.now(dt.UTC)
    first = _own(conn, user_id)  # membership first (BLD-108)
    if _closed(first, now):  # V-FIELDS.one/3: a closed window answers the same whatever was typed
        raise Refused(409, "window_closed", MSG_YOURS.format(n=first["number"]), field="number")
    n = _whole(number)
    try:
        with conn.transaction():
            one = _own(conn, user_id, lock=True)
            if _closed(one, now):
                raise Refused(409, "window_closed", MSG_YOURS.format(n=one["number"]), field="number")
            if one["number"] != n:
                if not numbers.is_free(conn, n, int(one["id"]), now):
                    raise _taken(conn, n, int(one["id"]), now)
                numbers.wear(conn, int(one["id"]), n, "chosen", now)
                conn.execute("UPDATE ones SET number = %s WHERE id = %s", (n, one["id"]))
                _audit(
                    conn, user_id, "ones.number_changed", f"one:{one['id']}", {"from": one["number"], "to": n}
                )
            one["number"] = n
    except psycopg.errors.UniqueViolation:
        # Someone claimed it in the same moment: the unique index settled it.
        raise _taken(conn, n, int(_own(conn, user_id)["id"]), now) from None
    return {"number_window": _window(one, now)}


def _check_brief(conn: Conn, text: Any) -> str:
    """V-FIELDS.one/4: one sentence, 20 to 140 characters; then the hidden-detail patterns (always) and the
    gatekeeper through the gateway when the assistant is on (V-FIELDS/5). With the assistant switched off (D1
    open, DEC-105) the patterns stand alone: the brief still goes to the programme team before anyone sees it."""
    clean = " ".join(str(text or "").split()) if isinstance(text, str) else ""
    if not BRIEF_MIN <= len(clean) <= BRIEF_MAX or re.search(r"[.!?]\s+\S", clean):
        raise Refused(422, "brief_invalid", MSG_BRIEF, field="text")
    if any(m.action == "block" for m in scan(clean, kfin_domains=get_settings().kfin_domains)):
        raise Refused(422, "personal_data", MSG_BRIEF_DETAILS, field="text")
    try:
        gk = run_agent(
            "gatekeeper",
            {"mode": "submission", "submission": {"choice_text": clean}},
            _draft_scope(),
            conn=conn,
        )
        _verdict(gk.data)
    except AgentSwitchedOff:
        pass
    except OnesRefused as exc:
        raise Refused(422, exc.code, MSG_BRIEF_DETAILS, field="text") from None
    return clean


def propose_brief(conn: Conn, user_id: str, text: Any, now: dt.datetime | None = None) -> dict[str, Any]:
    """`POST /one/brief` (L-ONES.rules/5): the One proposes a new brief; it goes live once the programme team
    approves it (`approve_brief`). A new proposal replaces one still waiting. Run the checks before the write:
    the gatekeeper is a model call."""
    now = now or dt.datetime.now(dt.UTC)
    one = _own(conn, user_id)
    brief = _check_brief(conn, text)
    with conn.transaction():
        conn.execute(
            "UPDATE ones SET brief_proposed_encrypted = %s, brief_proposed_at = %s WHERE id = %s",
            (seal(brief, f"one:{one['id']}:brief_proposed"), now, one["id"]),
        )
        _audit(conn, user_id, "ones.brief_proposed", f"one:{one['id']}", {"one_id": one["id"]})
    return {"brief": {"text": approved_brief(one), "pending": True}}


def glow_up_seen(conn: Conn, user_id: str, glow_id: Any, now: dt.datetime | None = None) -> dict[str, Any]:
    """The tier moment has played; it never plays again (S-ONE.rules/3). Every unseen one of theirs goes with it."""
    now = now or dt.datetime.now(dt.UTC)
    one = _own(conn, user_id)
    try:
        gid = int(glow_id)
    except (TypeError, ValueError):
        raise Refused(404, "not_found") from None
    owned = conn.execute(
        "SELECT 1 FROM one_glow_ups WHERE id = %s AND one_id = %s", (gid, one["id"])
    ).fetchone()
    if owned is None:
        raise Refused(404, "not_found")
    conn.execute(
        "UPDATE one_glow_ups SET seen_at = %s WHERE one_id = %s AND seen_at IS NULL", (now, one["id"])
    )
    return {"seen": True}


# --- Becoming a One, and the admin path (L-ONES.rules/1, DEC-106) -------------------------------------------------


def credited_users(conn: Conn, idea_uuid: Any) -> list[str]:
    """Everyone credited on an idea (E-ENTITIES Idea.credited): its sharer, and after a merge the sharer of each
    idea merged into it (a reversed merge no longer counts). Active people only."""
    rows = conn.execute(
        "SELECT DISTINCT m.user_id FROM ideas i JOIN contributor_map m ON m.contributor_code = i.contributor_code "
        "JOIN users u ON u.id = m.user_id AND u.active WHERE i.id = %(idea)s OR i.id IN (SELECT merged_idea_uuid "
        "FROM merges WHERE lead_idea_uuid = %(idea)s AND reversed_at IS NULL)",
        {"idea": str(idea_uuid)},
    ).fetchall()
    return sorted(str(r["user_id"]) for r in rows)


def impact_confirmed(conn: Conn, idea_uuid: Any) -> bool:
    """Measured and confirmed (L-IMPACT/3): at least one entered figure that counts, money only once Finance has
    confirmed it."""
    return bool(latest_figures(measurement_rows(conn, [idea_uuid]).get(str(idea_uuid), [])))


def _new_one(conn: Conn, user_id: str, way_in: str, idea_ref: str | None, now: dt.datetime) -> dict[str, Any]:
    window = dt.timedelta(days=promise("ones", "number_change_days", 30))
    n = conn.execute("SELECT next_number('ONE', '') AS n").fetchone()
    assert n is not None
    number = numbers.next_number(conn, 0, now)
    row = conn.execute(
        "INSERT INTO ones (induction_no, user_id, number, way_in, idea_id, inducted_at, swap_until) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (n["n"], user_id, number, way_in, idea_ref, now, now + window),
    ).fetchone()
    assert row is not None
    numbers.wear(conn, int(row["id"]), number, "allocated", now)
    return {"user_id": user_id, "one_id": int(row["id"]), "number": number}


def induct_for_idea(
    conn: Conn, idea_uuid: Any, *, actor: str, now: dt.datetime | None = None
) -> list[dict[str, Any]]:
    """L-ONES.rules/1: once an idea has shipped and its impact is measured and confirmed, everyone credited on it
    who is not already a One becomes one, with the next free number and the number window. Idempotent: call it
    after every measurement or Finance confirmation; nothing happens until the rules hold.

    A person an admin removed (`remove_one`) is not brought back automatically: the admin's call stands, and
    `mark_founding` or a fresh admin action is the way back. Runs in the caller's transaction (a savepoint per
    person). Returns who became a One: `[{user_id, one_id, number}]`. `actor` is the admin's users.id (audit)."""
    now = now or dt.datetime.now(dt.UTC)
    idea = conn.execute("SELECT id, idea_id, status FROM ideas WHERE id = %s", (str(idea_uuid),)).fetchone()
    if idea is None or idea["status"] != "shipped" or not impact_confirmed(conn, idea_uuid):
        return []
    made = []
    for user_id in credited_users(conn, idea_uuid):
        with conn.transaction():
            existing = conn.execute(
                "SELECT id FROM ones WHERE user_id = %s FOR UPDATE", (user_id,)
            ).fetchone()
            if existing is not None:
                continue  # already a One, or removed by an admin
            one = _new_one(conn, user_id, "accepted_idea", idea["idea_id"], now)
            _audit(conn, actor, "ones.inducted", f"one:{one['one_id']}",
                   {"idea_id": idea["idea_id"], "number": one["number"], "how": "measured_impact"})  # fmt: skip
            made.append(one)
    return made


def _need_admin(conn: Conn, actor: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM role_grants g JOIN users u ON u.id = g.user_id AND u.active WHERE g.user_id = %s "
        "AND g.role = 'admin' AND g.valid_from <= now() AND (g.valid_to IS NULL OR g.valid_to > now())",
        (actor,),
    ).fetchone()
    if row is None:
        raise Refused(403, "forbidden")


def mark_founding(conn: Conn, actor: str, user_id: str, now: dt.datetime | None = None) -> dict[str, Any]:
    """An admin marks a Founding One (DEC-102, DEC-106): a One already keeps their number and gets the flag; anyone
    else becomes a One with the next free number. Logged."""
    now = now or dt.datetime.now(dt.UTC)
    _need_admin(conn, actor)
    with conn.transaction():
        if conn.execute("SELECT 1 FROM users WHERE id = %s AND active", (user_id,)).fetchone() is None:
            raise Refused(404, "not_found")
        existing = conn.execute("SELECT * FROM ones WHERE user_id = %s FOR UPDATE", (user_id,)).fetchone()
        if existing is not None and existing["status"] == "active":
            conn.execute("UPDATE ones SET way_in = 'founding' WHERE id = %s", (existing["id"],))
            out = {"user_id": user_id, "one_id": int(existing["id"]), "number": existing["number"]}
        elif existing is not None:  # a removed One comes back to the same record
            window = dt.timedelta(days=promise("ones", "number_change_days", 30))
            number = numbers.next_number(conn, int(existing["id"]), now)
            conn.execute(
                "UPDATE ones SET status = 'active', number = %s, way_in = 'founding', inducted_at = %s, "
                "swap_until = %s, retired_at = NULL WHERE id = %s",
                (number, now, now + window, existing["id"]),
            )
            numbers.wear(conn, int(existing["id"]), number, "allocated", now)
            out = {"user_id": user_id, "one_id": int(existing["id"]), "number": number}
        else:
            out = _new_one(conn, user_id, "founding", None, now)
        _audit(conn, actor, "ones.founding_marked", f"one:{out['one_id']}", {"number": out["number"]})
    return out


def remove_one(conn: Conn, actor: str, user_id: str, now: dt.datetime | None = None) -> dict[str, Any]:
    """An admin removes a One (DEC-106): their number is freed (it rests, as `ones.numbers` says), their card and
    posts leave the Wall, Home and the office screen. Logged."""
    now = now or dt.datetime.now(dt.UTC)
    _need_admin(conn, actor)
    with conn.transaction():
        one = conn.execute(
            "SELECT * FROM ones WHERE user_id = %s AND status = 'active' FOR UPDATE", (user_id,)
        ).fetchone()
        if one is None:
            raise Refused(404, "not_found")
        numbers.release(conn, int(one["id"]), now)
        conn.execute(
            "UPDATE ones SET status = 'retired', number = NULL, retired_at = %s WHERE id = %s",
            (now, one["id"]),
        )
        _audit(conn, actor, "ones.removed", f"one:{one['id']}", {"number": one["number"]})
    return {"user_id": user_id, "one_id": int(one["id"]), "removed": True}


def approve_brief(conn: Conn, actor: str, one_id: int, now: dt.datetime | None = None) -> dict[str, Any]:
    """The programme team approves a proposed brief (L-ONES.rules/5): it goes live on the Wall and the office
    screen. Logged."""
    now = now or dt.datetime.now(dt.UTC)
    _need_admin(conn, actor)
    with conn.transaction():
        one = conn.execute("SELECT * FROM ones WHERE id = %s FOR UPDATE", (one_id,)).fetchone()
        if one is None or one["brief_proposed_at"] is None:
            raise Refused(404, "not_found")
        text = unseal(one["brief_proposed_encrypted"], f"one:{one_id}:brief_proposed")
        if text is None:
            raise Refused(409, "brief_unreadable")
        conn.execute(
            "UPDATE ones SET brief_encrypted = %s, brief_approved_at = %s, brief_proposed_encrypted = NULL, "
            "brief_proposed_at = NULL WHERE id = %s",
            (seal(text, f"one:{one_id}:brief"), now, one_id),
        )
        _audit(conn, actor, "ones.brief_approved", f"one:{one_id}", {"one_id": one_id})
    return {"one_id": one_id, "approved": True}


def decline_brief(conn: Conn, actor: str, one_id: int) -> dict[str, Any]:
    """The programme team does not take a proposed brief; the live one stays. Logged."""
    _need_admin(conn, actor)
    with conn.transaction():
        done = conn.execute(
            "UPDATE ones SET brief_proposed_encrypted = NULL, brief_proposed_at = NULL WHERE id = %s "
            "AND brief_proposed_at IS NOT NULL RETURNING id",
            (one_id,),
        ).fetchone()
        if done is None:
            raise Refused(404, "not_found")
        _audit(conn, actor, "ones.brief_declined", f"one:{one_id}", {"one_id": one_id})
    return {"one_id": one_id, "declined": True}
