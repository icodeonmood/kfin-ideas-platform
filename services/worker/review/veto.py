"""Desk decisions and the core committee's veto (§4.3, AT-B6-06).

Every core committee member sees what the desk decided (proposal, final call, reviewer's note) and the
disagreements people raised. Within the 5-working-day veto window (`rules/sla.md` `veto_window`) a member can
veto with a written reason: the item goes back to the queue assigned to them, the veto is written to
`audit_log` and counts as a correction. After the window closes a veto answers 409. The person hears only the
final outcome: if the member's call differs from the desk's, the message says it was reconsidered by the
committee; if it is the same, nothing new is sent.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from psycopg.types.json import Jsonb

from core.db import Conn
from embeddings import embed
from review.service import (
    ActionRefused,
    _card_text,
    _correction,
    _tagged,
    audited,
    refuse_own,
    staff_code,
)
from sla import engine


def desk_decisions(conn: Conn, limit: int = 200) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT r.id, r.ref_id, r.final, r.decided_at, r.decided_by, r.vetoed_by, u.staff_code, "
        "nullif(i.canvas->>'neutral_summary', '') AS summary, i.stage, "
        "(SELECT t.state FROM sla_timers t WHERE t.entity_type = 'review_item' AND t.entity_id = r.id::text "
        " AND t.stage = 'veto_window' ORDER BY t.id DESC LIMIT 1) AS window_state, "
        "(SELECT t.due_at FROM sla_timers t WHERE t.entity_type = 'review_item' AND t.entity_id = r.id::text "
        " AND t.stage = 'veto_window' ORDER BY t.id DESC LIMIT 1) AS window_due "
        "FROM review_items r JOIN ideas i ON i.idea_id = r.ref_id LEFT JOIN users u ON u.id = r.decided_by "
        "WHERE r.item_type = 'idea' AND r.decided_at IS NOT NULL ORDER BY r.decided_at DESC LIMIT %s",
        (limit,),
    ).fetchall()
    ids = [r["id"] for r in rows]
    notes = {
        r["review_item_id"]: r["note"]
        for r in conn.execute(
            "SELECT DISTINCT ON (review_item_id) review_item_id, note FROM corrections WHERE review_item_id = ANY(%s) "
            "AND note IS NOT NULL AND field LIKE 'value.%%' ORDER BY review_item_id, id",
            (ids,),
        ).fetchall()
    }  # the desk's note to the person, never a veto reason
    disagreements = conn.execute(
        "SELECT r.id, r.ref_id, r.created_at, nullif(i.canvas->>'neutral_summary', '') AS summary FROM review_items r "
        "JOIN ideas i ON i.idea_id = r.ref_id WHERE r.item_type = 'disagreement' AND r.state = 'open' "
        "ORDER BY r.created_at"
    ).fetchall()
    return {
        "decisions": [
            {
                "item_id": r["id"], "idea_id": r["ref_id"], "summary": r["summary"], "stage": r["stage"],
                "decision": r["final"], "decided_at": r["decided_at"].isoformat(), "decided_by": r["staff_code"],
                "note": notes.get(r["id"]), "vetoed": r["vetoed_by"] is not None,
                "veto_open": r["window_state"] == "running",
                "veto_until": r["window_due"].isoformat() if r["window_due"] else None,
            }
            for r in rows
        ],
        "disagreements": [
            {"item_id": d["id"], "idea_id": d["ref_id"], "summary": d["summary"], "at": d["created_at"].isoformat()}
            for d in disagreements
        ],
    }  # fmt: skip


def veto(
    conn: Conn, item_id: int, member: str, reason: str, now: dt.datetime | None = None
) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.UTC)
    with audited(conn), conn.transaction():
        item = conn.execute("SELECT * FROM review_items WHERE id = %s FOR UPDATE", (item_id,)).fetchone()
        if item is None or item["item_type"] != "idea":
            raise ActionRefused(404, "not_found")
        window = conn.execute(
            "SELECT id, due_at, state FROM sla_timers WHERE entity_type = 'review_item' AND entity_id = %s "
            "AND stage = 'veto_window' ORDER BY id DESC LIMIT 1 FOR UPDATE",
            (str(item_id),),
        ).fetchone()
        if (
            item["state"] != "decided"
            or window is None
            or window["state"] != "running"
            or now > window["due_at"]
        ):
            raise ActionRefused(409, "veto_window_closed")
        idea = conn.execute("SELECT * FROM ideas WHERE idea_id = %s", (item["ref_id"],)).fetchone()
        assert idea is not None
        refuse_own(conn, member, dict(idea), "veto")
        tagged = _tagged(conn, idea["idea_id"], reason, min_chars=10)
        code = staff_code(conn, member)
        conn.execute(
            "UPDATE review_items SET state = 'open', assigned_to = %s, vetoed_by = %s, veto_reason = %s, vetoed_at = %s, "
            "reasons = reasons || %s WHERE id = %s",
            (member, member, tagged, now, Jsonb({"vetoed_decision": item["final"]}), item_id),
        )
        conn.execute(
            "UPDATE sla_timers SET state = 'stopped', stopped_at = %s WHERE id = %s", (now, window["id"])
        )
        engine.start(conn, "review_item", str(item_id), "review", now=now)  # the member's own time limit
        _correction(
            conn,
            item_id,
            "desk_decision",
            item["final"],
            None,
            member,
            tagged,
            embed([_card_text(dict(idea))])[0],
        )  # vetoes count as corrections for learning (§5.1)
        conn.execute(
            "INSERT INTO audit_log (actor, action, entity, before, reason) VALUES (%s, 'review.veto', %s, %s, %s)",
            (code, f"review_item:{item_id}", Jsonb(item["final"]), tagged),
        )
        return {"state": "open", "assigned_to": member}
