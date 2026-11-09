"""Member cards for cluster work. Each idea's text is tagged in its own scope, so `[[CLIENT_AMC_1]]` in one idea
and in another can be different clients. Before cluster agents see several ideas together, each card is restored
to real values inside the worker and handed to `run_agent` under one proposal scope, which tags them again
consistently (§3.2 step 1). Real values never leave this process except through the gateway's tagging.
"""

from __future__ import annotations

from typing import Any

from core.db import Conn
from pii import vault
from pii.restore import restore

CARD_FIELDS = ("kind", "one_line", "details", "who", "value", "solution")


def ideas(conn: Conn, idea_ids: list[str]) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT idea_id, contributor_code, canvas, kind, category, play, area_ids, lobs, systems, roles_affected, "
        "stage, cluster_id FROM ideas WHERE idea_id = ANY(%s)",
        (idea_ids,),
    ).fetchall()
    return {r["idea_id"]: dict(r) for r in rows}


def real_canvas(conn: Conn, idea: dict[str, Any]) -> dict[str, Any]:
    canvas = {k: (idea.get("canvas") or {}).get(k) for k in CARD_FIELDS}
    return dict(restore(canvas, vault.mapping(conn, idea["idea_id"]), "real"))


def member_card(conn: Conn, ref: str, idea: dict[str, Any]) -> dict[str, Any]:
    """The cluster-summary input for one member, with real values (the gateway tags them)."""
    c = real_canvas(conn, idea)
    who = c.get("who") or {}
    solution = c.get("solution") or {}
    return {
        "ref": ref,
        "kind": idea.get("kind") or c.get("kind"),
        "one_line": str(c.get("one_line") or "")[:300],
        "details": " ".join(str(c.get("details") or "").split())[:1200],
        "who": {"segments": who.get("segments") or [], "frequency_or_reach": who.get("frequency_or_reach")},
        "category": idea.get("category"),
        "play": idea.get("play"),
        "areas": list(idea.get("area_ids") or []),
        "lobs": list(idea.get("lobs") or []),
        "roles_affected": list(idea.get("roles_affected") or []),
        "fix": (str(solution.get("approach")).strip() or None) if solution.get("approach") else None,
    }


def judge_card(conn: Conn, idea: dict[str, Any]) -> dict[str, Any]:
    c = real_canvas(conn, idea)
    return {
        "kind": idea.get("kind") or c.get("kind"),
        "one_line": c.get("one_line"),
        "details": " ".join(str(c.get("details") or "").split())[:1200],
        "who": {"segments": (c.get("who") or {}).get("segments") or []},
        "category": idea.get("category"),
        "play": idea.get("play"),
        "areas": list(idea.get("area_ids") or []),
        "lobs": list(idea.get("lobs") or []),
        "systems": list(idea.get("systems") or []),
    }


def judge_candidate(conn: Conn, idea: dict[str, Any]) -> dict[str, Any]:
    c = real_canvas(conn, idea)
    return {
        "cid": idea["idea_id"],
        "type": "idea",
        "title": str(c.get("one_line") or "")[:160],
        "summary": " ".join(str(c.get("details") or "").split())[:480],
        "stage": idea.get("stage"),
        "areas": list(idea.get("area_ids") or []),
        "lobs": list(idea.get("lobs") or []),
    }
