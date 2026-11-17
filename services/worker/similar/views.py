"""`GET /ideas/:id/similar` (A-API, L-SIMILAR.rules/4–6, C-SIMGRID, BLD-C092): SimilarMatch[] read from the stored
links, so Check it never waits on matching.

- Who: the sharer of the draft or idea, and the review desk and the Ones Committee for shared ideas. Anyone else
  gets None (answer 404). With `matching.show` off the sharer sees none; the desk keeps the list.
- What: the ideas found for this one (forward links), and for a shared idea also the newer shared ideas that
  found it (reverse links: "Colleagues on something similar" for its sharer, "Similar ideas" for the reviewer).
  Merged ideas resolve to the surviving idea; one entry per idea, the stronger link kept, `close` first.
- Each `idea` is the IdeaPreview this viewer may see (masked, names unless hidden from the Wall); for the desk its
  `compare` sits next to this idea's (`compare_with`). `my_request` is the viewer's own team-up request to that
  idea (lane F's table, read only), unless they withdrew it.
"""

from __future__ import annotations

from typing import Any

from core import killswitch
from core.db import Conn
from onepc.context import open_text
from similar.matching import survivor
from similar.preview import Viewer, find_idea, idea_preview, iso, person_refs

RANK = {"close": 0, "related": 1}


def _links(conn: Conn, idea: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {**dict(r), "forward": True}
        for r in conn.execute(
            "SELECT other_idea_uuid AS other, strength, reason, rank, created_at FROM similar_links "
            "WHERE idea_uuid = %s",
            (idea["id"],),
        ).fetchall()
    ]
    if idea.get("idea_id") and idea.get("shared_at") is not None:
        rows += [
            {**dict(r), "forward": False}
            for r in conn.execute(
                "SELECT l.idea_uuid AS other, l.strength, l.reason, l.rank, l.created_at FROM similar_links l "
                "JOIN ideas i ON i.id = l.idea_uuid WHERE l.other_idea_uuid = %s AND i.idea_id IS NOT NULL "
                "AND i.shared_at IS NOT NULL AND i.status NOT IN ('draft', 'withdrawn')",
                (idea["id"],),
            ).fetchall()
        ]
    return rows


def my_request(conn: Conn, other_uuid: str, viewer: Viewer) -> dict[str, Any] | None:
    """TeamUpRequest from the viewer to `other_uuid` (the latest, unless withdrawn)."""
    if not viewer.codes:
        return None
    r = conn.execute(
        "SELECT r.id, r.from_code, r.note_encrypted, r.state, r.lead_reason_encrypted, r.sent_at, r.answered_at, "
        "i.idea_id FROM teamup_requests r JOIN ideas i ON i.id = r.idea_uuid WHERE r.idea_uuid = %s "
        "AND r.from_code = ANY(%s) ORDER BY r.sent_at DESC LIMIT 1",
        (other_uuid, list(viewer.codes)),
    ).fetchone()
    if r is None or r["state"] == "withdrawn":
        return None
    rid = str(r["id"])
    brought = [
        {
            "id": str(b["idea_id"] or b["id"]),
            "title": str(b["title"] or b["idea_id"] or ""),
            "status": b["status"],
        }
        for b in conn.execute(
            "SELECT i.id, i.idea_id, i.title, i.status FROM teamup_brought t JOIN ideas i ON i.id = t.idea_uuid "
            "WHERE t.request_id = %s ORDER BY i.idea_id NULLS LAST",
            (rid,),
        ).fetchall()
    ]
    code = str(r["from_code"])
    out: dict[str, Any] = {
        "id": rid,
        "idea_id": str(r["idea_id"]),
        "from": person_refs(conn, [code], names_always=True)[code],
        "note": open_text("teamup_requests", "note_encrypted", rid, r["note_encrypted"]) or "",
        "brought": brought,
        "state": r["state"],
        "sent_at": iso(r["sent_at"]),
    }
    reason = open_text("teamup_requests", "lead_reason_encrypted", rid, r["lead_reason_encrypted"])
    if reason:
        out["lead_reason"] = reason
    if r["answered_at"] is not None:
        out["answered_at"] = iso(r["answered_at"])
    return out


def matches_for(conn: Conn, key: str, viewer: Viewer) -> list[dict[str, Any]] | None:
    """SimilarMatch[] for the draft or idea `key` (IDEA- reference or row ID), or None (answer 404)."""
    idea = find_idea(conn, key)
    if idea is None:
        return None
    owner = idea["contributor_code"] in viewer.codes
    shared = (
        idea.get("idea_id") is not None and idea.get("shared_at") is not None and idea["status"] != "draft"
    )
    if not (owner or (viewer.desk and shared)):
        return None
    if not viewer.desk and not killswitch.is_on("matching.show", conn):
        return []

    best: dict[str, dict[str, Any]] = {}
    for link in _links(conn, idea):
        row = survivor(conn, str(link["other"]))
        if (
            row is None
            or str(row["id"]) == str(idea["id"])
            or row["contributor_code"] == idea["contributor_code"]
        ):
            continue
        key_ = str(row["id"])
        order = (RANK[link["strength"]], not link["forward"], link["rank"], -link["created_at"].timestamp())
        if key_ not in best or order < best[key_]["order"]:
            best[key_] = {"order": order, "strength": link["strength"], "reason": link["reason"]}

    out: list[dict[str, Any]] = []
    for other, link in sorted(best.items(), key=lambda kv: kv[1]["order"]):
        preview = idea_preview(
            conn, other, viewer=viewer, compare_with=str(idea["id"]) if viewer.desk else None
        )
        if preview is None:
            continue
        match: dict[str, Any] = {"idea": preview, "strength": link["strength"], "reason": link["reason"]}
        request = my_request(conn, other, viewer)
        if request is not None:
            match["my_request"] = request
        out.append(match)
    return out


def keep_separate(conn: Conn, key: str, viewer: Viewer, *, on: bool = True) -> dict[str, Any] | None:
    """ "Keep mine separate" on Check it (L-SIMILAR.rules/8, C-SIMGRID.grid/4): recorded on the draft and on each
    similar idea found so far, for the reviewer ("2 found while she wrote. She kept hers separate."). `on=False` is
    "Show them again". The sharer's own unsent draft only, else None (answer 404). A merge request stays as it is."""
    idea = find_idea(conn, key)
    if idea is None or idea["contributor_code"] not in viewer.codes or idea["status"] != "draft":
        return None
    with conn.transaction():
        conn.execute("UPDATE ideas SET kept_separate = %s WHERE id = %s", (on, idea["id"]))
        if on:
            conn.execute(
                "UPDATE similar_links SET outcome = 'kept_separate' WHERE idea_uuid = %s "
                "AND (outcome IS NULL OR outcome = 'previewed')",
                (idea["id"],),
            )
        else:
            conn.execute(
                "UPDATE similar_links SET outcome = NULL WHERE idea_uuid = %s AND outcome = 'kept_separate'",
                (idea["id"],),
            )
        found = conn.execute(
            "SELECT count(*) AS n FROM similar_links WHERE idea_uuid = %s AND found_while = 'drafting'",
            (idea["id"],),
        ).fetchone()
    return {"kept_separate": on, "found_while_drafting": int(found["n"]) if found else 0}
