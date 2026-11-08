"""Build a message for one recipient (§3.7 step 4): the template's variables are read from the records the
notification points to, at the moment it is sent or viewed, and tagged text is restored only as far as that
recipient may see it. The submitter sees their own idea's real values; anyone else sees the neutral summary and
neutral labels (non-negotiable 7)."""

from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from core.config import get_settings
from core.crypto import CryptoError, decrypt_json
from core.db import Conn
from pii import vault
from pii.restore import restore
from rules import load_rule

IST = ZoneInfo("Asia/Kolkata")
NEXT_STEPS = {
    "review": "The review desk looks at it next.",
    "clustered": "It will be looked at together with the similar ideas.",
    "qualify": "The core committee looks at the most promising ideas each month.",
    "garage": "It goes to the Garage for delivery.",
    "fix_track": "It goes to the team that can fix it.",
    "closed": "No further steps are planned.",
}
OUTCOMES = {
    "kept": "The review desk's decision stands.",
    "changed": "The core committee changed the review desk's decision.",
}


def _date(ts: dt.datetime | None) -> str:
    return ts.astimezone(IST).strftime("%a %d %b") if ts else ""


def _first_name(conn: Conn, user_id: str) -> str:
    row = conn.execute("SELECT name FROM users WHERE id = %s", (user_id,)).fetchone()
    return str(row["name"]).split()[0] if row and row["name"] else "there"


def _name(conn: Conn, user_id: Any) -> str:
    if not user_id:
        return "The review desk"
    row = conn.execute("SELECT name FROM users WHERE id = %s", (str(user_id),)).fetchone()
    return str(row["name"]) if row and row["name"] else "The review desk"


def _owns(conn: Conn, user_id: str, idea: dict[str, Any]) -> bool:
    row = conn.execute(
        "SELECT 1 FROM contributor_map WHERE user_id = %s AND contributor_code = %s",
        (user_id, idea["contributor_code"]),
    ).fetchone()
    return row is not None


def _restore(conn: Conn, idea_id: str, value: Any, real: bool) -> Any:
    return restore(value, vault.mapping(conn, idea_id), "real" if real else "neutral")


def _decrypt_text(blob: Any, context: str) -> str | None:
    if blob is None:
        return None
    try:
        return str(decrypt_json(bytes(blob), context).get("text") or "")
    except CryptoError:
        return None


