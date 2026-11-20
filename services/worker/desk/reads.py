"""What the review desk reads (A-API.desk `GET /desk`; S-R1): the queue, its counts, the summary sentence and the
sidebar's "Waiting on sharers". Everything is worked out on read from stored facts (`desk.queue`).

Routing (L-SORT.rules/7) waits on the desk lead's area-to-reviewer map; until it arrives every reviewer sees
every idea on the desk except their own (SHIP_PLAN §8 fallback: any reviewer, never the sharer).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any

from core.db import Conn
from desk import clock, promises, queue, when
from desk.questions import SetFacts
from desk.store import (
    CUSTOMER_DETAIL,
    DESK_SEES,
    FILES_CHECKED,
    REVIEWERS,
    SHOWN_FILE,
    code_of,
    has_role,
    joined,
    now,
    person_by_code,
)
from desk.window import Window

_QUEUE = """
SELECT i.id, i.idea_id, i.title, i.area, i.city, i.status, i.decide_by, i.contributor_code, i.shared_at,
       u.name AS sharer_name, coalesce(u.first_name, split_part(u.name, ' ', 1)) AS sharer_first_name,
       qs.set_id, qs.sent_at, qs.seen_at, qs.due_at, qs.state AS set_state, qs.n_questions, qs.n_answered, qs.answered_at,
       d.choice, d.at AS decided_at,
       w.opens_at, w.closes_at, w.max_closes_at, w.extended_times,
       r.to_choice, r.at AS reversed_at
FROM ideas i
LEFT JOIN contributor_map cm ON cm.contributor_code = i.contributor_code
LEFT JOIN users u ON u.id = cm.user_id
LEFT JOIN LATERAL (
  SELECT s.id AS set_id, s.state, s.sent_at, s.seen_at, s.due_at,
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
        set_id=str(r["set_id"]) if r["set_id"] else None,
    )  # fmt: skip


def _row_json(row: queue.Row) -> dict[str, Any]:
    return {
        "idea_id": row.idea_id, "title": row.title, "who": row.who, "questions": row.questions,
        "time_left": row.time_left, "variant": row.variant, "due_at": row.due_at.isoformat() if row.due_at else None,
        "decide_by": row.decide_by, "action": row.action, "action_kind": row.action_kind, "decision": row.decision,
        "committee": row.committee, "area": row.area, "asked": row.asked, "answered": row.answered, "set_id": row.set_id,
    }  # fmt: skip


def _read_only(row: queue.Row) -> queue.Row:
    """A row for a reader who is not on the review desk (BLD-B270): "Remind {name}" writes, so it becomes "Open";
    "Open" and "Read answers" only go to S-R2."""
    return dataclasses.replace(row, action="Open", action_kind="open") if row.action_kind == "remind" else row


def desk(conn: Conn, user_id: str, tab: str = "waiting", sort: str = "time_left", q: str | None = None,
         at: dt.datetime | None = None) -> dict[str, Any]:  # fmt: skip
    """GET /desk: one tab's rows (sorted), every tab's count, the summary sentence and the sidebar's three most
    urgent ideas waiting on their sharers. A search narrows the rows and the counts alike."""
    t = at or now()
    p = promises.get()
    from desk.clocks import return_due

    return_due(
        conn, t
    )  # a Not now whose date has come is back on the desk now, timer or not (L-DECIDE.rules/7)
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
    if not has_role(conn, user_id, REVIEWERS):  # the desk's actions are the review desk's (BLD-B270)
        shown = [_read_only(r) for r in shown]
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


# ---------------------------------------------------------------------------------------------------------------
# The reviewer's page (A-API.desk GET /desk/ideas/:id; S-R2) and the listen script (L-LISTEN)
# ---------------------------------------------------------------------------------------------------------------
STATUS_LABELS = {
    "checking": "Checking", "with_review_desk": "With the review desk", "needs_you": "Needs you", "picked": "Picked",
    "being_built": "Being built", "shipped": "Shipped", "not_now": "Not now", "not_picked": "Not picked",
    "withdrawn": "Withdrawn", "merged": "Merged",
}  # fmt: skip
PILLS = {"needs_you": "warn", "not_now": "warn", "shipped": "ok", "not_picked": "neutral", "withdrawn": "neutral",
         "merged": "neutral"}  # fmt: skip
HIDDEN_KINDS = {"folio": "Folio", "pan": "PAN", "phone": "Phone number", "email": "Email", "account": "Account number",
                "aadhaar": "Aadhaar", "name": "Name"}  # fmt: skip
