"""What a person sees of a scan (§4.2 steps 3–4), restored for the viewer the web app vouches for.

The web app decides the mode from §3.1 (owner: `real`); this module only opens the vault. Reviewer flags,
confidences and internal tags are never in the submitter's view.
"""

from __future__ import annotations

from typing import Any, Literal

from core.config import get_settings
from core.db import Conn
from pii import vault
from pii.restore import restore
from rules import load_rule
from scan.matching import submitter_cards
from scan.pipeline import contestable, load_result

DATA_TYPE_LABELS = {
    "investor_or_customer_name": "an investor's or customer's name",
    "tagged_person_as_investor": "a person described as an investor or customer",
    "individual_distributor_details": "an individual distributor's details",
    "address": "a home address",
    "account_or_folio_number": "an account or folio number",
    "government_id": "a government ID",
    "date_of_birth": "a date of birth",
    "phone": "a phone number",
    "personal_email": "a personal email address",
    "sensitive_detail": "a sensitive personal detail",
    "other": "personal data",
}


def _suggested(canvas: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for path, who in sorted((canvas.get("provenance") or {}).items()):
        if who != "suggested":
            continue
        node: Any = canvas
        for key in path.split("."):
            node = node.get(key) if isinstance(node, dict) else None
        if node not in (None, "", []):
            out.append({"path": path, "value": node})
    return out


def view(conn: Conn, idea_uuid: str, mode: Literal["real", "neutral"]) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT s.*, i.idea_id, i.stage FROM scans s JOIN ideas i ON i.id = s.idea_uuid WHERE s.idea_uuid = %s",
        (idea_uuid,),
    ).fetchone()
    if row is None:
        idea = conn.execute("SELECT idea_id, stage FROM ideas WHERE id = %s", (idea_uuid,)).fetchone()
        if idea is None:
            return None
        return {
            "state": "queued",
            "step": "queued",
            "outcome": None,
            "idea_id": idea["idea_id"],
            "stage": idea["stage"],
        }
    result = load_result(row)
    mapping = vault.mapping(conn, row["idea_id"]) if result else {}
    result = restore(result, mapping, mode)
    out: dict[str, Any] = {
        "state": row["state"],
        "step": row["step"],
        "outcome": row["outcome"],
        "idea_id": row["idea_id"],
        "stage": row["stage"],
    }
    if row["outcome"] == "blocked":
        spans = result["gatekeeper"]["personal_data"]["spans"]
        out["blocked"] = {
            "spans": [
                {
                    "field": s["field"],
                    "quote": s["quote"],
                    "label": DATA_TYPE_LABELS.get(s["data_type"], "personal data"),
                }
                for s in spans
            ],
            "investor_context": bool(result["gatekeeper"]["investor_context_tags"]),
            "can_contest": contestable(result["gatekeeper"]),
        }
    elif row["outcome"] == "redirect":
        kind = result["gatekeeper"]["kind"]["value"]
        rules = load_rule(get_settings().company_repo_path, "redirects").data
        target = (rules.get("targets") or {}).get(kind) or {}
        out["redirect"] = {
            "kind": kind,
            "team": target.get("team"),
            "url": target.get("url"),
            "message": target.get("message"),
            "override_label": rules.get("override_label", "No, this is an idea"),
            "override_reason_min_chars": int(rules.get("override_reason_min_chars", 15)),
        }
    elif row["outcome"] == "ready" and "canvas_assist" in result:
        ca = result["canvas_assist"]
        out["ready"] = {
            "suggested": _suggested(ca),
            "neutral_summary": ca["neutral_summary"],
            "next_best": ca["strength"]["next_best"],
            "matches": submitter_cards(conn, result["match"]) if "match" in result else [],
        }
    return out
