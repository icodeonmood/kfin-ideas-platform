"""The review item screen (§4.3, AT-B6-02): the person's original words beside the confirmed canvas (answers they
gave marked apart from the assistant's), strength, attachments and their check status; the proposals with
confidence and reasons; the candidates with labels and reasons; and history. Restored for the viewer as the web
app decides (§3.1 `see_restored_values`: the reviewer handling it, the core committee)."""

from __future__ import annotations

from typing import Any, Literal

from core.config import get_settings
from core.db import Conn
from pii import vault
from pii.restore import restore
from scan.inputs import _taxonomy


def item_view(conn: Conn, item_id: int, mode: Literal["real", "neutral"]) -> dict[str, Any] | None:
    item = conn.execute("SELECT * FROM review_items WHERE id = %s", (item_id,)).fetchone()
    if item is None:
        return None
    idea = conn.execute("SELECT * FROM ideas WHERE idea_id = %s", (item["ref_id"],)).fetchone()
    if idea is None:
        return None
    mapping = vault.mapping(conn, idea["idea_id"])

    def show(value: Any) -> Any:
        return restore(value, mapping, mode)

    card = dict(idea["canvas"] or {})
    proposal = dict(item["proposal"] or {})
    candidates = []
    for c in proposal.get("candidates") or []:
        f = conn.execute(
            "SELECT repo_path, summary FROM repo_files WHERE kfin_id = %s LIMIT 1", (c.get("cid"),)
        ).fetchone()
        candidates.append(
            {
                "cid": c.get("cid"), "type": c.get("type"), "label": c.get("label"), "confidence": c.get("confidence"),
                "reason": show(c.get("reason")), "visibility": c.get("visibility"), "stage": c.get("stage"),
                "summary": f["summary"] if f else None, "repo_path": f["repo_path"] if f else None,
            }
        )  # fmt: skip
    history = [
        {"event": r["event_type"], "by": r["actor"], "at": r["created_at"].isoformat()}
        for r in conn.execute(
            "SELECT event_type, actor, created_at FROM outbox WHERE aggregate_id = %s ORDER BY id",
            (idea["idea_id"],),
        ).fetchall()
    ]
    timer = conn.execute(
        "SELECT stage, state, due_at FROM sla_timers WHERE entity_type = 'review_item' AND entity_id = %s "
        "ORDER BY id DESC LIMIT 1",
        (str(item_id),),
    ).fetchone()
    attachments = [
        {"id": a["id"], "name": a["name"], "state": a["state"],
         # Week 3 (D3): the digest and its claims, tagged under the idea's scope and restored like the canvas.
         "digest": show(a["digest"]) if a["state"] == "clean" else None,
         "claims": show((a["digest_meta"] or {}).get("claims") or []) if a["state"] == "clean" else [],
         "patterns_only": bool((a["checks"] or {}).get("gatekeeper_skipped"))}
        for a in conn.execute(
            "SELECT id, name, state, digest, digest_meta, checks FROM attachments WHERE idea_uuid = %s "
            "ORDER BY created_at",
            (idea["id"],),
        ).fetchall()
    ]  # fmt: skip
    tax = _taxonomy(get_settings().company_repo_path)
    return {
        "item": {
            "id": item["id"], "type": item["item_type"], "state": item["state"],
            "assigned_to": str(item["assigned_to"]) if item["assigned_to"] else None,
            "decided_at": item["decided_at"].isoformat() if item["decided_at"] else None,
            "final": item["final"], "timer": dict(timer) | {"due_at": timer["due_at"].isoformat()} if timer else None,
            "vetoed": item["vetoed_by"] is not None, "veto_reason": show(item["veto_reason"]),
        },
        "idea": {
            "id": idea["idea_id"], "stage": idea["stage"], "strength": idea["strength"], "visibility": idea["visibility"],
            "card": show({k: v for k, v in card.items() if k != "original_text"}),
            "original_text": show(card.get("original_text")),
            "provenance": card.get("provenance") or {},
            "attachments": attachments,
        },
        "proposals": {
            "system": proposal.get("system") or {}, "confidence": item["confidence"] or {},
            "flags": show((item["reasons"] or {}).get("flags_for_reviewer") or []),
            "contested": (item["reasons"] or {}).get("contested"),
            "person_says": show((item["reasons"] or {}).get("person_says")),
            "best_same": proposal.get("best_same"), "suggested_action": proposal.get("suggested_action"),
            "choice": proposal.get("choice"),
        },
        "candidates": candidates,
        "history": history,
        "taxonomy": {
            "areas": [{"id": a["id"], "name": a["name"]} for a in tax["areas"]],
            "lobs": [{"id": x["id"], "name": x["name"]} for x in tax["lobs"]],
        },
    }  # fmt: skip
