"""The idea page (AT-B7-03): the timeline is the history table in the idea's file in the company repo, so the page
and the repo always agree. Two views, chosen by the web app from §3.1:

- `full`: the person who shared it, and the review roles. The confirmed canvas, restored in the mode the web app
  decided (`see_restored_values`); the open question and "Disagree with this?" for the owner; every history row.
- `public`: everyone else, and only for ideas the desk has accepted and everyone may see. The neutral summary,
  area, stage and colleague count, and the milestones of the history without notes or who did what.
"""

from __future__ import annotations

from typing import Any, Literal

from core import killswitch
from core.config import get_settings
from core.crypto import decrypt_json
from core.db import Conn
from pii import vault
from pii.restore import restore
from repo_writer.render import existing_state
from views.common import first_area, is_public, public_card, taxonomy_names
from views.mine import OWNER_WORDS, owner_status

EVENT_WORDS = {
    "submitted": "Shared",
    "reviewed": "Reviewed by the review desk",
    "redirected": "Sent to the right team",
    "visibility_changed": "Who can see it was changed",
    "summary_written": "The review desk wrote the short summary colleagues see",
    "review_overdue": "The review took longer than planned",
    "needs_info_overdue": "Set aside: no answer yet",
    "clustered": "Grouped with similar ideas",
    "shortlisted": "Shortlisted",
    "picked": "Picked",
    "shipped": "Shipped",
    "resolved": "Fixed",
}
PUBLIC_EVENTS = {"submitted", "reviewed", "clustered", "shortlisted", "picked", "shipped", "resolved"}
DISAGREE_STAGES = ("reviewed", "in_cluster", "declined", "redirected", "parked")


def _by(actor: str, owner_code: str, viewer_codes: list[str]) -> str:
    if actor in viewer_codes:
        return "You"
    if actor.startswith("REV-") or actor.startswith("human:REV-"):
        return "The review desk"
    if actor.startswith("CTR-"):
        return "The person who shared it" if actor == owner_code else "A colleague"
    if actor.startswith("core:") or actor.startswith("committee:"):
        return "The core committee"
    return "The platform"


def timeline(
    idea: dict[str, Any], view: Literal["full", "public"], viewer_codes: list[str]
) -> list[dict[str, str]]:
    rel = idea.get("repo_path")
    if not rel:
        return []
    path = get_settings().company_repo_path / rel
    rows, _ = existing_state(path.read_text(encoding="utf-8") if path.exists() else None)
    out = []
    for r in rows:
        if view == "public" and r.event not in PUBLIC_EVENTS:
            continue
        out.append(
            {
                "when": r.when,
                "event": r.event,
                "what": EVENT_WORDS.get(r.event, r.event.replace("_", " ").capitalize()),
                **(
                    {"by": _by(r.by, idea["contributor_code"], viewer_codes), "note": r.note}
                    if view == "full"
                    else {}
                ),
            }
        )
    return out


def find(conn: Conn, idea_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM ideas WHERE idea_id = %s", (idea_id,)).fetchone()
    return dict(row) if row else None


def page(
    conn: Conn,
    idea_id: str,
    view: Literal["full", "public"],
    mode: Literal["real", "neutral"],
    viewer_codes: list[str],
) -> dict[str, Any] | None:
    """None when the idea does not exist or this view may not show it (the web app answers 404 either way)."""
    idea = find(conn, idea_id)
    if idea is None or not idea["idea_id"]:
        return None
    areas, _ = taxonomy_names()
    if view == "public":
        if not is_public(idea) or not killswitch.is_on("wall.public", conn):
            return None  # the wall switch hides everyone else's view of ideas too (B7 review)
        card = public_card(conn, idea, areas)
        if card is None:
            return None
        return {"view": "public", "card": card, "timeline": timeline(idea, "public", viewer_codes)}

    owner = idea["contributor_code"] in viewer_codes
    mapping = vault.mapping(conn, idea_id)
    canvas = {
        k: v
        for k, v in (idea["canvas"] or {}).items()
        if k not in ("original_text", "provenance", "evidence")
    }
    out: dict[str, Any] = {
        "view": "full",
        "owner": owner,
        "idea_id": idea_id,
        "card": restore(canvas, mapping, mode),
        "area": first_area(idea["area_ids"], areas),
        "visibility": idea["visibility"],
        "strength": idea["strength"],
        "status": owner_status(conn, idea)
        if owner
        else {
            "stage": OWNER_WORDS.get(idea["stage"], ("With the review desk", ""))[0],
            "next_step": None,
            "due": None,
        },
        "timeline": timeline(idea, "full", viewer_codes),
    }
    if owner:
        out["uuid"] = str(idea["id"])  # the owner's own follow-up calls (answer, disagree) use it
        q = conn.execute(
            "SELECT id, question_encrypted, due_at FROM idea_questions WHERE idea_uuid = %s AND answered_at IS NULL "
            "ORDER BY id DESC LIMIT 1",
            (idea["id"],),
        ).fetchone()
        out["question"] = None
        if q is not None and idea["stage"] in ("needs_info", "withdrawn"):
            text = decrypt_json(bytes(q["question_encrypted"]), f"question:{q['id']}").get("text")
            out["question"] = {"text": restore(text, mapping, mode), "due": q["due_at"].isoformat()}
        open_disagreement = conn.execute(
            "SELECT 1 FROM review_items WHERE item_type = 'disagreement' AND ref_id = %s AND state = 'open'",
            (idea_id,),
        ).fetchone()
        out["can_disagree"] = idea["stage"] in DISAGREE_STAGES and open_disagreement is None
    return out
