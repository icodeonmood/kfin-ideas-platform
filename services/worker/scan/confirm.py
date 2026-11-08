"""The person checks the canvas before choosing (§4.2 step 4: "accepts, edits or clears each one, then clicks
'Looks right'"). Suggestions are kept (provenance `accepted`) or cleared; the one line and details can be edited.
Edited text is pattern-checked, re-checked by the gatekeeper and tagged like any submission; if the one line or
details changed by more than `match.rerun_if_edit_share` of their words, the match runs again (AT-B5-07).
"""

from __future__ import annotations

import difflib
from typing import Any

from core.config import get_settings
from core.db import Conn
from gateway import run_agent
from pii.patterns import scan
from pii.tagger import tag_payload
from rules import load_rule
from scan.matching import card_text, run_matching
from scan.pipeline import _save_result, contestable, decide, load_result, thresholds

EMPTY: dict[str, Any] = {
    "one_line": None,
    "details": "",
    "who.frequency_or_reach": None,
    "who.today_alternative": None,
}


class ConfirmRefused(Exception):
    def __init__(self, status: int, code: str, details: Any = None):
        super().__init__(code)
        self.status, self.code, self.details = status, code, details


def _set_path(node: dict[str, Any], path: str, value: Any) -> None:
    keys = path.split(".")
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value


def _empty_for(path: str) -> Any:
    if path in EMPTY:
        return EMPTY[path]
    if path in ("who.segments", "ecosystem.references"):
        return []
    if path in ("kind", "value.category", "ecosystem.solved_elsewhere"):
        return None  # required enums: kept as suggested if cleared (schema needs a value); see below
    return None


def edit_share(before: str, after: str) -> float:
    """Share of words changed between two texts (0 = identical, 1 = nothing in common)."""
    a, b = before.split(), after.split()
    if not a and not b:
        return 0.0
    return 1.0 - difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio()


def confirm(conn: Conn, idea_uuid: str, idea_id: str, body: dict[str, Any]) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM scans WHERE idea_uuid = %s", (idea_uuid,)).fetchone()
    if row is None or row["state"] != "done" or row["outcome"] != "ready":
        raise ConfirmRefused(409, "not_available_now")
    result = load_result(row)
    card: dict[str, Any] = dict(result.get("confirmed") or result["canvas_assist"])
    provenance: dict[str, str] = dict(card.get("provenance") or {})

    # Keep or clear each suggestion. Required enums the person clears fall back to "not sure"/"don't know".
    keep: dict[str, Any] = body.get("keep") or {}
    for path, who in list(provenance.items()):
        if who not in ("suggested", "accepted"):
            continue
        if keep.get(path, True):
            provenance[path] = "accepted"
            continue
        if path == "value.category":
            _set_path(card, path, "not_sure")
        elif path == "ecosystem.solved_elsewhere":
            _set_path(card, path, "dont_know")
        elif path == "kind":
            continue  # a kind is needed to route the idea; it stays suggested for the reviewer
        else:
            _set_path(card, path, _empty_for(path))
        provenance.pop(path, None)

    # Edits to the one line and details: patterns, then gatekeeper, then tags.
    edits = {k: str(body[k]).strip() for k in ("one_line", "details") if isinstance(body.get(k), str)}
    if edits.get("one_line") is not None and len(edits["one_line"].split()) > 20:
        raise ConfirmRefused(422, "one_line_too_long")
    if edits.get("details") is not None and len(edits["details"]) < 50:
        raise ConfirmRefused(422, "details_too_short")
    domains = get_settings().kfin_domains
    for field, text in edits.items():
        hits = [m for m in scan(text, kfin_domains=domains) if m.action == "block"]
        if hits:
            raise ConfirmRefused(422, "personal_data", [{"field": field, "label": hits[0].label}])
    if edits:
        gk = run_agent("gatekeeper", {"mode": "submission", "submission": edits}, idea_id, conn=conn)
        if decide(gk.data, thresholds()) == "blocked" and not contestable(gk.data):
            raise ConfirmRefused(
                422, "personal_data", [{"field": s["field"]} for s in gk.data["personal_data"]["spans"]]
            )
        tagged = tag_payload(conn, idea_id, edits).payload
        for field, value in tagged.items():
            if value != card.get(field):
                card[field] = value
                provenance[field] = "submitter"
    card["provenance"] = provenance

    share_limit = float(
        load_rule(get_settings().company_repo_path, "thresholds").data["match"]["rerun_if_edit_share"]
    )
    before = (result.get("match") or {}).get("card_text") or card_text(result["canvas_assist"])
    rerun = edit_share(before, card_text(card)) > share_limit
    if rerun:
        result["match"] = run_matching(conn, idea_id, card)
    result["confirmed"] = card
    _save_result(conn, idea_uuid, result)
    return {"rerun_match": rerun}