# L-HIDE.detect's "Label shown" for each kind, as the desk's "Shown, because …" lines name them
DETECT_LABELS = {"folio": "Folio", "pan": "PAN", "phone": "Phone", "email": "Email", "account": "Account",
                 "aadhaar": "Aadhaar", "name": "Name"}  # fmt: skip

_BRINGS = {"saves_time": "saves time", "saves_cost": "saves cost", "earns_revenue": "earns revenue",
           "less_outside_tools": "cuts reliance on outside tools", "not_sure": "not sure yet"}  # fmt: skip
CHECKED = FILES_CHECKED


def _size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB".replace(".0 MB", " MB")
    return f"{max(1, round(n / 1024))} KB"


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _brings(values: list[str]) -> str:
    if "saves_time" in values and "saves_cost" in values:  # the board's "saves time and cost"
        rest = [_BRINGS[v] for v in values if v not in ("saves_time", "saves_cost")]
        return _and(["saves time and cost", *rest]) if rest else "saves time and cost"
    return _and([_BRINGS.get(v, v) for v in values]) if values else ""


Hidden = list[
    tuple[str, str | None]
]  # each hidden detail's kind and its masked hint ("Folio ••••89"), if stored


def _kind_names(kinds: list[str]) -> list[str]:
    """'Folio', then 'phone number': the first capitalised, the rest as they sit in a sentence."""
    names = [HIDDEN_KINDS.get(k, k) for k in dict.fromkeys(kinds)]
    first, *rest = names
    return [first, *[n.lower() if n not in ("PAN", "Aadhaar") else n for n in rest]]


def _hidden_line(hidden: Hidden) -> str:
    """The own words' line: "Folio hidden." (DeskIdea board)."""
    return _and(_kind_names([k for k, _ in hidden])) + " hidden." if hidden else ""


def _hidden_from_everyone(hidden: Hidden) -> str:
    """The Attached part's last sentence (DeskIdea board): "Folio ••••89 is hidden from everyone." with the masked
    hint when the one detail stores one; "Folio is hidden from everyone." without; "Folio and phone number are hidden
    from everyone." for two kinds."""
    if not hidden:
        return ""
    kind, masked = hidden[0]
    if len(hidden) == 1 and masked and "•" in masked:  # a hint shows the kept characters: "Folio ••••89"
        name = HIDDEN_KINDS.get(kind, kind)
        return f"{masked if not masked.startswith('•') else f'{name} {masked}'} is hidden from everyone."
    names = _kind_names([k for k, _ in hidden])
    return f"{_and(names)} {'is' if len(names) == 1 else 'are'} hidden from everyone."


def _evidence_text(files: list[dict[str, Any]], hidden: Hidden) -> str:
    """The Attached part in words (board DeskIdea): "One file: branch-call-log-nov.pdf. Folio ••••89 is hidden from
    everyone." File names stand in for what each file is until the assistant describes them."""
    from desk.listen import _NUMBERS

    sent = [f for f in files if not f["answer_id"]]
    bits = []
    if sent:
        n = len(sent)
        names = "; ".join(str(f["name"]) for f in sent)
        bits.append(f"{_NUMBERS[n] if n < len(_NUMBERS) else n} file{'s' * (n != 1)}: {names}.")
    if hidden:
        bits.append(_hidden_from_everyone(hidden))
    return " ".join(bits)


def _hidden(conn: Conn, idea_uuid: Any) -> Hidden:
    """The details hidden from everyone, one per value: a desk "Hide this" adds a row for each copy it masks, so the
    rows are grouped by vault tag (L-HIDE.rules/7). Shown details are not here (`_shown`). Only what the sharer has
    given the desk: never the desk's own words (a question, a reason) nor an answer still in draft, which stays the
    sharer's until sent (non-negotiable 7; BLD-B247). `_shown` reads under the same filter."""
    return [
        (str(r["kind"]), str(r["masked"]) if r["masked"] else None)
        for r in conn.execute(
            "SELECT kind, masked FROM (SELECT DISTINCT ON (coalesce(vault_tag, id::text)) kind, masked, created_at "
            "FROM hidden_details WHERE idea_uuid = %s AND state = 'hidden' AND source <> 'desk' AND NOT (source = "
            "'answer' AND NOT EXISTS (SELECT 1 FROM answers a WHERE a.id::text = source_id AND a.sent_at IS NOT NULL)) "
            "ORDER BY coalesce(vault_tag, id::text), created_at) d ORDER BY created_at",
            (idea_uuid,),
        )
    ]