def variables(conn: Conn, user_id: str, event: str, refs: dict[str, Any]) -> dict[str, Any]:
    base = get_settings().app_base_url.rstrip("/")
    data: dict[str, Any] = {"recipient": {"first_name": _first_name(conn, user_id)}, "links": {}}
    idea = None
    if refs.get("idea_id"):
        idea = conn.execute(
            "SELECT id, idea_id, contributor_code, canvas, strength FROM ideas WHERE idea_id = %s",
            (refs["idea_id"],),
        ).fetchone()
    target_id = refs.get("target_id")
    if event == "idea.joined" and target_id and str(target_id).startswith("IDEA-"):
        idea = conn.execute(
            "SELECT id, idea_id, contributor_code, canvas, strength FROM ideas WHERE idea_id = %s",
            (target_id,),
        ).fetchone()
    if idea:
        card = idea["canvas"] or {}
        own = _owns(conn, user_id, idea)
        one_line = (
            _restore(conn, idea["idea_id"], card.get("one_line"), True)
            if own
            else card.get("neutral_summary")
        )
        data["idea"] = {
            "id": idea["idea_id"],
            "one_line": one_line or "your idea",
            "strength": idea["strength"] if idea["strength"] is not None else 0,
            "next_best": list(((card.get("strength") or {}).get("next_best") or [])[:2]),
        }
        data["links"]["idea"] = f"{base}/ideas/{idea['idea_id']}" if own else f"{base}/my-ideas"
        due = conn.execute(
            "SELECT t.due_at FROM sla_timers t JOIN review_items r ON t.entity_id = r.id::text "
            "WHERE r.ref_id = %s AND t.stage = 'review' ORDER BY t.id DESC LIMIT 1",
            (idea["idea_id"],),
        ).fetchone()
        data["review"] = {"due_date": _date(due["due_at"]) if due else ""}
    if refs.get("reviewer_user_id") or event in ("idea.question", "idea.reviewed", "idea.redirected"):
        data["reviewer"] = {"name": _name(conn, refs.get("reviewer_user_id"))}

    if event == "idea.question" and idea:
        q = conn.execute(
            "SELECT id, question_encrypted, due_at FROM idea_questions WHERE id = %s",
            (refs.get("question_id"),),
        ).fetchone()
        text = _decrypt_text(q["question_encrypted"], f"question:{q['id']}") if q else None
        data["question"] = {
            "text": _restore(conn, idea["idea_id"], text or "", _owns(conn, user_id, idea)),
            "due_date": _date(q["due_at"]) if q else "",
        }
    if event == "idea.reviewed":
        grouped = refs.get("outcome") == "grouped"
        data["outcome"] = {"grouped": grouped, "standalone": not grouped}
        data["cluster"] = {
            "name": refs.get("cluster_id") or "",
            "other_count": refs.get("cluster_other_count") or 0,
        }
        data["next_step"] = {"text": NEXT_STEPS.get(str(refs.get("next_step")), NEXT_STEPS["review"])}
        note = None
        if refs.get("note_correction_id") and idea:
            row = conn.execute(
                "SELECT note FROM corrections WHERE id = %s", (refs["note_correction_id"],)
            ).fetchone()
            note = _restore(conn, idea["idea_id"], row["note"], _owns(conn, user_id, idea)) if row else None
        data.setdefault("reviewer", {})["note"] = note
    if event == "idea.redirected":
        targets = load_rule(get_settings().company_repo_path, "redirects").data.get("targets") or {}
        t = targets.get(str(refs.get("redirect_kind"))) or {}
        data["redirect"] = {
            "team": t.get("team") or "",
            "message": t.get("message") or "",
            "url": t.get("url"),
        }
    if event == "idea.reconsidered" and idea:
        item = conn.execute(
            "SELECT veto_reason FROM review_items WHERE id = %s", (refs.get("review_item_id"),)
        ).fetchone()
        reason = (
            _restore(conn, idea["idea_id"], item["veto_reason"], _owns(conn, user_id, idea)) if item else ""
        )
        data["member"] = {"name": _name(conn, refs.get("member_user_id"))}
        data["outcome"] = {
            "text": OUTCOMES.get(str(refs.get("outcome")), OUTCOMES["changed"]),
            "reason": reason,
        }
        data["next_step"] = {"text": NEXT_STEPS.get(str(refs.get("next_step")), NEXT_STEPS["review"])}
    if event == "idea.joined":
        row = conn.execute(
            "SELECT count(DISTINCT contributor_code) AS n FROM idea_links WHERE coalesce(idea_id, cluster_id) = %s "
            "AND link_type IN ('joiner', 'plus_one')",
            (target_id,),
        ).fetchone()
        n = int(row["n"]) if row else 1
        data["join"] = {
            "count": n,
            "count_word": "colleague" if n == 1 else "colleagues",
            "names_visible": False,  # names arrive with consent rules in a later block
        }
    if event == "adoption.requested":
        sol = conn.execute(
            "SELECT summary FROM repo_files WHERE kfin_id = %s LIMIT 1", (refs.get("solution_id"),)
        ).fetchone()
        link = conn.execute(
            "SELECT l.context_text, u.hr_department FROM idea_links l JOIN contributor_map m ON m.contributor_code = "
            "l.contributor_code JOIN users u ON u.id = m.user_id WHERE l.id = %s",
            (refs.get("link_id"),),
        ).fetchone()
        context = (
            _restore(conn, refs["idea_id"], link["context_text"], False)
            if link and link["context_text"]
            else ""
        )
        data["solution"] = {
            "id": refs.get("solution_id"),
            "title": (sol["summary"] if sol else "") or "your solution",
        }
        data["requester"] = {"lob_name": (link["hr_department"] if link else None) or "another team"}
        data["request"] = {"context": context}
        data["links"]["request"] = f"{base}/review"
    if event == "sla.reminder":
        timer = conn.execute(
            "SELECT due_at FROM sla_timers WHERE id = %s", (refs.get("timer_id"),)
        ).fetchone()
        data["item"] = {
            "label": refs.get("idea_id") or "An item",
            "due_date": _date(timer["due_at"]) if timer else "",
        }
        data["reminder"] = {"share_percent": int(float(refs.get("share") or 0) * 100)}
        data["links"]["item"] = f"{base}/review"
    if event == "sla.breached":
        data["breach"] = {"days_late": refs.get("days_late", 0), "limit_wd": refs.get("limit_wd", 0)}
        data["item"] = {
            "label": refs.get("item_label") or "",
            "owner_name": _name(conn, refs.get("owner_user_id")),
        }
        data["links"]["item"] = f"{base}/review"
    return data
