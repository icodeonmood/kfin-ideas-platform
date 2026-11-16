"""What the review desk reads (A-API.desk `GET /desk`; S-R1): the queue, its counts, the summary sentence and the
sidebar's "Waiting on sharers". Everything is worked out on read from stored facts (`desk.queue`).

Routing (L-SORT.rules/7) waits on the desk lead's area-to-reviewer map; until it arrives every reviewer sees
every idea on the desk except their own (SHIP_PLAN §8 fallback: any reviewer, never the sharer).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from core.db import Conn
from desk import promises, queue, when
from desk.questions import SetFacts
from desk.store import code_of, now
from desk.window import Window

_QUEUE = """
SELECT i.id, i.idea_id, i.title, i.area, i.city, i.status, i.decide_by, i.contributor_code, i.shared_at,
       u.name AS sharer_name, coalesce(u.first_name, split_part(u.name, ' ', 1)) AS sharer_first_name,
       qs.sent_at, qs.seen_at, qs.due_at, qs.state AS set_state, qs.n_questions, qs.n_answered, qs.answered_at,
       d.choice, d.at AS decided_at,
       w.opens_at, w.closes_at, w.max_closes_at, w.extended_times,
       r.to_choice, r.at AS reversed_at
FROM ideas i
LEFT JOIN contributor_map cm ON cm.contributor_code = i.contributor_code
LEFT JOIN users u ON u.id = cm.user_id
LEFT JOIN LATERAL (
  SELECT s.state, s.sent_at, s.seen_at, s.due_at,
         (SELECT count(*) FROM questions q WHERE q.set_id = s.id) AS n_questions,
         (SELECT count(*) FROM questions q JOIN answers a ON a.question_id = q.id
           WHERE q.set_id = s.id AND a.sent_at IS NOT NULL) AS n_answered,
         (SELECT max(a.sent_at) FROM questions q JOIN answers a ON a.question_id = q.id WHERE q.set_id = s.id)
           AS answered_at
  FROM question_sets s WHERE s.idea_uuid = i.id AND s.state <> 'queued' ORDER BY s.created_at DESC LIMIT 1
) qs ON true
LEFT JOIN LATERAL (
  SELECT d.id, d.choice, d.at FROM idea_decisions d WHERE d.idea_uuid = i.id ORDER BY d.at DESC LIMIT 1
) d ON true
LEFT JOIN decision_windows w ON w.decision_id = d.id
LEFT JOIN decision_reversals r ON r.window_id = w.id
WHERE (i.status IN ('with_review_desk', 'needs_you') OR d.at > %(since)s)
  AND i.contributor_code IS DISTINCT FROM %(own)s
  AND (%(q)s::text IS NULL OR i.title ILIKE %(like)s OR i.idea_id ILIKE %(like)s OR u.name ILIKE %(like)s
       OR i.area ILIKE %(like)s)
"""


DOTS = {"normal": "blue", "warn": "amber", "bad": "red"}  # S-R1.rules/5


def _desk_idea(r: dict[str, Any]) -> queue.DeskIdea:
    facts = None
    if r["sent_at"] is not None:
        facts = SetFacts(
            int(r["n_questions"]),
            int(r["n_answered"]),
            r["sent_at"],
            r["seen_at"],
            r["due_at"],
            r["answered_at"],
            closed=r["set_state"] == "closed",
        )
    window = None
    if r["opens_at"] is not None:
        window = Window(
            r["opens_at"], r["closes_at"], r["max_closes_at"], int(r["extended_times"]), r["reversed_at"]
        )
    reversal = queue.Reversal(str(r["to_choice"]), r["reversed_at"]) if r["reversed_at"] else None
    return queue.DeskIdea(
        idea_id=str(r["idea_id"]), title=str(r["title"] or ""), sharer_name=str(r["sharer_name"] or "A colleague"),
        sharer_first_name=str(r["sharer_first_name"] or "the sharer"), area=str(r["area"] or ""),
        city=str(r["city"] or ""), status=str(r["status"]), decide_by=r["decide_by"], questions=facts,
        decision=r["choice"], decided_at=r["decided_at"], window=window, reversal=reversal,
    )  # fmt: skip


def _row_json(row: queue.Row) -> dict[str, Any]:
    return {
        "idea_id": row.idea_id, "title": row.title, "who": row.who, "questions": row.questions,
        "time_left": row.time_left, "variant": row.variant, "due_at": row.due_at.isoformat() if row.due_at else None,
        "decide_by": row.decide_by, "action": row.action, "action_kind": row.action_kind, "decision": row.decision,
        "committee": row.committee, "area": row.area,
    }  # fmt: skip


def desk(conn: Conn, user_id: str, tab: str = "waiting", sort: str = "time_left", q: str | None = None,
         at: dt.datetime | None = None) -> dict[str, Any]:  # fmt: skip
    """GET /desk: one tab's rows (sorted), every tab's count, the summary sentence and the sidebar's three most
    urgent ideas waiting on their sharers. A search narrows the rows and the counts alike."""
    t = at or now()
    p = promises.get()
    search = (q or "").strip() or None
    rows = conn.execute(
        _QUEUE,
        {"since": t - dt.timedelta(days=p.decided_this_week_days), "own": code_of(conn, user_id), "q": search,
         "like": f"%{search}%" if search else None},
    ).fetchall()  # fmt: skip
    ideas = [_desk_idea(dict(r)) for r in rows if r["decide_by"] is not None or r["decided_at"] is not None]
    chosen: queue.Tab = tab if tab in queue.TABS else "waiting"
    tabbed = [(i, queue.tab_of(i, t, p.decided_this_week_days)) for i in ideas]
    shown = [queue.row(i, k, t) for i, k in tabbed if k == chosen]
    sort_by: queue.Sort = sort if sort in queue.SORTS else "time_left"
    waiting = sorted(
        (queue.row(i, "waiting", t) for i, k in tabbed if k == "waiting"), key=lambda r: r.due_at or t
    )[:3]
    return {
        "items": [_row_json(r) for r in queue.sort_rows(shown, chosen, sort_by)],
        "total": len(shown),
        "counts": queue.counts(ideas, t, p.decided_this_week_days),
        "summary": queue.summary(ideas, t, p.decided_this_week_days),
        "tab": chosen,
        "sort": sort_by,
        "waiting_on_sharers": [
            {"idea_id": r.idea_id, "title": r.title, "dot": DOTS[r.variant or "normal"]} for r in waiting
        ],
        "now": t.astimezone(when.IST).isoformat(),
    }
