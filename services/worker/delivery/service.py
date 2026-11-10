"""Delivery (§4.8 to §4.11): from a picked idea or cluster to a closed, measured result.

1. **Handover.** A core committee member or an admin starts the handover for a picked idea or cluster (the committee
   flow calls `start_from_pick` itself once it is built). The owner completes the pack: track, owner, sponsor, the
   delivery PM, the success metric (name, baseline, target, unit), spend reference and the checklist. The owner
   submits it; the named sponsor approves it (one click, logged). The stage moves to `in_garage` (build or
   procurement) or `in_fix_track`.
2. **Delivery status.** Live sync with the delivery pipeline is coming soon (§4.9): until then an admin links the
   pipeline page by hand and the PM or an admin records each phase and the gate status. Every change notifies the
   contributors, the owner and the sponsor. `shipped` ships it.
3. **Fix track** (§4.10). The owner keeps an action plan of milestones; reminders come from `delivery.tick`. The owner
   submits before-and-after numbers; the sponsor approves; the stage becomes `resolved`.
4. **Measure and close** (§4.11). Shipping or resolving opens two measurements, at 30 and 90 days. The owner fills
   them; the sponsor confirms (never their own entry). Money shows only once an admin records Finance's
   confirmation (DEC-071). The 90-day confirmation closes it, with "target met" or "target not met"; contributors
   lose nothing either way. Confirmed results feed the Ones' measured impact (wall, home, screens, leaderboard).

People decide every step; no agent moves anything (non-negotiable 5). Free text (the metric's name, the objective,
milestone titles, notes) passes the patterns and the gatekeeper first and is stored encrypted; packs and results hold
codes, numbers and booleans only. Every step is audited with IDs and codes; no text is logged.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from comms.route import emit
from core.db import Conn
from delivery.phases import (
    COMPLIANCE_TIERS,
    FEATURE_TYPES,
    GATE_STATUS,
    METRIC_UNITS,
    PHASE_IDS,
    PRODUCTS,
    TRACKS,
    plain_step,
)
from ones.service import MAX_MEASURE, MEASURE_UNITS, roles
from ones.text import OnesRefused, checked, seal
from sla.calendar import add_working_days

Refused = OnesRefused  # one refusal type across the committee's tools: a safe code, never text

MARKS = {"day_30": 30, "day_90": 90}
CHECKLIST = ("working_group_formed", "baseline_captured", "build_slot_confirmed", "dev_slot_confirmed")
SPEND_REF = re.compile(r"^[A-Z0-9][A-Z0-9/-]{2,30}$")
COMMITTEE = {"core_committee", "core_chair"}
SPONSOR_ROLES = {"sponsor", "ceo"}
FLOW_STAGES = (
    "in_cluster", "ready_for_scoring", "scored", "shortlisted", "presenting", "picked", "handover", "in_garage", "in_fix_track",
    "shipped", "resolved", "measuring",
)  # fmt: skip
MAX_NUMBER = 10**12
PACK_FIELDS = frozenset({
    "track", "product", "feature_type", "compliance_tier", "unit", "baseline", "target", "spend", "checklist",
    "owner_email", "sponsor_email", "pm_email", "metric", "objective",
})  # fmt: skip
FILL_EARLY_WD = 2  # a result can be entered from two working days before its mark (BLD-127)


# --- Helpers ---------------------------------------------------------------------------------------------------


def _audit(conn: Conn, actor: str, action: str, entity: str, after: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, %s, %s, %s)",
        (actor if actor.startswith(("user:", "process:")) else f"user:{actor}", action, entity, Jsonb(after)),
    )


def _delivery(conn: Conn, delivery_id: Any, *, lock: bool = False) -> dict[str, Any]:
    try:
        did = int(delivery_id)
    except (TypeError, ValueError):
        raise Refused(404, "not_found") from None
    if lock:
        row = conn.execute("SELECT * FROM deliveries WHERE id = %s FOR UPDATE", (did,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM deliveries WHERE id = %s", (did,)).fetchone()
    if row is None:
        raise Refused(404, "not_found")
    return dict(row)


def _user_by_email(conn: Conn, email: Any, code: str) -> str:
    row = conn.execute(
        "SELECT id FROM users WHERE lower(email) = lower(%s) AND active", (str(email or "").strip(),)
    ).fetchone()
    if row is None:
        raise Refused(422, code)
    return str(row["id"])


def _number(value: Any, code: str, *, minimum: float = 0) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise Refused(422, code) from None
    if n != n or not minimum <= n <= MAX_NUMBER:  # NaN or out of range
        raise Refused(422, code)
    return int(n) if n.is_integer() else round(n, 2)


def _date(value: Any, code: str) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        raise Refused(422, code) from None


def is_party(d: dict[str, Any], user_id: str) -> bool:
    return user_id in {str(d.get("owner_user_id")), str(d.get("sponsor_user_id")), str(d.get("pm_user_id"))}


def can_see(conn: Conn, d: dict[str, Any], user_id: str, have: set[str] | None = None) -> bool:
    have = have if have is not None else roles(conn, user_id)
    if have & ({"admin"} | COMMITTEE) or is_party(d, user_id):
        return True
    return (
        conn.execute(
            "SELECT 1 FROM delivery_milestones WHERE delivery_id = %s AND owner_user_id = %s",
            (d["id"], user_id),
        ).fetchone()
        is not None
    )


def subject_ideas(conn: Conn, subject_type: str, subject_id: str) -> list[str]:
    """The idea IDs a delivery covers: the idea itself, or every member of the cluster."""
    if subject_type == "idea":
        return [subject_id]
    rows = conn.execute(
        "SELECT idea_id FROM ideas WHERE cluster_id = %s AND idea_id IS NOT NULL", (subject_id,)
    )
    return [str(r["idea_id"]) for r in rows.fetchall()]


def _set_stage(conn: Conn, d: dict[str, Any], stage: str) -> None:
    """Move the idea (or the cluster and every member idea in the decision flow) and record it in each idea's file."""
    if d["subject_type"] == "cluster":
        conn.execute("UPDATE clusters SET stage = %s WHERE id = %s", (stage, d["subject_id"]))
        ideas = [
            str(r["idea_id"])
            for r in conn.execute(
                "UPDATE ideas SET stage = %s WHERE cluster_id = %s AND stage = ANY(%s) RETURNING idea_id",
                (stage, d["subject_id"], list(FLOW_STAGES)),
            ).fetchall()
        ]
    else:
        conn.execute("UPDATE ideas SET stage = %s WHERE idea_id = %s", (stage, d["subject_id"]))
        ideas = [d["subject_id"]]
    for idea_id in ideas:
        conn.execute(
            "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES ('idea.stage_changed', %s, "
            "'process:delivery', %s)",
            (idea_id, Jsonb({"history": [{"event": stage, "by": "process:delivery"}]})),
        )


