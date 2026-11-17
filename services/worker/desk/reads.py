"""What the review desk reads (A-API.desk `GET /desk`; S-R1): the queue, its counts, the summary sentence and the
sidebar's "Waiting on sharers". Everything is worked out on read from stored facts (`desk.queue`).

Routing (L-SORT.rules/7) waits on the desk lead's area-to-reviewer map; until it arrives every reviewer sees
every idea on the desk except their own (SHIP_PLAN §8 fallback: any reviewer, never the sharer).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from core.db import Conn
from desk import clock, promises, queue, when
from desk.questions import SetFacts
from desk.store import (
    CUSTOMER_DETAIL,
    DESK_SEES,
    FILES_CHECKED,
    SHOWN_FILE,
    code_of,
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


def _hidden_line(kinds: list[str]) -> str:
    if not kinds:
        return ""
    names = [HIDDEN_KINDS.get(k, k) for k in dict.fromkeys(kinds)]
    first, *rest = names
    return _and([first, *[n.lower() if n not in ("PAN", "Aadhaar") else n for n in rest]]) + " hidden."


def _evidence_text(files: list[dict[str, Any]], hidden_kinds: list[str]) -> str:
    """The Attached part in words (board DeskIdea): "One file: branch-call-log-nov.pdf. Folio ••••89 is hidden from
    everyone." File names stand in for what each file is until the assistant describes them."""
    from desk.listen import _NUMBERS

    sent = [f for f in files if not f["answer_id"]]
    bits = []
    if sent:
        n = len(sent)
        names = "; ".join(str(f["name"]) for f in sent)
        bits.append(f"{_NUMBERS[n] if n < len(_NUMBERS) else n} file{'s' * (n != 1)}: {names}.")
    if hidden_kinds:
        bits.append(_hidden_line(hidden_kinds).replace(" hidden.", " hidden from everyone."))
    return " ".join(bits)


def _hidden_kinds(conn: Conn, idea_uuid: Any) -> list[str]:
    return [
        str(r["kind"])
        for r in conn.execute(
            "SELECT kind FROM hidden_details WHERE idea_uuid = %s AND state = 'hidden' ORDER BY created_at",
            (idea_uuid,),
        )
    ]


