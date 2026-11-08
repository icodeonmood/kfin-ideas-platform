"""Scan step 5–7 (§4.2): match the card (plan P3), let the judge label the candidates, and build what the
submitter may see — Find your crew.

What a submitter may see of other people's ideas (§4.2 step 7, AT-B5-05): only the neutral summary (re-checked
with the patterns, tags and the name detector before display), the area tag, the stage, the number of colleagues
on it and, for solutions, the owning LOB. Never an ID, title, text, file or name. Committee-only items appear as
"a related idea is with the review desk" and nothing else. `matching.show` off: the submitter sees no matches;
the review desk keeps the full list.
"""

from __future__ import annotations

from typing import Any

from core import killswitch
from core.db import Conn
from embeddings import embed
from gateway import run_agent
from pii.detect import detect, directory
from pii.patterns import scan
from pii.tagger import TAG_RE
from router.corrections import corrections_for
from router.match import Candidate, match
from router.taxonomy import glossary_ids
from scan.inputs import _taxonomy

STAGE_WORDS = {
    "scanned": "With the review desk",
    "reviewed": "Reviewed",
    "needs_info": "With the review desk",
    "in_cluster": "Grouped with similar ideas",
    "ready_for_scoring": "Being assessed",
    "scored": "Being assessed",
    "shortlisted": "Shortlisted",
    "presenting": "Being presented",
    "picked": "Picked for the Garage",
    "handover": "In the Garage",
    "in_garage": "In the Garage",
    "in_fix_track": "Being fixed",
    "shipped": "In the Garage",
    "resolved": "Fixed",
    "measuring": "In the Garage",
    "declined": "Looked at before",
    "parked": "Looked at before",
}


def card_text(card: dict[str, Any]) -> str:
    return "\n".join(str(card.get(k) or "") for k in ("one_line", "details")).strip()


def judge_card(ca: dict[str, Any]) -> dict[str, Any]:
    value = ca.get("value") or {}
    system = ca.get("system") or {}
    return {
        "kind": ca.get("kind"),
        "one_line": ca.get("one_line"),
        "details": ca.get("details"),
        "who": {"segments": (ca.get("who") or {}).get("segments") or []},
        "category": value.get("category"),
        "play": value.get("play"),
        "areas": system.get("areas") or [],
        "lobs": system.get("lobs") or [],
        "systems": system.get("systems") or [],
    }


def _judge_candidate(c: Candidate) -> dict[str, Any]:
    first, _, rest = c.text.partition("\n")
    return {
        "cid": c.kfin_id,
        "type": c.file_type,
        "title": first.strip()[:160],
        "summary": " ".join(rest.split())[:480],  # about 120 tokens (agents/judge `candidate_token_trim`)
        "stage": c.stage,
        "areas": c.area_ids,
        "lobs": c.lobs,
    }


def run_matching(conn: Conn, idea_id: str, ca: dict[str, Any]) -> dict[str, Any]:
    """Candidates and the judge's labels, for the review desk and (filtered) the submitter. Tagged, stored
    encrypted with the scan result."""
    text = card_text(ca)
    vec = embed([text])[0]
    gl = sorted(set((ca.get("system") or {}).get("systems") or []) | set(glossary_ids(conn, text)))
    found = [c for c in match(conn, text, gl, exclude_ids=(idea_id,), card_vector=vec) if c.kfin_id]
    labels: dict[str, dict[str, Any]] = {}
    best = None
    if found:
        out = run_agent(
            "judge",
            {
                "card": judge_card(ca),
                "candidates": [_judge_candidate(c) for c in found],
                "past_corrections": corrections_for(conn, vec, field="match"),
            },
            idea_id,
            conn=conn,
        )
        labels = {r["cid"]: r for r in out.data["results"]}
        best = out.data["best_same"]
    return {
        "card_text": text,
        "best_same": best,
        "candidates": [
            {
                "cid": c.kfin_id,
                "type": c.file_type,
                "stage": c.stage,
                "visibility": c.visibility,
                "score": round(c.score, 6),
                "via": c.via,
                "label": labels.get(c.kfin_id or "", {}).get("label", "different"),
                "reason": labels.get(c.kfin_id or "", {}).get("reason"),
                "confidence": labels.get(c.kfin_id or "", {}).get("confidence"),
            }
            for c in found
        ],
    }


def _safe_summary(conn: Conn, summary: str | None) -> str | None:
    """Shown only if it holds no tag, no pattern match and no name or client the detector recognises."""
    if not summary or TAG_RE.search(summary) or scan(summary, kfin_domains=[]):
        return None
    return None if detect(summary, directory(conn)) else summary


def _colleagues(conn: Conn, cid: str, kind: str) -> int | None:
    if kind == "idea":
        row = conn.execute(
            "SELECT 1 + count(*) AS n FROM idea_links WHERE idea_id = %s AND link_type IN ('joiner', 'plus_one')",
            (cid,),
        ).fetchone()
        return int(row["n"]) if row else 1
    if kind == "cluster":
        row = conn.execute("SELECT distinct_contributors FROM clusters WHERE id = %s", (cid,)).fetchone()
        return int(row["distinct_contributors"]) if row else None
    return None


def submitter_cards(conn: Conn, result: dict[str, Any]) -> list[dict[str, Any]]:
    """Find your crew, as the submitter may see it. `ref` is a position, never the other item's ID."""
    if not killswitch.is_on("matching.show", conn):
        return []
    areas = {a["id"]: a["name"] for a in _taxonomy_areas()}
    lobs = {x["id"]: x["name"] for x in _taxonomy_lobs()}
    cards: list[dict[str, Any]] = []
    with_desk = False
    for i, c in enumerate(result.get("candidates") or []):
        if c["label"] not in ("same", "related"):
            continue
        if c["visibility"] == "committee":
            with_desk = True
            continue
        row = conn.execute(
            "SELECT summary, area_ids, lobs FROM repo_files WHERE kfin_id = %s LIMIT 1", (c["cid"],)
        ).fetchone()
        if row is None:
            continue
        kind = c["type"]
        heading = (
            "In the Garage"
            if kind == "solution"
            else "Looked at before"
            if kind == "decision"
            else "In the Garage: colleagues are on this"
            if c["label"] == "same"
            else "Related"
        )
        cards.append(
            {
                "ref": f"m{i + 1}",
                "kind": kind,
                "label": c["label"],
                "heading": heading,
                "summary": _safe_summary(conn, row["summary"]),
                "area": next((areas.get(a) for a in row["area_ids"] or [] if a in areas), None),
                "stage": STAGE_WORDS.get(c["stage"] or "", "With the review desk"),
                "colleagues": _colleagues(conn, c["cid"], kind),
                "owning_lob": (lobs.get(row["lobs"][0]) if kind == "solution" and row["lobs"] else None),
            }
        )
    if with_desk:
        cards.append(
            {
                "ref": None,
                "kind": "with_desk",
                "label": "related",
                "heading": "A related idea is with the review desk",
            }
        )
    return cards


def _taxonomy_areas() -> list[dict[str, Any]]:
    from core.config import get_settings

    return list(_taxonomy(get_settings().company_repo_path)["areas"])


def _taxonomy_lobs() -> list[dict[str, Any]]:
    from core.config import get_settings

    return list(_taxonomy(get_settings().company_repo_path)["lobs"])