def _notify(conn: Conn, d: dict[str, Any], event: str, extra: dict[str, Any] | None = None) -> None:
    """Contributors (submitter or cluster members), the owner, the sponsor and the PM. IDs and codes only."""
    people = sorted({str(u) for u in (d["owner_user_id"], d["sponsor_user_id"], d["pm_user_id"]) if u})
    refs: dict[str, Any] = {
        "delivery_id": d["id"], "subject_id": d["subject_id"], "target_id": d["subject_id"], "joiner_code": "",
        "current_owner_ids": people, **(extra or {}),
    }  # fmt: skip
    if d["subject_type"] == "idea":
        refs["idea_id"] = d["subject_id"]
    else:
        refs["cluster_id"] = d["subject_id"]  # every member idea's owner and everyone who joined the group
    emit(conn, event, refs)


def _role_users(conn: Conn, role: str) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT g.user_id FROM role_grants g JOIN users u ON u.id = g.user_id WHERE g.role = %s "
        "AND u.active AND g.valid_from <= now() AND (g.valid_to IS NULL OR g.valid_to > now())",
        (role,),
    ).fetchall()
    return [str(r["user_id"]) for r in rows]


def target_met(baseline: Any, target: Any, actual: Any) -> bool | None:
    """Did the actual reach the target, in the direction the target set from the baseline?"""
    try:
        b, t, a = float(baseline), float(target), float(actual)
    except (TypeError, ValueError):
        return None
    return a >= t if t >= b else a <= t


# --- 1. Handover -----------------------------------------------------------------------------------------------


def _subject(conn: Conn, subject_type: Any, subject_id: Any) -> tuple[str, str, str]:
    st = str(subject_type or "")
    sid = str(subject_id or "").strip().upper()
    if st == "idea" and re.fullmatch(r"IDEA-[0-9]{4}-[0-9]{6}", sid):
        row = conn.execute("SELECT stage FROM ideas WHERE idea_id = %s", (sid,)).fetchone()
    elif st == "cluster" and re.fullmatch(r"CL-[0-9]{4}", sid):
        row = conn.execute("SELECT stage FROM clusters WHERE id = %s", (sid,)).fetchone()
    else:
        raise Refused(400, "subject_required")
    if row is None:
        raise Refused(404, "subject_not_found")
    return st, sid, str(row["stage"])


def _insert(conn: Conn, st: str, sid: str, track: str, actor_id: str | None) -> dict[str, Any]:
    pack = {
        "product": "other", "feature_type": "kfintech-product", "compliance_tier": "standard", "unit": None,
        "baseline": None, "target": None, "spend": None, "checklist": dict.fromkeys(CHECKLIST, False),
    }  # fmt: skip
    row = conn.execute(
        "INSERT INTO deliveries (subject_type, subject_id, track, pack, slug, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
        (st, sid, track, Jsonb(pack), sid.lower(), actor_id),
    ).fetchone()
    assert row is not None
    d = dict(row)
    _set_stage(conn, d, "handover")
    return d