def _checked_files(
    conn: Conn, idea_uuid: Any, states: tuple[str, ...] = FILES_CHECKED
) -> list[dict[str, Any]]:
    """Files in `states` (the checked ones; the desk's view adds those holding a customer detail, DEC-107, each with
    its `customer_detail` marker). Never one still checking, infected or locked; a draft answer's files stay the
    sharer's until the answer is sent."""
    return [
        {**f, "customer_detail": f["file_state"] == CUSTOMER_DETAIL}
        for f in conn.execute(
            "SELECT id, name, bytes, pages, hidden_note, uploaded_by_code, answer_id, created_at, file_state "  # noqa: S608 (SHOWN_FILE is fixed text)
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
            "asked_line": f"{'You' if mine else asked_by.first_name} asked, {when.which_day(r['sent_at'], at)} "
                          f"{when.clock(r['sent_at'])}",
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
                "text": unseal(r["answer_encrypted"], "answers", "text_encrypted", str(r["answer_id"])),
                "at": r["answered_at"].isoformat(), "by": by.first_name,
                "line": f"{by.first_name} answered, {when.which_day(r['answered_at'], at)} {when.clock(r['answered_at'])}",
                "files": [{"id": f["id"], "name": f["name"], "hidden": f["hidden_note"],
                           "customer_detail": f["file_state"] == CUSTOMER_DETAIL} for f in files],
            }  # fmt: skip
        out.setdefault(str(r["part"]), []).append(item)
    return out


def _file_artefacts(conn: Conn, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The Attachments card's file rows (S-R2.left/2), each marked when it holds a customer detail (DEC-107)."""
    out: list[dict[str, Any]] = []
    for f in files:
        by = person_by_code(conn, f["uploaded_by_code"]).first_name
        size = _size(int(f["bytes"])) + (
            f", {f['pages']} page{'s' * (f['pages'] != 1)}" if f["pages"] else ""
        )
        when_line = "Added with the answers." if f["answer_id"] else f"Attached by {by}."
        out.append({"kind": "file", "id": f["id"], "title": f["name"],
                    "line": f"{when_line} {size}." + (f" {f['hidden_note']}" if f["hidden_note"] else ""),
                    "action": "Open", "customer_detail": f["customer_detail"]})  # fmt: skip
    return out


def _part_texts(
    conn: Conn, idea: dict[str, Any], files: list[dict[str, Any]], hidden_kinds: list[str]
) -> dict[str, str]:
    """Each part's words as the idea holds them (S-R2.left/3); the worth part is shown as tiles."""
    fix = conn.execute("SELECT how, included FROM idea_fix WHERE idea_uuid = %s", (idea["id"],)).fetchone()
    return {
        "summary": idea["summary"] or "", "often": idea["often"] or "", "who": ", ".join(idea["affects"] or []),
        "cost": "", "evidence": _evidence_text(files, hidden_kinds),
        "fix": (fix["how"] or "") if fix and fix["included"] else "",
    }  # fmt: skip


def _parts(texts: dict[str, str], asked: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    from desk.questions import PART_NAMES, PARTS

    return [
        {"part": p, "name": PART_NAMES[p], "text": texts[p], "questions": asked.get(p, [])} for p in PARTS
    ]


def _own_words(conn: Conn, idea_uuid: Any) -> list[dict[str, Any]]:
    """The sharer's own words, the masked copy (L-REVIEW.open/3)."""
    from desk.store import unseal

    return [
        {"seq": m["seq"], "via": m["via"], "at": m["created_at"].isoformat(),
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
        texts = _part_texts(conn, c, files, _hidden_kinds(conn, c["id"]))
        out.append({
            "idea_id": c["idea_id"], "title": c["title"] or "", "into": c["into_idea_id"],
            "merged_at": c["merged_at"].isoformat() if c["merged_at"] else None,
            "sharer": sharer.as_json(), "label": f"{sharer.first_name}’s idea, {c['idea_id']}",
            "parts": _parts(texts, _questions(conn, c["id"], at, viewer_id)),
            "files": _file_artefacts(conn, files), "own_words": _own_words(conn, c["id"]),
        })  # fmt: skip
    return out


def _panel(conn: Conn, idea: dict[str, Any], user_id: str, at: dt.datetime) -> dict[str, Any]:
    """Which working state the panel opens in (L-REVIEW.panel), with what it shows."""
    from desk import committee, questions

    if idea["status"] == "merged":  # first: a Not now that came back and was then merged shows the merge
        return {"state": "merged"}
    decision = committee.for_idea(conn, str(idea["id"]), user_id, at)
    if decision is not None and idea["status"] not in ON_DESK_STATUSES:
        return {"state": "decided", "decision": decision}
    s = conn.execute(
        "SELECT * FROM question_sets WHERE idea_uuid = %s AND state NOT IN ('queued', 'closed') "
        "ORDER BY created_at DESC LIMIT 1",
        (idea["id"],),
    ).fetchone()
    if s is None:
        return {"state": "reviewing", "decision": decision}
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
        return {"state": "answered", "title": title, "spare_line": spare, **common}
    sharer_first = person_by_code(conn, idea["contributor_code"]).first_name
    return {"state": "sent", "title": f"Waiting on {sharer_first}", **common}


ON_DESK_STATUSES = frozenset({"with_review_desk", "needs_you"})


def reviewer_idea(conn: Conn, ref: str, user_id: str, at: dt.datetime | None = None) -> dict[str, Any]:
    """Everything a reviewer needs to decide on one idea, on one page (S-R2.left, S-R2.panel). Raw words are the
    masked copy (L-REVIEW.open/3); unmasked hidden details never reach the desk."""
    from desk import revise, worth
    from desk.store import is_own, load_idea, person_by_code

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
    heading = f"Shared {when.day(shared_at, t)} by {sharer.name}, {sharer.area or idea['area'] or ''}, {idea['city'] or ''}."
    if idea["sorting_confirmed_at"] and sorting_line:
        heading += f" Sorting confirmed by {sharer.first_name}: {sorting_line[0].lower() + sorting_line[1:]}."
    messages = _own_words(conn, idea["id"])
    hidden_kinds = _hidden_kinds(conn, idea["id"])
    # the desk opens a file holding a customer detail, marked (DEC-107)
    files = _checked_files(conn, idea["id"], DESK_SEES)
    similar_n = conn.execute(
        "SELECT count(*) AS n FROM similar_links WHERE idea_uuid = %s AND found_while = 'drafting'",
        (idea["id"],),
    ).fetchone()
    versions = conn.execute(
        "SELECT count(*) AS n, count(*) FILTER (WHERE 'title' = ANY(changed_fields)) AS titles "
        "FROM idea_versions WHERE idea_uuid = %s",
        (idea["id"],),
    ).fetchone()
    first = sharer.first_name
    artefacts = _file_artefacts(conn, files)
    if messages:
        artefacts.append({"kind": "own_words", "title": f"{first}’s own words",
                          "line": " ".join(x for x in (f"As {first} wrote them on {when.DAYS[shared_at.astimezone(when.IST).weekday()]}, before the draft.",
                                                       _hidden_line(hidden_kinds)) if x),
                          "action": "Read"})  # fmt: skip
    if similar_n and similar_n["n"]:
        n = int(similar_n["n"])
        kept = f" {first} kept it separate." if idea["kept_separate"] else ""
        artefacts.append({"kind": "similar_found", "title": "Similar ideas",
                          "line": f"{n} found while {first} wrote.{kept}", "action": "Compare"})  # fmt: skip
    if versions and versions["n"]:
        n, titles = int(versions["n"]), int(versions["titles"])
        bits = [f"{n} version{'s' * (n != 1)}."]
        if titles:
            bits.append(
                f"Title changed {when.times(titles)}"
                + (", sorting confirmed." if idea["sorting_confirmed_at"] else ".")
            )
        artefacts.append({"kind": "versions", "title": "Draft history", "line": " ".join(bits), "action": "See changes"})  # fmt: skip
    sharer_worth, reviewer_worth, revision = revise.current(conn, str(idea["id"]))
    parts = _parts(_part_texts(conn, idea, files, hidden_kinds), _questions(conn, idea["id"], t, user_id))
    similar = [
        {"idea_id": s["idea_id"], "title": s["title"], "status": s["status"], "strength": s["strength"],
         "reason": s["reason"], "merged": s["merged_into"] == idea["id"],
         "meta": f"{s['idea_id']}, {person_by_code(conn, s['contributor_code']).name}, {s['area'] or ''}, "
                 f"{s['city'] or ''}. {s['crew']} on its crew"}
        for s in conn.execute(
            "SELECT o.idea_id, o.title, o.status, o.area, o.city, o.contributor_code, o.merged_into, l.strength, l.reason, "
            "(SELECT count(*) FROM crew_members c WHERE c.idea_uuid = o.id AND c.left_at IS NULL) AS crew "
            "FROM similar_links l JOIN ideas o ON o.id = l.other_idea_uuid "
            "WHERE l.idea_uuid = %s AND o.status NOT IN ('draft', 'withdrawn') ORDER BY l.rank",
            (idea["id"],),
        )
    ]  # fmt: skip
    decide_by = idea["decide_by"]
    c = clock.countdown(decide_by, t) if decide_by else None
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
        "can_act": not own and idea["status"] in ON_DESK_STATUSES,
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
            "line": (
                f"You’ve revised what it’s worth. {first} sees your figures next to theirs when you decide."
                if reviewer_worth is not None
                else f"Clear enough? Decide now. If it’s worth more than {first} could put into numbers, revise what it’s "
                f"worth first. {first} sees your figures next to theirs."
            ),
        },
        "similar": similar,
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
    texts = _part_texts(conn, idea, files, _hidden_kinds(conn, idea["id"]))
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