SHOWN_BECAUSE = {
    "scheme_or_product_code": "it’s a scheme or product code",
    "internal_reference": "it’s an internal reference",
    "made_up_example": "it’s made up for the example",
}  # L-HIDE.rules/6, C-HIDDEN.list/1


def _shown(conn: Conn, idea_uuid: Any) -> list[dict[str, Any]]:
    """L-HIDE.rules/6: what the sharer chose to show, and why, as the review desk reads it: "Folio shown, because
    it’s an internal reference." One line per value (grouped by vault tag; the latest showing), oldest first. The
    value itself is never here: the desk reads it in the masked copy's place, as everyone does."""
    from desk.store import person_by_user

    rows = conn.execute(
        "SELECT kind, reason, shown_by, shown_at FROM (SELECT DISTINCT ON (coalesce(vault_tag, id::text)) kind, "
        "reason, shown_by, shown_at FROM hidden_details WHERE idea_uuid = %s AND state = 'shown' AND source <> 'desk' "
        "AND NOT (source = 'answer' AND NOT EXISTS (SELECT 1 FROM answers a WHERE a.id::text = source_id "
        "AND a.sent_at IS NOT NULL)) "
        "ORDER BY coalesce(vault_tag, id::text), shown_at DESC) d ORDER BY shown_at, kind",
        (idea_uuid,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        kind, reason = str(r["kind"]), str(r["reason"])
        label = DETECT_LABELS.get(kind, kind)
        out.append({
            "kind": kind, "kind_label": label, "reason": reason, "because": SHOWN_BECAUSE.get(reason, ""),
            "by": person_by_user(conn, str(r["shown_by"]) if r["shown_by"] else None).first_name,
            "at": r["shown_at"].isoformat(), "line": f"{label} shown, because {SHOWN_BECAUSE.get(reason, '')}.",
        })  # fmt: skip
    return out


def _said_at(t: dt.datetime, at: dt.datetime) -> str:
    """When something was said on the desk: "today 11:20 am" (DeskIdea board), else the day and the time with a
    comma between them: "Monday 16 November, 11:20 am", "yesterday, 6:10 pm"."""
    d = when.which_day(t, at)
    return f"{d} {when.clock(t)}" if d == "today" else f"{d}, {when.clock(t)}"


def _checked_files(
    conn: Conn, idea_uuid: Any, states: tuple[str, ...] = FILES_CHECKED
) -> list[dict[str, Any]]:
    """Files in `states` (the checked ones; the desk's view adds those holding a customer detail, DEC-107, each with
    its `customer_detail` marker). Never one still checking, infected or locked; a draft answer's files stay the
    sharer's until the answer is sent."""
    return [
        {**f, "customer_detail": f["file_state"] == CUSTOMER_DETAIL}
        for f in conn.execute(
            "SELECT id, name, bytes, pages, hidden_note, uploaded_by_code, answer_id, created_at, file_state, "  # noqa: S608 (SHOWN_FILE is fixed text)
            "(SELECT a.sent_at FROM answers a WHERE a.id = attachments.answer_id) AS answer_sent_at, "
            "(SELECT a.by_code FROM answers a WHERE a.id = attachments.answer_id) AS answer_by "
            f"FROM attachments WHERE idea_uuid = %s AND kind = 'file' AND {SHOWN_FILE} "
            "AND (answer_id IS NULL OR EXISTS (SELECT 1 FROM answers a WHERE a.id = attachments.answer_id "
            "AND a.sent_at IS NOT NULL)) ORDER BY created_at, id",
            (idea_uuid, list(states)),
        )
    ]


def _questions(
    conn: Conn, idea_uuid: Any, at: dt.datetime, viewer_id: str | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Every question sent on this idea, pinned to its part, with its answer once sent (S-R2.left/3). "You asked"
    for the viewer's own questions, "{first name} asked" for another reviewer's (reference/copy/DeskIdea.md). An
    answer's files are those the desk may open (DEC-107), each with its `customer_detail` marker."""
    from desk.store import person_by_code, person_by_user, unseal

    out: dict[str, list[dict[str, Any]]] = {}
    for r in conn.execute(
        "SELECT q.id, q.part, q.text_encrypted, s.sent_at, s.by_user_id, a.id AS answer_id, a.text_encrypted AS "
        "answer_encrypted, a.sent_at AS answered_at, a.by_code FROM questions q JOIN question_sets s ON s.id = q.set_id "
        "LEFT JOIN answers a ON a.question_id = q.id AND a.sent_at IS NOT NULL "
        "WHERE s.idea_uuid = %s AND s.state <> 'queued' ORDER BY s.sent_at, q.seq",
        (idea_uuid,),
    ).fetchall():
        asked_by = person_by_user(conn, r["by_user_id"])
        mine = viewer_id is not None and str(r["by_user_id"]) == str(viewer_id)
        item: dict[str, Any] = {
            "id": str(r["id"]), "text": unseal(r["text_encrypted"], "questions", "text_encrypted", str(r["id"])),
            "asked_at": r["sent_at"].isoformat(), "asked_by": asked_by.first_name,
            "asked_line": f"{'You' if mine else asked_by.first_name} asked, {_said_at(r['sent_at'], at)}",
            "state": "Answered" if r["answer_id"] else "Not answered yet", "answer": None,
        }  # fmt: skip
        if r["answer_id"]:
            by = person_by_code(conn, r["by_code"])
            files = conn.execute(
                "SELECT id, name, hidden_note, file_state FROM attachments WHERE answer_id = %s AND "  # noqa: S608 (fixed text)
                f"{SHOWN_FILE} ORDER BY created_at, id",
                (r["answer_id"], list(DESK_SEES)),
            ).fetchall()
            item["answer"] = {
                "id": str(r["answer_id"]),
                "text": unseal(r["answer_encrypted"], "answers", "text_encrypted", str(r["answer_id"])),
                "at": r["answered_at"].isoformat(), "by": by.first_name,
                "line": f"{by.first_name} answered, {_said_at(r['answered_at'], at)}",
                "files": [{"id": f["id"], "name": f["name"], "hidden": f["hidden_note"],
                           "customer_detail": f["file_state"] == CUSTOMER_DETAIL} for f in files],
            }  # fmt: skip
        out.setdefault(str(r["part"]), []).append(item)
    return out


def _file_artefacts(conn: Conn, files: list[dict[str, Any]], at: dt.datetime) -> list[dict[str, Any]]:
    """The Attachments card's file rows (S-R2.left/2, DeskIdea board), each marked when it holds a customer detail
    (DEC-107): "Attached by Kavya. 140 KB, 3 pages. A phone number on page 2 is hidden." and, for a file sent with
    the answers, "Added with Kavya’s answers today." with its hidden line."""
    out: list[dict[str, Any]] = []
    for f in files:
        hidden = f" {f['hidden_note']}" if f["hidden_note"] else ""
        if f["answer_id"]:
            who = person_by_code(conn, f["answer_by"] or f["uploaded_by_code"]).first_name
            d = when.which_day(f["answer_sent_at"], at) if f["answer_sent_at"] else ""
            day = f" {d}" if d in ("today", "yesterday") else f" on {d}" if d else ""
            line = f"Added with {who}’s answers{day}.{hidden}"
        else:
            by = person_by_code(conn, f["uploaded_by_code"]).first_name
            pages = f", {f['pages']} page{'s' * (f['pages'] != 1)}" if f["pages"] else ""
            line = f"Attached by {by}. {_size(int(f['bytes']))}{pages}.{hidden}"
        out.append({"kind": "file", "id": f["id"], "title": f["name"], "line": line, "action": "Open",
                    "customer_detail": f["customer_detail"]})  # fmt: skip
    return out


def _who(affects: list[str] | None) -> str:
    """Who it affects, as the DeskIdea board reads it: "Investors, KFin teams." """
    text = ", ".join(a for a in (affects or []) if a)
    return text if not text or text.endswith(".") else f"{text}."


def _part_texts(
    conn: Conn, idea: dict[str, Any], files: list[dict[str, Any]], hidden: Hidden
) -> dict[str, str]:
    """Each part's words as the idea holds them (S-R2.left/3); the worth part is shown as tiles."""
    fix = conn.execute("SELECT how, included FROM idea_fix WHERE idea_uuid = %s", (idea["id"],)).fetchone()
    return {
        "summary": idea["summary"] or "", "often": idea["often"] or "", "who": _who(idea["affects"]),
        "cost": "", "evidence": _evidence_text(files, hidden),
        "fix": (fix["how"] or "") if fix and fix["included"] else "",
    }  # fmt: skip


def _parts(texts: dict[str, str], asked: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Each part for S-R2's left column, with `empty`, the words it reads when it has no text (S-R2.panel, BLD-B264):
    "No fix suggested. It was optional." for Fix, "Nothing attached." for Attached, "Not given." for the rest."""
    from desk.questions import PART_EMPTY, PART_NAMES, PARTS

    return [
        {
            "part": p,
            "name": PART_NAMES[p],
            "text": texts[p],
            "empty": PART_EMPTY[p],
            "questions": asked.get(p, []),
        }
        for p in PARTS
    ]


def _own_words(conn: Conn, idea_uuid: Any) -> list[dict[str, Any]]:
    """The sharer's own words, the masked copy (L-REVIEW.open/3)."""
    from desk.store import unseal

    return [
        {"id": str(m["id"]), "seq": m["seq"], "via": m["via"], "at": m["created_at"].isoformat(),
         "text": unseal(m["text_encrypted"], "idea_messages", "text_encrypted", str(m["id"]))}
        for m in conn.execute("SELECT * FROM idea_messages WHERE idea_uuid = %s ORDER BY seq", (idea_uuid,))
    ]  # fmt: skip


_MERGED_IN = """
WITH RECURSIVE chain(id) AS (
  SELECT id FROM ideas WHERE merged_into = %s AND status = 'merged'
  UNION SELECT i.id FROM ideas i JOIN chain c ON i.merged_into = c.id WHERE i.status = 'merged'
)
SELECT i.*, (SELECT max(m.at) FROM merges m WHERE m.merged_idea_uuid = i.id AND m.reversed_at IS NULL) AS merged_at,
       l.idea_id AS into_idea_id
FROM chain c JOIN ideas i ON i.id = c.id JOIN ideas l ON l.id = i.merged_into
ORDER BY coalesce(i.shared_at, i.created_at), i.id
"""


def _contributions(conn: Conn, idea: dict[str, Any], at: dt.datetime, viewer_id: str) -> list[dict[str, Any]]:
    """L-MERGE.effects/3: every idea merged into this one, through the whole `merged_into` chain, as a contribution
    under its sharer's first name: its parts, the answers its sharer sent, its words and its files. Files are gated
    as the lead's are: checked, or marked when they hold a customer detail (DEC-107)."""
    out: list[dict[str, Any]] = []
    for c in conn.execute(_MERGED_IN, (idea["id"],)).fetchall():
        sharer = person_by_code(conn, c["contributor_code"])
        files = _checked_files(conn, c["id"], DESK_SEES)
        texts = _part_texts(conn, c, files, _hidden(conn, c["id"]))
        out.append({
            "idea_id": c["idea_id"], "title": c["title"] or "", "into": c["into_idea_id"],
            "merged_at": c["merged_at"].isoformat() if c["merged_at"] else None,
            "sharer": sharer.as_json(), "label": f"{sharer.first_name}’s idea, {c['idea_id']}",
            "parts": _parts(texts, _questions(conn, c["id"], at, viewer_id)),
            "files": _file_artefacts(conn, files, at), "own_words": _own_words(conn, c["id"]),
        })  # fmt: skip
    return out


def _queued(conn: Conn, idea: dict[str, Any], user_id: str) -> dict[str, Any] | None:
    """The question set this reviewer queued and has not sent: the panel's Asking state opens with it (S-R2.panel,
    J-REVIEW/A1). A queued set is its reviewer's alone, so another reviewer's is never returned; the desk's lists
    leave queued sets out (L-REVIEW.queue). The panel saves its queue as it changes (`asking.save_queue`, BLD-B272):
    `rev` is the stored save's revision (0 for a set from before), which the panel's next save carries as its `base`.
    A queue emptied by its reviewer is kept with no questions, so its revision still counts."""
    from desk import questions
    from desk.store import person_by_code, unseal

    s = conn.execute(
        "SELECT id, time_to_answer, queue_rev FROM question_sets WHERE idea_uuid = %s AND state = 'queued' "
        "AND by_user_id = %s ORDER BY created_at DESC LIMIT 1",
        (idea["id"], user_id),
    ).fetchone()
    if s is None:
        return None
    asked = [
        {"id": str(q["id"]), "part": q["part"], "part_name": questions.PART_NAMES.get(str(q["part"]), ""),
         "text": unseal(q["text_encrypted"], "questions", "text_encrypted", str(q["id"])),
         "suggested": bool(q["suggested"])}
        for q in conn.execute(
            "SELECT id, part, text_encrypted, suggested FROM questions WHERE set_id = %s ORDER BY seq", (s["id"],)
        ).fetchall()
    ]  # fmt: skip
    first = person_by_code(conn, idea["contributor_code"]).first_name
    return {
        "set_id": str(s["id"]), "questions": asked, "time_to_answer": s["time_to_answer"],
        "ready_line": questions.ready_line(len(asked)), "send_label": questions.send_label(len(asked), first),
        "rev": int(s["queue_rev"] or 0),
    }  # fmt: skip


def _panel(conn: Conn, idea: dict[str, Any], user_id: str, at: dt.datetime) -> dict[str, Any]:
    """Which working state the panel opens in (L-REVIEW.panel), with what it shows. While the desk can still ask
    (Reviewing, Answered), `queued` carries the questions this reviewer queued and has not sent."""
    from desk import committee, questions

    if idea["status"] == "merged":  # first: a Not now that came back and was then merged shows the merge
        return {"state": "merged"}
    decision = committee.for_idea(conn, str(idea["id"]), user_id, at, lines="reviewer")
    lines = (
        decision.pop("lines") if decision is not None else None
    )  # the reviewer's words (DeskIdea, Decided)
    if decision is not None and idea["status"] not in ON_DESK_STATUSES:
        return {"state": "decided", "decision": decision, "lines": lines}
    s = conn.execute(
        "SELECT * FROM question_sets WHERE idea_uuid = %s AND state NOT IN ('queued', 'closed') "
        "ORDER BY created_at DESC LIMIT 1",
        (idea["id"],),
    ).fetchone()
    if s is None:
        return {"state": "reviewing", "decision": decision, "queued": _queued(conn, idea, user_id)}
    n = conn.execute(
        "SELECT count(*) AS n, count(a.sent_at) AS answered, max(a.sent_at) AS answered_at FROM questions q "
        "LEFT JOIN answers a ON a.question_id = q.id AND a.sent_at IS NOT NULL WHERE q.set_id = %s",
        (s["id"],),
    ).fetchone()
    assert n is not None
    facts = questions.SetFacts(int(n["n"]), int(n["answered"]), s["sent_at"], s["seen_at"], s["due_at"],
                               n["answered_at"])  # fmt: skip
    c = clock.countdown(s["due_at"], at)
    sent_line = f"Sent {when.which_day(s['sent_at'], at)}, {when.clock(s['sent_at'])}."
    if s["seen_at"]:
        sent_line += f" Seen {when.clock(s['seen_at'])}."
    common = {
        "set_id": str(s["id"]), "count": facts.count, "answered": facts.answered, "due_at": s["due_at"].isoformat(),
        "countdown": c.label("to answer"), "variant": c.variant, "sent_line": sent_line,
        "decide_by_line": f"Decide by {when.day(idea['decide_by'], at)}." if idea["decide_by"] else None,
    }  # fmt: skip
    if questions.state(facts) == "answered":
        title = {1: "Answered", 2: "Both answered"}.get(facts.count) or f"All {facts.count} answered"
        spare = questions.spare_line(n["answered_at"], s["due_at"]) if n["answered_at"] else None
        return {"state": "answered", "title": title, "spare_line": spare, **common,
                "queued": _queued(conn, idea, user_id)}  # fmt: skip
    sharer_first = person_by_code(conn, idea["contributor_code"]).first_name
    return {"state": "sent", "title": f"Waiting on {sharer_first}", **common}


ON_DESK_STATUSES = frozenset({"with_review_desk", "needs_you"})


def reviewer_idea(conn: Conn, ref: str, user_id: str, at: dt.datetime | None = None) -> dict[str, Any]:
    """Everything a reviewer needs to decide on one idea, on one page (S-R2.left, S-R2.panel). Raw words are the
    masked copy (L-REVIEW.open/3); unmasked hidden details never reach the desk."""
    from desk import revise, worth
    from desk.store import READERS, is_own, load_idea, person_by_code

    t = at or now()
    idea = load_idea(conn, ref)
    sharer = person_by_code(conn, idea["contributor_code"])
    own = is_own(conn, user_id, idea)
    shared_at = idea["shared_at"] or idea["created_at"]
    sorting = [
        worth.KIND_LABELS.get(str(idea["kind"]), "").lower(),
        str(idea["area"] or ""),
        _brings(list(idea["brings"])),
    ]
    sorting_line = ", ".join(s for s in sorting if s)
    heading = f"Shared {when.day(shared_at, t)} by {joined(sharer.name, sharer.area or idea['area'], idea['city'])}."
    if idea["sorting_confirmed_at"] and sorting_line:
        heading += f" Sorting confirmed by {sharer.first_name}: {sorting_line[0].lower() + sorting_line[1:]}."
    messages = _own_words(conn, idea["id"])
    hidden = _hidden(conn, idea["id"])
    # the desk opens a file holding a customer detail, marked (DEC-107)
    files = _checked_files(conn, idea["id"], DESK_SEES)
    similar_n = conn.execute(
        "SELECT count(*) AS n FROM similar_links WHERE idea_uuid = %s AND found_while = 'drafting'",
        (idea["id"],),
    ).fetchone()
    # the idea as shared is version 1, as lanes C and E count it (E-ENTITIES: "3 versions. Title changed once,
    # sorting confirmed."); a row for the shared version, with no changed fields, is not counted twice
    versions = conn.execute(
        "SELECT count(*) FILTER (WHERE cardinality(changed_fields) > 0) AS edits, "
        "count(*) FILTER (WHERE 'title' = ANY(changed_fields)) AS titles FROM idea_versions WHERE idea_uuid = %s",
        (idea["id"],),
    ).fetchone()
    first = sharer.first_name
    artefacts = _file_artefacts(conn, files, t)
    if messages:  # the day of the first message, which is when they wrote them (DeskIdea board)
        wrote = dt.datetime.fromisoformat(messages[0]["at"]).astimezone(when.IST)
        artefacts.append({"kind": "own_words", "title": f"{first}’s own words",
                          "line": " ".join(x for x in (f"As {first} wrote them on {when.DAYS[wrote.weekday()]}, before the draft.",
                                                       _hidden_line(hidden)) if x),
                          "action": "Read"})  # fmt: skip
    if similar_n and similar_n["n"]:
        n = int(similar_n["n"])
        kept = f" {first} kept it separate." if idea["kept_separate"] else ""
        artefacts.append({"kind": "similar_found", "title": "Similar ideas",
                          "line": f"{n} found while {first} wrote.{kept}", "action": "Compare"})  # fmt: skip
    if versions and versions["edits"]:  # only once it has been changed
        n, titles = 1 + int(versions["edits"]), int(versions["titles"])
        bits = [f"{n} version{'s' * (n != 1)}."]
        if titles:
            bits.append(
                f"Title changed {when.times(titles)}"
                + (", sorting confirmed." if idea["sorting_confirmed_at"] else ".")
            )
        artefacts.append({"kind": "versions", "title": "Draft history", "line": " ".join(bits), "action": "See changes"})  # fmt: skip
    sharer_worth, reviewer_worth, revision = revise.current(conn, str(idea["id"]))
    parts = _parts(_part_texts(conn, idea, files, hidden), _questions(conn, idea["id"], t, user_id))
    # C-SHEET-MERGE.after (BLD-B266): a row is Merged both ways, when the other idea joined this one and when this
    # idea joined it (the reviewer chose the other to lead, J-REVIEW/M3); one merged into some third idea is not
    this_uuid, joined_to = str(idea["id"]), str(idea["merged_into"] or "")
    similar = [
        {"idea_id": s["idea_id"], "title": s["title"], "status": s["status"], "strength": s["strength"],
         "reason": s["reason"], "merged": str(s["merged_into"] or "") == this_uuid or str(s["uuid"]) == joined_to,
         # S-R2.similar (BLD-B264): "IDEA-…, Ravi Nair, Investor service, Hyderabad. 4 on its crew", from the bits
         # that exist, so a sharer with no city or no area leaves no empty comma
         "meta": f"{joined(s['idea_id'], person_by_code(conn, s['contributor_code']).name, s['area'], s['city'])}. "
                 f"{s['crew']} on its crew"}
        # A link counts both ways: an idea found similar to this one while its sharer wrote (and later merged into
        # it, J-SIMILAR/6a) is this idea's similar idea too (S-R2.left/5, J-SIMILAR/7). This idea's own link wins.
        for s in conn.execute(
            "SELECT * FROM (SELECT DISTINCT ON (o.id) o.id AS uuid, o.idea_id, o.title, o.status, o.area, o.city, "
            "o.contributor_code, o.merged_into, l.strength, l.reason, l.rank, l.idea_uuid = %(id)s AS own_link, "
            "(SELECT count(*) FROM crew_members c WHERE c.idea_uuid = o.id AND c.left_at IS NULL) AS crew "
            "FROM similar_links l JOIN ideas o "
            "ON o.id = CASE WHEN l.idea_uuid = %(id)s THEN l.other_idea_uuid ELSE l.idea_uuid END "
            "WHERE (l.idea_uuid = %(id)s OR l.other_idea_uuid = %(id)s) AND o.status NOT IN ('draft', 'withdrawn') "
            "ORDER BY o.id, own_link DESC) s ORDER BY s.own_link DESC, s.rank, s.idea_id",
            {"id": idea["id"]},
        )
    ]  # fmt: skip
    decide_by = idea["decide_by"]
    c = clock.countdown(decide_by, t) if decide_by else None
    # Decide, Ask, worth, Merge and the reminder are the review desk's: a committee member reads without them
    # (BLD-B270; the worker refuses their writes, `REVIEWERS`)
    can_act = not own and idea["status"] in ON_DESK_STATUSES and has_role(conn, user_id, REVIEWERS)
    return {
        "idea": {
            "id": idea["idea_id"],
            "title": idea["title"],
            "status": idea["status"],
            "status_label": STATUS_LABELS.get(str(idea["status"]), ""),
            "pill": PILLS.get(str(idea["status"]), "blue"),
            "heading": heading,
            "kind": idea["kind"],
            "area": idea["area"],
        },
        "sharer": sharer.as_json(),
        "own": own,
        "can_act": can_act,
        "decide_by": {
            "at": decide_by.isoformat() if decide_by else None,
            "label": when.day(decide_by, t) if decide_by else None,
            "left": c.label("to decide") if c else None,
        },
        "artefacts": artefacts,
        "own_words": messages,
        "parts": parts,
        "worth": {
            "tiles": [vars(x) for x in worth.tiles(sharer_worth, reviewer_worth)],
            "revised": reviewer_worth is not None,
            "revision": revision,
            # The board's lines tell the reviewer to decide or revise, so only the review desk acting on the idea reads
            # them; anyone who can't act (a committee member, BLD-B270) reads none (S-R2.panel; the BLD-B270 follow-up)
            "line": (
                None
                if not can_act
                else f"You’ve revised what it’s worth. {first} sees your figures next to theirs when you decide."
                if reviewer_worth is not None
                else f"Clear enough? Decide now. If it’s worth more than {first} could put into numbers, revise what it’s "
                f"worth first. {first} sees your figures next to theirs."
            ),
        },
        "similar": similar,
        # L-HIDE.rules/6: the review desk and the Ones Committee read why a detail was shown; no one else does
        "shown": _shown(conn, idea["id"]) if has_role(conn, user_id, READERS) else [],
        "contributions": _contributions(conn, idea, t, user_id),
        "panel": _panel(conn, idea, user_id, t),
    }


def script_for(conn: Conn, ref: str, at: dt.datetime | None = None) -> Any:
    """The masked listen script for an idea, the same for every viewer (L-LISTEN/2): what the browser voice reads
    (BLD-B230) and what lane C's hosted voice synthesises part by part (DEC-108), so the chapters, the estimate and the
    audio agree. Each part is spoken as `listen.spoken(title, text)`; `Script.version` changes with the content.
    Returns a `desk.listen.Script`."""
    from desk import listen, revise
    from desk.store import load_idea

    t = at or now()
    idea = load_idea(conn, ref)
    files = _checked_files(conn, idea["id"])  # viewer-independent: never a file holding a customer detail
    sharer_worth, reviewer_worth, _rev = revise.current(conn, str(idea["id"]))
    # the plain kind names ("Folio is hidden from everyone."): the masked hint ("Folio ••••89") is for the page only,
    # never spoken
    texts = _part_texts(conn, idea, files, [(kind, None) for kind, _hint in _hidden(conn, idea["id"])])
    answers = {
        part: [listen.Answer(q["answer"]["by"], q["answer"]["text"] or "") for q in qs if q["answer"]]
        for part, qs in _questions(conn, idea["id"], t).items()
    }
    return listen.build(texts, worth=reviewer_worth or sharer_worth, answers=answers)


def listen_script(conn: Conn, ref: str, user_id: str) -> dict[str, Any]:
    """`GET /desk/ideas/:id/listen`: the script as JSON, for the review desk and the Ones Committee only (the route
    checks too). `script_for` stays viewer-independent: lane C calls it behind its own gate."""
    from desk.store import READERS, require_role

    require_role(conn, user_id, READERS)
    return dict(script_for(conn, ref).as_json())


def load_uuid(conn: Conn, ref: str) -> Any:
    from desk.store import load_idea

    return load_idea(conn, ref)["id"]