def start(conn: Conn, actor: str, body: dict[str, Any]) -> dict[str, Any]:
    """A core committee member or an admin starts the handover for a picked idea or cluster."""
    if not roles(conn, actor) & (COMMITTEE | {"admin"}):
        raise Refused(403, "forbidden")
    track = body.get("track") or "build"
    if track not in TRACKS:
        raise Refused(422, "track_not_valid")
    with conn.transaction():
        st, sid, stage = _subject(conn, body.get("subject_type"), body.get("subject_id"))
        existing = conn.execute(
            "SELECT id FROM deliveries WHERE subject_type = %s AND subject_id = %s", (st, sid)
        ).fetchone()
        if existing:
            raise Refused(409, "already_started")
        if stage != "picked":
            raise Refused(409, "not_picked")
        try:
            with conn.transaction():  # a savepoint: a start that lost a race answers 409, not 500
                d = _insert(conn, st, sid, str(track), actor)
        except psycopg.errors.UniqueViolation:
            raise Refused(409, "already_started") from None
        _audit(conn, actor, "delivery.started", f"delivery:{d['id']}", {"subject": sid, "track": track})
    return {"id": d["id"]}


def start_from_pick(conn: Conn, subject_type: str, subject_id: str, track: str = "build") -> int:
    """For the committee flow: open the handover the moment the core committee picks an idea or cluster. Call it
    inside the transaction that records the decision: it opens no transaction of its own and never commits, only
    a savepoint around the insert. Idempotent: a second call (or one that loses a race) returns the existing
    delivery. The subject and its member ideas still in the decision flow (`in_cluster` included) move to
    handover (BLD-126)."""
    st, sid, stage = _subject(conn, subject_type, subject_id)

    def existing() -> int | None:
        row = conn.execute(
            "SELECT id FROM deliveries WHERE subject_type = %s AND subject_id = %s", (st, sid)
        ).fetchone()
        return int(row["id"]) if row else None

    found = existing()
    if found is not None:
        return found
    if stage != "picked":
        raise Refused(409, "not_picked")
    try:
        with conn.transaction():  # a savepoint inside the caller's transaction
            d = _insert(conn, st, sid, track if track in TRACKS else "build", None)
    except psycopg.errors.UniqueViolation:
        found = existing()
        if found is None:
            raise Refused(409, "already_started") from None
        return found
    _audit(
        conn, "process:committee", "delivery.started", f"delivery:{d['id']}", {"subject": sid, "track": track}
    )
    return int(d["id"])


def _can_edit(have: set[str], d: dict[str, Any], actor: str) -> bool:
    if "admin" in have or actor in {str(d.get("owner_user_id")), str(d.get("sponsor_user_id"))}:
        return True
    return d.get("owner_user_id") is None and bool(have & COMMITTEE)  # before an owner is named


def save_pack(conn: Conn, actor: str, delivery_id: Any, body: dict[str, Any]) -> dict[str, Any]:
    """The owner (or an admin) completes the pack. Text checks run first, outside the transaction."""
    have = roles(conn, actor)
    d = _delivery(conn, delivery_id)
    if not can_see(conn, d, actor, have):
        raise Refused(404, "not_found")
    if not _can_edit(have, d, actor):
        raise Refused(403, "forbidden")
    if d["state"] not in ("drafting", "awaiting_sponsor"):
        raise Refused(409, "pack_locked")
    pack = dict(d["pack"] or {})
    updates: dict[str, Any] = {}
    if "track" in body:
        if body["track"] not in TRACKS:
            raise Refused(422, "track_not_valid")
        updates["track"] = body["track"]
    for key, allowed in (
        ("product", PRODUCTS),
        ("feature_type", FEATURE_TYPES),
        ("compliance_tier", COMPLIANCE_TIERS),
    ):
        if key in body:
            if body[key] not in allowed:
                raise Refused(422, f"{key}_not_valid")
            pack[key] = body[key]
    if "unit" in body:
        if body["unit"] not in METRIC_UNITS:
            raise Refused(422, "unit_not_valid")
        pack["unit"] = body["unit"]
    for key in ("baseline", "target"):
        if key in body:
            pack[key] = None if body[key] in (None, "") else _number(body[key], f"{key}_not_valid")
    if "spend" in body:
        spend = str(body.get("spend") or "").strip().upper()
        if spend not in ("", "NONE") and not SPEND_REF.fullmatch(spend):
            raise Refused(422, "spend_not_valid")
        pack["spend"] = None if spend == "" else ("none" if spend == "NONE" else spend)
    if "checklist" in body:
        given = body.get("checklist") or {}
        if not isinstance(given, dict):
            raise Refused(422, "checklist_not_valid")
        pack["checklist"] = {
            k: given.get(k, (pack.get("checklist") or {}).get(k, False)) is True for k in CHECKLIST
        }
    people: dict[str, str | None] = {}
    for key, code in (("owner", "owner_not_found"), ("sponsor", "sponsor_not_found"), ("pm", "pm_not_found")):
        if f"{key}_email" in body:
            email = str(body.get(f"{key}_email") or "").strip()
            people[f"{key}_user_id"] = _user_by_email(conn, email, code) if email else None
    if people.get("sponsor_user_id") and not roles(conn, str(people["sponsor_user_id"])) & SPONSOR_ROLES:
        raise Refused(422, "sponsor_not_a_sponsor")
    owner = people.get("owner_user_id", d.get("owner_user_id"))
    sponsor = people.get("sponsor_user_id", d.get("sponsor_user_id"))
    if owner and sponsor and str(owner) == str(sponsor):
        raise Refused(422, "owner_is_sponsor")  # the sponsor approves the owner's work, so they must differ
    metric = checked(conn, body["metric"], min_chars=5, max_chars=120) if body.get("metric") else None
    objective = (
        checked(conn, body["objective"], min_chars=10, max_chars=400) if body.get("objective") else None
    )

    with conn.transaction():
        d = _delivery(conn, d["id"], lock=True)
        if d["state"] not in ("drafting", "awaiting_sponsor"):
            raise Refused(409, "pack_locked")
        sets = ["pack = %s", "state = 'drafting'"]
        args: list[Any] = [Jsonb(pack)]
        for col, value in {**updates, **people}.items():
            sets.append(f"{col} = %s")
            args.append(value)
        if metric is not None:
            sets.append("metric_encrypted = %s")
            args.append(seal(metric, f"delivery:{d['id']}:metric"))
        if objective is not None:
            sets.append("objective_encrypted = %s")
            args.append(seal(objective, f"delivery:{d['id']}:objective"))
        conn.execute(f"UPDATE deliveries SET {', '.join(sets)} WHERE id = %s", (*args, d["id"]))  # noqa: S608
        _audit(
            conn,
            actor,
            "delivery.pack_saved",
            f"delivery:{d['id']}",
            {"keys": sorted(PACK_FIELDS & set(body))},
        )
    return {"id": d["id"], "state": "drafting"}


def missing(d: dict[str, Any]) -> list[str]:
    """What the pack still needs before the sponsor can approve it (§4.8 step 2)."""
    pack = d["pack"] or {}
    checklist = pack.get("checklist") or {}
    out = [k for k in ("owner_user_id", "sponsor_user_id") if not d.get(k)]
    if d.get("metric_encrypted") is None:
        out.append("metric")
    out += [k for k in ("baseline", "target", "unit") if pack.get(k) in (None, "")]
    if not pack.get("spend"):
        out.append("spend")
    if not checklist.get("working_group_formed"):
        out.append("working_group_formed")
    if not checklist.get("baseline_captured"):
        out.append("baseline_captured")
    if d["track"] in ("build", "procurement"):
        if not d.get("pm_user_id"):
            out.append("pm_user_id")
        if not checklist.get("build_slot_confirmed"):
            out.append("build_slot_confirmed")
        if pack.get("feature_type") == "kfintech-product" and not checklist.get("dev_slot_confirmed"):
            out.append("dev_slot_confirmed")
    if d["track"] == "fix" and d.get("objective_encrypted") is None:
        out.append("objective")
    return out


def submit(conn: Conn, actor: str, delivery_id: Any) -> dict[str, Any]:
    have = roles(conn, actor)
    with conn.transaction():
        d = _delivery(conn, delivery_id, lock=True)
        if not can_see(conn, d, actor, have):
            raise Refused(404, "not_found")
        if "admin" not in have and actor != str(d.get("owner_user_id")):
            raise Refused(403, "forbidden")
        if d["state"] != "drafting":
            raise Refused(409, "not_drafting")
        gaps = missing(d)
        if gaps:
            raise Refused(422, "pack_incomplete:" + ",".join(gaps))
        conn.execute(
            "UPDATE deliveries SET state = 'awaiting_sponsor', submitted_by = %s WHERE id = %s",
            (actor, d["id"]),
        )
        emit(
            conn,
            "delivery.approval_needed",
            {
                "delivery_id": d["id"],
                "subject_id": d["subject_id"],
                "current_owner_ids": [str(d["sponsor_user_id"])],
            },
        )
        _audit(conn, actor, "delivery.submitted", f"delivery:{d['id']}", {})
    return {"id": d["id"], "state": "awaiting_sponsor"}


def _sponsor_check(conn: Conn, d: dict[str, Any], actor: str, have: set[str]) -> None:
    if not can_see(conn, d, actor, have):
        raise Refused(404, "not_found")
    if actor != str(d.get("sponsor_user_id")) or not have & SPONSOR_ROLES:
        raise Refused(403, "sponsor_only")


def approve(conn: Conn, actor: str, delivery_id: Any, now: dt.datetime | None = None) -> dict[str, Any]:
    """The named sponsor approves the pack (§4.8 step 3). The stage moves on; the delivery starts."""
    now = now or dt.datetime.now(dt.UTC)
    have = roles(conn, actor)
    with conn.transaction():
        d = _delivery(conn, delivery_id, lock=True)
        _sponsor_check(conn, d, actor, have)
        if d["state"] != "awaiting_sponsor":
            raise Refused(409, "not_awaiting_sponsor")
        if str(d.get("submitted_by")) == actor:
            raise Refused(403, "own_submission")  # the person who sent the pack never approves it (BLD-126)
        gaps = missing(d)
        if gaps:
            raise Refused(422, "pack_incomplete:" + ",".join(gaps))
        link = "manual" if d["track"] in ("build", "procurement") else "none"
        conn.execute(
            "UPDATE deliveries SET state = 'in_delivery', sponsor_approved_by = %s, sponsor_approved_at = %s, "
            "link_state = %s, phase = CASE WHEN %s = 'none' THEN NULL ELSE '01-discover' END, gate_status = "
            "CASE WHEN %s = 'none' THEN NULL ELSE 'clear' END, phase_updated_at = %s WHERE id = %s",
            (actor, now, link, link, link, now, d["id"]),
        )
        d = _delivery(conn, d["id"])
        _set_stage(conn, d, "in_fix_track" if d["track"] == "fix" else "in_garage")
        _notify(conn, d, "delivery.phase_changed", {"phase": "started"})
        _audit(conn, actor, "delivery.approved", f"delivery:{d['id']}", {"track": d["track"]})
    return {"id": d["id"], "state": "in_delivery"}


def send_back(conn: Conn, actor: str, delivery_id: Any) -> dict[str, Any]:
    have = roles(conn, actor)
    with conn.transaction():
        d = _delivery(conn, delivery_id, lock=True)
        _sponsor_check(conn, d, actor, have)
        if d["state"] != "awaiting_sponsor":
            raise Refused(409, "not_awaiting_sponsor")
        conn.execute("UPDATE deliveries SET state = 'drafting' WHERE id = %s", (d["id"],))
        _audit(conn, actor, "delivery.sent_back", f"delivery:{d['id']}", {})
    return {"id": d["id"], "state": "drafting"}


# --- 2. Delivery status (manual until live sync) ---------------------------------------------------------------


def link_page(conn: Conn, actor: str, delivery_id: Any, body: dict[str, Any]) -> dict[str, Any]:
    """An admin links the delivery pipeline's page by hand (§4.8 failure handling). Live sync is coming soon."""
    if "admin" not in roles(conn, actor):
        raise Refused(403, "forbidden")
    page = str(body.get("page_id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9-]{8,64}", page):
        raise Refused(422, "page_id_not_valid")
    with conn.transaction():
        d = _delivery(conn, delivery_id, lock=True)
        if d["track"] == "fix" or d["state"] not in ("in_delivery", "shipped"):
            raise Refused(409, "not_in_delivery")
        conn.execute(
            "UPDATE deliveries SET pipeline_page_id = %s, link_state = 'linked' WHERE id = %s",
            (page, d["id"]),
        )
        _audit(conn, actor, "delivery.linked", f"delivery:{d['id']}", {})
    return {"id": d["id"], "link_state": "linked"}


def set_phase(
    conn: Conn, actor: str, delivery_id: Any, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    """The PM or an admin records the pipeline's phase and gate status (§4.9, by hand until live sync)."""
    now = now or dt.datetime.now(dt.UTC)
    have = roles(conn, actor)
    phase = body.get("phase")
    gate = body.get("gate_status") or "clear"
    if phase not in PHASE_IDS:
        raise Refused(422, "phase_not_valid")
    if gate not in GATE_STATUS:
        raise Refused(422, "gate_status_not_valid")
    with conn.transaction():
        d = _delivery(conn, delivery_id, lock=True)
        if not can_see(conn, d, actor, have):
            raise Refused(404, "not_found")
        if "admin" not in have and actor != str(d.get("pm_user_id")):
            raise Refused(403, "forbidden")
        if d["track"] == "fix" or d["state"] != "in_delivery":
            raise Refused(409, "not_in_delivery")
        if phase == d["phase"] and gate == d["gate_status"]:
            return {"id": d["id"], "phase": phase, "unchanged": True}
        previous_phase = d["phase"]
        blocked_since = (d["blocked_since"] or now) if gate == "blocked" else None
        conn.execute(
            "UPDATE deliveries SET phase = %s, gate_status = %s, blocked_since = %s, phase_updated_at = %s, "
            "blocked_flagged_at = CASE WHEN %s THEN blocked_flagged_at ELSE NULL END WHERE id = %s",
            (phase, gate, blocked_since, now, gate == "blocked", d["id"]),
        )
        d = _delivery(conn, d["id"])
        _audit(
            conn, actor, "delivery.phase_set", f"delivery:{d['id']}", {"phase": phase, "gate_status": gate}
        )
        if phase == "shipped":
            _close_delivery_work(conn, d, "shipped", now)
        elif plain_step(phase) != plain_step(previous_phase):
            # News only when the plain words change: a gate going blocked or clear is the team's business
            # (BLD-127), and so is a move between build steps inside "Being built" (BLD-157).
            _notify(conn, d, "delivery.phase_changed", {"phase": phase, "gate_status": gate})
    return {"id": d["id"], "phase": phase}


def _close_delivery_work(conn: Conn, d: dict[str, Any], state: str, now: dt.datetime) -> None:
    """Shipped or resolved: the stage moves on and the 30- and 90-day measurements open (§4.11 step 1)."""
    col = "shipped_at" if state == "shipped" else "resolved_at"
    conn.execute(f"UPDATE deliveries SET state = %s, {col} = %s WHERE id = %s", (state, now, d["id"]))  # noqa: S608
    for mark, days in MARKS.items():
        conn.execute(
            "INSERT INTO delivery_measurements (delivery_id, mark, due_at) VALUES (%s, %s, %s) "
            "ON CONFLICT (delivery_id, mark) DO NOTHING",
            (d["id"], mark, now + dt.timedelta(days=days)),
        )
    _set_stage(conn, d, state)
    _notify(conn, d, "delivery.phase_changed", {"phase": state})


# --- 3. Fix track ----------------------------------------------------------------------------------------------


def _fix_owner_check(conn: Conn, d: dict[str, Any], actor: str, have: set[str]) -> None:
    if not can_see(conn, d, actor, have):
        raise Refused(404, "not_found")
    if "admin" not in have and actor != str(d.get("owner_user_id")):
        raise Refused(403, "forbidden")
    if d["track"] != "fix" or d["state"] != "in_delivery":
        raise Refused(409, "not_in_fix_track")


def add_milestone(
    conn: Conn, actor: str, delivery_id: Any, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    today = (now or dt.datetime.now(dt.UTC)).date()
    have = roles(conn, actor)
    d = _delivery(conn, delivery_id)
    _fix_owner_check(conn, d, actor, have)
    due = _date(body.get("due_on"), "due_on_not_valid")
    if not today - dt.timedelta(days=30) <= due <= today + dt.timedelta(days=366):
        raise Refused(422, "due_on_not_valid")
    owner = (
        _user_by_email(conn, body["owner_email"], "owner_not_found")
        if str(body.get("owner_email") or "").strip()
        else str(d["owner_user_id"])
    )
    title = checked(conn, body.get("title"), min_chars=5, max_chars=120)
    with conn.transaction():
        d = _delivery(conn, d["id"], lock=True)
        _fix_owner_check(conn, d, actor, have)
        row = conn.execute(
            "INSERT INTO delivery_milestones (delivery_id, title_encrypted, owner_user_id, due_on) "
            "VALUES (%s, '\\x00', %s, %s) RETURNING id",
            (d["id"], owner, due),
        ).fetchone()
        assert row is not None
        conn.execute(
            "UPDATE delivery_milestones SET title_encrypted = %s WHERE id = %s",
            (seal(title, f"milestone:{row['id']}"), row["id"]),
        )
        _audit(conn, actor, "delivery.milestone_added", f"delivery:{d['id']}", {"milestone_id": row["id"]})
    return {"id": row["id"]}


def set_milestone(
    conn: Conn,
    actor: str,
    delivery_id: Any,
    milestone_id: Any,
    body: dict[str, Any],
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.UTC)
    have = roles(conn, actor)
    status = body.get("status")
    if status not in ("open", "done"):
        raise Refused(422, "status_not_valid")
    try:
        mid = int(milestone_id)
    except (TypeError, ValueError):
        raise Refused(404, "not_found") from None
    with conn.transaction():
        d = _delivery(conn, delivery_id, lock=True)
        if not can_see(conn, d, actor, have):
            raise Refused(404, "not_found")
        m = conn.execute(
            "SELECT * FROM delivery_milestones WHERE id = %s AND delivery_id = %s FOR UPDATE", (mid, d["id"])
        ).fetchone()
        if m is None:
            raise Refused(404, "not_found")
        if "admin" not in have and actor not in {str(d.get("owner_user_id")), str(m["owner_user_id"])}:
            raise Refused(403, "forbidden")
        if d["track"] != "fix" or d["state"] != "in_delivery":
            raise Refused(409, "not_in_fix_track")
        conn.execute(
            "UPDATE delivery_milestones SET status = %s, done_at = %s WHERE id = %s",
            (status, now if status == "done" else None, mid),
        )
        _audit(
            conn,
            actor,
            "delivery.milestone_set",
            f"delivery:{d['id']}",
            {"milestone_id": mid, "status": status},
        )
    return {"id": mid, "status": status}


def complete_fix(
    conn: Conn, actor: str, delivery_id: Any, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    """The owner submits before-and-after numbers (§4.10 completion). Evidence files are coming soon."""
    now = now or dt.datetime.now(dt.UTC)
    have = roles(conn, actor)
    d = _delivery(conn, delivery_id)
    _fix_owner_check(conn, d, actor, have)
    before = _number(body.get("before"), "before_not_valid")
    after = _number(body.get("after"), "after_not_valid")
    notes = checked(conn, body["notes"], min_chars=10, max_chars=600) if body.get("notes") else None
    with conn.transaction():
        d = _delivery(conn, d["id"], lock=True)
        _fix_owner_check(conn, d, actor, have)
        conn.execute(
            "UPDATE deliveries SET completion = %s, completion_notes = %s, completed_at = %s, completed_by = %s "
            "WHERE id = %s",
            (
                Jsonb({"before": before, "after": after, "unit": (d["pack"] or {}).get("unit")}),
                seal(notes, f"delivery:{d['id']}:completion") if notes else None, now, actor, d["id"],
            ),
        )  # fmt: skip
        emit(
            conn,
            "delivery.completion_to_approve",
            {
                "delivery_id": d["id"],
                "subject_id": d["subject_id"],
                "current_owner_ids": [str(d["sponsor_user_id"])],
            },
        )
        _audit(conn, actor, "delivery.completion_submitted", f"delivery:{d['id']}", {})
    return {"id": d["id"], "completed": True}


def approve_completion(
    conn: Conn, actor: str, delivery_id: Any, now: dt.datetime | None = None
) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.UTC)
    have = roles(conn, actor)
    with conn.transaction():
        d = _delivery(conn, delivery_id, lock=True)
        _sponsor_check(conn, d, actor, have)
        if d["track"] != "fix" or d["state"] != "in_delivery" or d["completed_at"] is None:
            raise Refused(409, "nothing_to_approve")
        if str(d.get("completed_by")) == actor:
            raise Refused(403, "own_entry")  # whoever submitted the numbers never approves them (BLD-126)
        _close_delivery_work(conn, d, "resolved", now)
        _audit(conn, actor, "delivery.resolved", f"delivery:{d['id']}", {})
    return {"id": d["id"], "state": "resolved"}


# --- 4. Measure and close --------------------------------------------------------------------------------------


def _measurement(conn: Conn, d: dict[str, Any], mark: Any) -> dict[str, Any]:
    if mark not in MARKS:
        raise Refused(404, "not_found")
    row = conn.execute(
        "SELECT * FROM delivery_measurements WHERE delivery_id = %s AND mark = %s FOR UPDATE", (d["id"], mark)
    ).fetchone()
    if row is None:
        raise Refused(409, "not_measuring")
    return dict(row)


def fill(
    conn: Conn, actor: str, delivery_id: Any, mark: Any, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    """The owner (or an admin) fills a measurement: the metric against its baseline, costs, adoption and the four
    impact measures (DEC-071). Values and fixed units only; one optional checked note."""
    now = now or dt.datetime.now(dt.UTC)
    have = roles(conn, actor)
    d = _delivery(conn, delivery_id)
    if not can_see(conn, d, actor, have):
        raise Refused(404, "not_found")
    if "admin" not in have and actor != str(d.get("owner_user_id")):
        raise Refused(403, "forbidden")
    results: dict[str, Any] = {"metric_actual": _number(body.get("metric_actual"), "metric_actual_not_valid")}
    for key in ("capex_inr", "opex_inr", "adoption"):
        if body.get(key) not in (None, ""):
            results[key] = _number(body[key], f"{key}_not_valid")
    for key, units in MEASURE_UNITS.items():
        m = body.get(key)
        if m in (None, {}, ""):
            continue
        if not isinstance(m, dict) or m.get("unit") not in units:
            raise Refused(422, f"{key}_not_valid")
        value = _number(m.get("value"), f"{key}_not_valid")
        if value > MAX_MEASURE:
            raise Refused(422, f"{key}_not_valid")
        results[key] = {"value": int(value), "unit": m["unit"]}
    notes = checked(conn, body["notes"], min_chars=10, max_chars=600) if body.get("notes") else None
    with conn.transaction():
        d = _delivery(conn, d["id"], lock=True)
        if d["state"] not in ("shipped", "resolved"):
            raise Refused(409, "not_measuring")
        m = _measurement(conn, d, mark)
        if m["confirmed_at"] is not None:
            raise Refused(409, "already_confirmed")
        if add_working_days(now, FILL_EARLY_WD) < m["due_at"]:
            raise Refused(409, "not_due_yet")  # results come at 30 and 90 days, not on the day it ships
        pack = d["pack"] or {}
        results["target_met"] = target_met(pack.get("baseline"), pack.get("target"), results["metric_actual"])
        results["actual_vs_target"] = progress_ratio(
            pack.get("baseline"), pack.get("target"), results["metric_actual"]
        )
        conn.execute(
            "UPDATE delivery_measurements SET results = %s, notes_encrypted = %s, filled_by = %s, filled_at = %s, "
            "finance_confirmed_by = NULL, finance_confirmed_at = NULL WHERE id = %s",
            (Jsonb(results), seal(notes, f"measurement:{m['id']}") if notes else None, actor, now, m["id"]),
        )
        emit(
            conn,
            "delivery.measure_to_confirm",
            {"delivery_id": d["id"], "subject_id": d["subject_id"], "mark": mark,
             "current_owner_ids": [str(d["sponsor_user_id"])]},
        )  # fmt: skip
        _audit(conn, actor, "delivery.measurement_filled", f"delivery:{d['id']}", {"mark": mark})
    return {"id": d["id"], "mark": mark, "target_met": results["target_met"]}


def confirm(
    conn: Conn, actor: str, delivery_id: Any, mark: Any, now: dt.datetime | None = None
) -> dict[str, Any]:
    """The sponsor confirms a measurement, never one they filled. The 90-day one closes the delivery."""
    now = now or dt.datetime.now(dt.UTC)
    have = roles(conn, actor)
    with conn.transaction():
        d = _delivery(conn, delivery_id, lock=True)
        _sponsor_check(conn, d, actor, have)
        if d["state"] not in ("shipped", "resolved"):
            raise Refused(409, "not_measuring")
        m = _measurement(conn, d, mark)
        if m["filled_at"] is None:
            raise Refused(409, "not_filled")
        if m["confirmed_at"] is not None:
            raise Refused(409, "already_confirmed")
        if str(m["filled_by"]) == actor:
            raise Refused(403, "own_entry")
        if mark == "day_90":
            first = conn.execute(
                "SELECT confirmed_at FROM delivery_measurements WHERE delivery_id = %s AND mark = 'day_30'",
                (d["id"],),
            ).fetchone()
            if first is None or first["confirmed_at"] is None:
                raise Refused(409, "day_30_first")
        conn.execute(
            "UPDATE delivery_measurements SET confirmed_by = %s, confirmed_at = %s WHERE id = %s",
            (actor, now, m["id"]),
        )
        feed_latest(conn, d)
        if mark == "day_30":
            _set_stage(conn, d, "measuring")
            _notify(conn, d, "delivery.phase_changed", {"phase": "measured_30"})
        else:
            outcome = "target_met" if (m["results"] or {}).get("target_met") else "target_not_met"
            conn.execute(
                "UPDATE deliveries SET state = 'closed', closed_at = %s, outcome = %s WHERE id = %s",
                (now, outcome, d["id"]),
            )
            _set_stage(conn, d, "closed")
            _notify(conn, d, "delivery.phase_changed", {"phase": "closed", "outcome": outcome})
        _audit(conn, actor, "delivery.measurement_confirmed", f"delivery:{d['id']}", {"mark": mark})
    return {"id": d["id"], "mark": mark, "closed": mark == "day_90"}


def finance_confirm(
    conn: Conn, actor: str, delivery_id: Any, mark: Any, now: dt.datetime | None = None
) -> dict[str, Any]:
    """An admin records that Finance has confirmed the money figure (DEC-071). Until then money never shows."""
    now = now or dt.datetime.now(dt.UTC)
    if "admin" not in roles(conn, actor):
        raise Refused(403, "forbidden")
    with conn.transaction():
        d = _delivery(conn, delivery_id, lock=True)
        m = _measurement(conn, d, mark)
        if "money" not in (m["results"] or {}):
            raise Refused(409, "no_money_figure")
        if m["finance_confirmed_at"] is not None:
            raise Refused(409, "already_finance_confirmed")
        if str(m["filled_by"]) == actor:
            raise Refused(403, "own_entry")  # the admin who typed the figure never vouches for it (BLD-126)
        conn.execute(
            "UPDATE delivery_measurements SET finance_confirmed_by = %s, finance_confirmed_at = %s WHERE id = %s",
            (actor, now, m["id"]),
        )
        feed_latest(conn, d)
        _audit(conn, actor, "delivery.finance_confirmed", f"delivery:{d['id']}", {"mark": mark})
    return {"id": d["id"], "mark": mark, "finance_confirmed": True}


def progress_ratio(baseline: Any, target: Any, actual: Any) -> float | None:
    """How far the result went from the baseline towards the target: 1.0 is the target met exactly, for an
    increase or a reduction alike (BLD-127). None without a baseline, or when the target is the baseline."""
    try:
        b, t, a = float(baseline), float(target), float(actual)
    except (TypeError, ValueError):
        return None
    if t == b:
        return None
    return round((a - b) / (t - b), 3)


def feed_latest(conn: Conn, d: dict[str, Any]) -> int:
    """The Ones' measured impact always comes from the latest confirmed result (the 90-day one once it exists),
    with money shown only if Finance confirmed that same result. A late Finance confirmation of the 30-day result
    never overwrites 90-day values (BLD-126)."""
    m = conn.execute(
        "SELECT results, finance_confirmed_at FROM delivery_measurements WHERE delivery_id = %s "
        "AND confirmed_at IS NOT NULL ORDER BY CASE mark WHEN 'day_90' THEN 0 ELSE 1 END LIMIT 1",
        (d["id"],),
    ).fetchone()
    if m is None:
        return 0
    return feed_ones(conn, d, m["results"] or {}, finance_ok=m["finance_confirmed_at"] is not None)


def feed_ones(conn: Conn, d: dict[str, Any], results: dict[str, Any], *, finance_ok: bool) -> int:
    """Confirmed results become the measured impact of every One whose accepted idea this delivery covers, so the
    wall, the home carousel, the screens and the leaderboard show them (DEC-071, DEC-083)."""
    measures: dict[str, Any] = {}
    for key in MEASURE_UNITS:
        if key in results:
            measures[key] = {"value": results[key]["value"], "unit": results[key]["unit"]}
            if key == "money":
                measures[key]["finance_confirmed"] = finance_ok
    if not measures:
        return 0
    ideas = subject_ideas(conn, d["subject_type"], d["subject_id"])
    rows = conn.execute(
        "UPDATE ones SET measures = measures || %s WHERE way_in = 'accepted_idea' AND idea_id = ANY(%s) RETURNING id",
        (Jsonb(measures), ideas),
    ).fetchall()
    for r in rows:
        _audit(conn, "process:delivery", "ones.measures_from_delivery", f"one:{r['id']}",
               {"delivery_id": d["id"], "keys": sorted(measures)})  # fmt: skip
    return len(rows)
