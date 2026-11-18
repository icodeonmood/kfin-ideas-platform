"""S-07, My ideas: everything the person has shared or teamed up on, where each is, and the one next step for each.

All list state lives in the URL (P-ROUTES.state, S-07.return/1): `list` (yours, teamed), `filter`, `sort`, `q` and
`row` (the row opened last, for "Back where you were"). The server normalises them and returns the canonical
query, so a link reproduces the view for whoever opens it, with only what that person may see (J-BROWSE/6).

Search here is a plain text match on the title, the short summary and the reference of the person's own list.
Asking in your own words (`C-SEARCH` ask, `L-SEARCH`) is lane F's and arrives on the same `q`.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any
from urllib.parse import urlencode

from core.db import Conn
from ideapage import adapters, read
from ideapage.shape import MY_IDEAS_FILTER_LABEL, display_status
from ideapage.track import Decided, decided
from ideapage.words import (
    DECISION_LABEL,
    count,
    day,
    mini_track,
    number_word,
    pill,
    saved_when,
    weekday_or_day,
)
from onepc import enums

LISTS = tuple(enums.values("my_ideas_list"))  # yours, teamed
SORTS = tuple(enums.values("my_ideas_sort"))  # latest, shared, stage
FILTERS = tuple(
    enums.values("my_ideas_filter")
)  # all, needs_you, drafts, with_review_desk, picked_and_building, …
LIST_LABEL = {"yours": "Yours", "teamed": "Teamed up"}
SORT_LABEL = {"latest": "Latest activity", "shared": "Date shared", "stage": "Stage"}
# The phone's sort cycler names the sort in a sentence ("Sorted by latest activity", PhoneMyIdeas) and its chip row
# shortens one filter ("With the desk").
SORTED_BY = {
    "latest": "Sorted by latest activity",
    "shared": "Sorted by date shared",
    "stage": "Sorted by stage",
}
SHORT_FILTER_LABEL = {"with_review_desk": "With the desk"}
SNIPPET_MAX = 96
STAGE_RANK = {
    "shipped": 9,
    "being_built": 8,
    "picked": 7,
    "needs_you": 6,
    "with_review_desk": 5,
    "checking": 4,
    "not_now": 3,
    "not_picked": 2,
    "withdrawn": 1,
    "merged": 1,
    "draft": 0,
}
Q_MAX = 200
# The statuses whose own row reads the decision (its date counts as activity, S-07's "Latest activity").
DECIDED_STATUSES = ("picked", "not_now", "not_picked", "being_built", "shipped")


def group_of(status: str) -> str:
    """The filter a row belongs to (S-07.filters, E-ENUMS.idea-status groups)."""
    if status == "needs_you":
        return "needs_you"
    if status == "draft":
        return "drafts"
    if status in ("checking", "with_review_desk"):
        return "with_review_desk"
    if status in enums.PICKED_AND_BUILDING:
        return "picked_and_building"
    if status == "shipped":
        return "shipped"
    return "closed"


def normalise(params: dict[str, Any]) -> dict[str, Any]:
    """Unknown values fall back to the defaults, so a hand-edited link still opens a sensible view."""
    list_ = params.get("list") if params.get("list") in LISTS else "yours"
    filter_ = params.get("filter") if params.get("filter") in FILTERS else "all"
    sort = params.get("sort") if params.get("sort") in SORTS else "latest"
    q = " ".join(str(params.get("q") or "").split())[:Q_MAX]
    row = str(params.get("row") or "")[:64] or None
    return {"list": list_, "filter": filter_, "sort": sort, "q": q, "row": row}


def query_of(state: dict[str, Any], **override: Any) -> str:
    """The canonical query string for a list state, defaults left out ('' for the plain list)."""
    s = {**state, **override}
    pairs = [
        (k, s[k])
        for k, default in (("list", "yours"), ("filter", "all"), ("sort", "latest"), ("q", ""), ("row", None))
        if s.get(k) and s[k] != default
    ]
    return urlencode(pairs)


def url_of(state: dict[str, Any], **override: Any) -> str:
    q = query_of(state, **override)
    return "/my-ideas" + (f"?{q}" if q else "")


def _matches(row: dict[str, Any], q: str) -> int:
    """0 for no match; higher is closer (title before summary before reference)."""
    if not q:
        return 1
    needle = q.lower()
    if needle in (row["title"] or "").lower():
        return 3
    if needle in (row["_summary"] or "").lower():
        return 2
    if needle in (row["ref"] or "").lower():
        return 1
    return 0


def snippet(text: str, limit: int = SNIPPET_MAX) -> str:
    """The short summary cut at a word for a search result's second line ('… so they…', MyIdeas search)."""
    t = " ".join(text.split())
    if len(t) <= limit:
        return t
    cut = t[:limit].rsplit(" ", 1)[0].rstrip(",;:.")
    return f"{cut}…"


def _activity(*times: dt.datetime | None) -> dt.datetime:
    return max(t for t in (*times, dt.datetime.min.replace(tzinfo=dt.UTC)) if t is not None)


def _saved_on(idea: dict[str, Any], device: str | None) -> dict[str, Any]:
    """Where a draft was last saved (L-DRAFT.autosave/4): the device class, and whether it is the device asking. A
    draft that arrived by email or Teams has no device and reads as the laptop."""
    return {
        "device": idea["saved_device"] or "laptop",
        "this_device": bool(device and device == idea.get("saved_device_id")),
    }


def _where(saved_on: dict[str, Any]) -> str:
    """'on this laptop', 'on your phone' (S-07.rows, C-SIDEBAR.anatomy/4)."""
    return f"on {'this' if saved_on['this_device'] else 'your'} {saved_on['device']}"


def _draft_row(conn: Conn, idea: dict[str, Any], now: dt.datetime, device: str | None) -> dict[str, Any]:
    uid = str(idea["id"])
    title = idea["title"] or "Your draft"
    saved = idea["saved_at"] or idea["created_at"]
    saved_on = _saved_on(idea, device)
    where = _where(saved_on)
    archived = idea.get("archived_at") is not None
    waiting = conn.execute(
        "SELECT i.id, i.idea_id, i.contributor_code FROM merge_requests r "
        "JOIN ideas i ON i.id = r.other_idea_uuid WHERE r.draft_uuid = %s AND r.state = 'waiting' LIMIT 1",
        (uid,),
    ).fetchone()
    if archived:
        # L-DRAFT.autosave/8: kept, not deleted; restored from My ideas → Drafts. Restoring a draft is lane C's
        # write (L-DRAFT); the action names it (`draft.restore`) and opens the draft.
        meta = f"Archived {day(idea['archived_at'], now)}, {where}"
        sentence = "Untouched for 30 days, so it was archived. Your words are kept."
        action = {"label": "Restore it", "op": "draft.restore", "to": f"/share/{uid}", "style": "line"}
    else:
        meta = f"Saved {saved_when(saved, now)}, {where}"
        if waiting:
            # The draft's owner is not on that idea's crew yet, so its lead is named only when they show their
            # name on the Wall and are still here; otherwise "the lead" (DEC-104, BLD-F029, BLD-E048). The lead is
            # the live crew lead, who answers the request, not always the person who shared it (L-TEAMUP.rules/10).
            lead = read.person_by_code(conn, adapters.lead_code(conn, dict(waiting)))
            who = lead["first_name"] if lead and read.shows_name(lead) else "the lead"
            sentence = f"Waiting for {who} to answer about joining {waiting['idea_id']}. Your words are kept."
        elif str(idea.get("step") or "").startswith("check") or idea.get("step") == "send":
            kept = (
                "Your words and sorting are kept."
                if idea.get("sorting_confirmed_at") or idea.get("sorting_sources")
                else "Your words are kept."
            )
            sentence = f"About a minute left. {kept}"
        else:
            n = conn.execute(
                "SELECT count(*) AS n FROM idea_messages WHERE idea_uuid = %s", (uid,)
            ).fetchone()
            lines = int(n["n"]) if n else 0
            sentence = (
                f"{number_word(lines).capitalize()} line{'s' * (lines != 1)} so far. Your words are kept."
                if lines
                else "Nothing written yet. Start when you’re ready."
            )
        action = {"label": "Carry on", "to": f"/share/{uid}", "style": "line"}
    return {
        "id": uid,
        "ref": None,
        "list": "yours",
        "title": title,
        "_summary": idea["summary"] or "",
        "href": f"/share/{uid}",
        "meta": meta,
        "pill": pill("draft"),
        "track": None,
        "next_step": {
            "sentence": sentence,
            "action": {**action, "accessible_name": f"{action['label']}: {title}"},
        },
        "archived": archived,
        "saved_on": saved_on,
        "group": "drafts",
        "_activity": saved,
        "_shared": saved,
        "_rank": STAGE_RANK["draft"],
    }


def _own_row(conn: Conn, idea: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    uid = str(idea["id"])
    key = read.key_of(idea)
    title = idea["title"] or key
    qset = read.question_set(conn, uid)
    status = display_status(idea, qset, for_sharer=True)
    dec: Decided | None = (
        decided(read.decision(conn, uid, with_text=True)) if idea["status"] in DECIDED_STATUSES else None
    )
    phone_sentence: str | None = None
    see = {"label": "See where it is", "to": f"/ideas/{key}", "style": "line"}
    read_it = {"label": "Read the decision", "to": f"/ideas/{key}", "style": "line"}
    meta_when = f"Shared {day(idea['shared_at'], now)}" if idea["shared_at"] else ""
    if status == "needs_you" and qset:
        n = len(qset["questions"])
        when = weekday_or_day(qset["sent_at"], now) if qset.get("sent_at") else None
        on = f" {when}" if when in ("today", "yesterday") else f" on {when}" if when else ""
        sentence = f"The review desk asked you {count(n, 'question')}{on}."
        # The phone board names who asked: "Meera from the review desk asked you 3 questions on Monday."
        # (PhoneMyIdeas.md); the desktop board says "The review desk" (MyIdeas.md).
        asker = read.person_by_user(conn, qset.get("by_user_id"))
        if asker:
            phone_sentence = (
                f"{asker['first_name']} from the review desk asked you {count(n, 'question')}{on}."
            )
        action = {"label": "Answer the questions", "to": f"/ideas/{key}/answer", "style": "primary"}
    elif status == "needs_you":  # questions sent, the set not readable yet
        sentence = "The review desk asked you some questions."
        action = {"label": "Answer the questions", "to": f"/ideas/{key}/answer", "style": "primary"}
    elif status in ("checking", "with_review_desk"):
        if qset and qset["state"] in read.ANSWERED_SET_STATES:
            asker = read.person_by_user(conn, qset["by_user_id"])
            who = asker["first_name"] if asker else "The review desk"
            by = (
                f" The review desk decides by {day(idea['decide_by'], now)}." if idea.get("decide_by") else ""
            )
            sentence = f"{who} has your answers.{by}"
        elif idea.get("decide_by"):
            sentence = f"The review desk looks at it by {day(idea['decide_by'], now)}."
        else:
            sentence = "The review desk looks at it next."
        action = see
    elif status == "picked" and dec and dec.reversed:
        meta_when = f"{DECISION_LABEL[dec.choice]} by the Ones Committee, {day(dec.at, now)}"
        sentence = f"The committee reversed the review desk’s {DECISION_LABEL[dec.desk_choice].lower()}: {dec.note or ''}".rstrip(
            ": "
        )
        action = read_it
    elif status == "picked":
        if dec:
            meta_when = f"Picked {day(dec.at, now)}"
        team = f" You’ll hear who by {day(dec.team_by, now)}." if dec and dec.team_by else ""
        sentence = f"A team is being chosen to build it.{team}"
        action = see
    elif status == "being_built":
        team_row = read.build_team(conn, uid)
        sentence = f"{team_row['name']} is building it." if team_row else "A team is building it."
        action = see
    elif status == "shipped":
        at = read.status_at(conn, uid, "shipped")
        sentence = (
            f"Live since {day(at, now)}. The team is measuring what changed."
            if at
            else "Live. The team is measuring what changed."
        )
        action = {"label": "See what it changed", "to": f"/ideas/{key}", "style": "line"}
    elif status in ("not_now", "not_picked") and dec and dec.reversed:
        meta_when = f"{DECISION_LABEL[dec.choice]} by the Ones Committee, {day(dec.at, now)}"
        sentence = f"The committee reversed the review desk’s {DECISION_LABEL[dec.desk_choice].lower()}: {dec.note or ''}".rstrip(
            ": "
        )
        action = read_it
    elif status == "not_now":
        back = (
            f" The review desk looks at it again on {day(dec.return_at, now)}."
            if dec and dec.return_at
            else ""
        )
        sentence = f"Not now.{back}"
        action = read_it
    elif status == "not_picked":
        sentence = dec.reason if dec and dec.reason else "Not picked."
        action = read_it
    elif status == "withdrawn":
        on = f" on {day(idea['withdrawn_at'], now)}" if idea.get("withdrawn_at") else ""
        sentence = f"Withdrawn{on}. It’s back in your drafts."
        action = {
            "label": "Restore it",
            "op": "restore",
            "method": "POST",
            "path": f"/api/ideas/{key}/restore",
            "style": "line",
        }
    elif status == "merged":
        m = read.live_merge_into(conn, uid)
        by = " by the review desk" if m and m["via"] == "review_desk" else ""
        sentence = (
            f"Merged into {m['lead_ref']}{by}. Your words carry on there."
            if m and m.get("lead_ref")
            else "Merged into another idea."
        )
        action = see
    else:
        sentence, action = "", see
    meta = ", ".join(x for x in (idea["idea_id"], meta_when) if x)
    times = [idea.get("status_changed_at"), idea.get("saved_at"), idea.get("shared_at")]
    if qset:
        times += [qset.get("sent_at"), qset.get("answered_at")]
    if dec:
        times += [dec.at]
    return {
        "id": key,
        "ref": idea["idea_id"],
        "list": "yours",
        "title": title,
        "_summary": idea["summary"] or "",
        "href": f"/ideas/{key}",
        "meta": meta,
        "pill": pill(status),
        "track": mini_track(status),
        "next_step": {
            "sentence": sentence,
            **({"phone_sentence": phone_sentence} if phone_sentence else {}),
            "action": {**action, "accessible_name": f"{action['label']}: {title}"},
        },
        "group": group_of(status),
        "_activity": _activity(*times),
        "_shared": idea["shared_at"] or idea["created_at"],
        "_rank": STAGE_RANK.get(status, 0),
    }


def _teamed_row(conn: Conn, idea: dict[str, Any], joined_at: dt.datetime, now: dt.datetime) -> dict[str, Any]:
    """A colleague's idea the person is on the crew of, as everyone sees it (summary only, S-09)."""
    uid = str(idea["id"])
    key = str(idea["idea_id"])
    title = idea["title"] or key
    status = display_status(idea, None, for_sharer=False)  # a crew member never sees "Needs you"
    sharer = read.person_by_code(conn, idea["contributor_code"])
    whose = f"{sharer['name']}’s idea" if sharer and read.shows_name(sharer) else "A colleague’s idea"
    dec = (
        decided(read.decision(conn, uid))
        if status in ("picked", "not_now", "not_picked", "being_built", "shipped")
        else None
    )
    if status in ("checking", "with_review_desk"):
        by = f" on {day(idea['decide_by'], now)}" if idea.get("decide_by") else " next"
        sentence = f"The review desk looks at it{by}. You’ll get a note either way."
    elif status == "picked":
        team = f" The build team is chosen by {day(dec.team_by, now)}." if dec and dec.team_by else ""
        sentence = f"Picked. A team is being chosen to build it.{team}"
    elif status == "being_built":
        team_row = read.build_team(conn, uid)
        sentence = f"{team_row['name']} is building it." if team_row else "A team is building it."
    elif status == "shipped":
        at = read.status_at(conn, uid, "shipped")
        sentence = (
            f"Live since {day(at, now)}. The team is measuring what changed."
            if at
            else "Live. The team is measuring what changed."
        )
    elif status == "not_now":
        sentence = (
            f"Not now. It comes back to the review desk on {day(dec.return_at, now)}."
            if dec and dec.return_at
            else "Not now."
        )
    elif status == "not_picked":
        sentence = "Not going ahead."
    elif status == "merged":
        m = read.live_merge_into(conn, uid)
        sentence = f"Now part of {m['lead_ref']}." if m and m.get("lead_ref") else "Now part of another idea."
    else:
        sentence = ""
    action = (
        {"label": "See the result", "to": f"/ideas/{key}", "style": "line"}
        if status == "shipped"
        else {"label": "Open the idea", "to": f"/ideas/{key}", "style": "line"}
    )
    return {
        "id": key,
        "ref": key,
        "list": "teamed",
        "title": title,
        "_summary": idea["summary"] or "",
        "href": f"/ideas/{key}",
        "meta": f"{whose}, you teamed up {day(joined_at, now)}, {key}",
        "pill": pill(status),
        "track": mini_track(status),
        "next_step": {
            "sentence": sentence,
            "action": {**action, "accessible_name": f"{action['label']}: {title}"},
        },
        "group": group_of(status),
        "_activity": _activity(idea.get("status_changed_at"), joined_at, dec.at if dec else None),
        "_shared": idea["shared_at"] or idea["created_at"],
        "_rank": STAGE_RANK.get(status, 0),
    }


EMPTY = {
    "needs_you": ("Nothing needs you right now.", "When the review desk asks you something, it shows here."),
    "drafts": ("No drafts.", "Drafts you start are kept here, saved as you type."),
    "with_review_desk": (
        "Nothing with the review desk right now.",
        "Ideas wait here for up to {days} working days before a decision.",
    ),
    "picked_and_building": (
        "Nothing picked yet.",
        "Ideas the review desk picks show here while a team builds them.",
    ),
    "shipped": ("Nothing shipped yet.", "Ideas land here once they ship and their effect is measured."),
    "closed": ("Nothing closed.", "Ideas that weren’t picked or were withdrawn show here, with the reason."),
}  # needs_you, drafts and picked_and_building: NOT DRAWN, written to the pattern of the drawn three
# Where the phone board words a line differently (PhoneMyIdeas.md); the desktop's is in EMPTY (MyIdeas.md).
PHONE_EMPTY_LINE = {"shipped": "Ideas land here once they ship and their impact is measured."}


def my_ideas(
    conn: Conn,
    user_id: str,
    params: dict[str, Any],
    *,
    device: str | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """A-API.my-ideas: rows with their next step, counts per filter (for the current list) and per list (for the
    current filter), the search sentence, the empty state and the canonical URL."""
    t = now or read.now()
    state = normalise(params)
    me = read.viewer(conn, user_id)
    rows: list[dict[str, Any]] = []
    if me.code:
        for r in conn.execute(
            "SELECT * FROM ideas WHERE contributor_code = %s ORDER BY coalesce(shared_at, saved_at, created_at) DESC",
            (me.code,),
        ).fetchall():
            idea = dict(r)
            if idea["status"] == "draft":
                rows.append(_draft_row(conn, idea, t, device))
            elif idea["idea_id"] is not None or idea["status"] == "merged":
                rows.append(_own_row(conn, idea, t))
        for r in conn.execute(
            "SELECT i.*, c.joined_at AS crew_joined_at FROM crew_members c JOIN ideas i ON i.id = c.idea_uuid "
            "WHERE c.contributor_code = %s AND c.left_at IS NULL AND c.role = 'crew' AND i.contributor_code <> %s "
            "AND i.idea_id IS NOT NULL AND i.status NOT IN ('draft', 'withdrawn')",
            (me.code, me.code),
        ).fetchall():
            idea = dict(r)
            rows.append(_teamed_row(conn, idea, idea["crew_joined_at"], t))

    def in_filter(row: dict[str, Any], f: str) -> bool:
        if f == "all":
            return not row.get("archived")
        return bool(row["group"] == f)

    scored = [(row, _matches(row, state["q"])) for row in rows]
    hits = [(row, s) for row, s in scored if s > 0]
    counts = {
        f: sum(1 for row, _ in hits if row["list"] == state["list"] and in_filter(row, f)) for f in FILTERS
    }
    lists = {
        lst: sum(1 for row, _ in hits if row["list"] == lst and in_filter(row, state["filter"]))
        for lst in LISTS
    }
    shown = [(row, s) for row, s in hits if row["list"] == state["list"] and in_filter(row, state["filter"])]
    key = {"latest": "_activity", "shared": "_shared", "stage": "_rank"}[state["sort"]]
    shown.sort(key=lambda rs: (rs[1] if state["q"] else 0, rs[0][key], rs[0]["_activity"]), reverse=True)

    out: dict[str, Any] = {
        "items": [_public_row(row, state) for row, _ in shown],
        "total": len(shown),
        "counts": counts,
        "lists": lists,
        "state": state,
        "query": query_of(state),
        "url": url_of(state),
        "tabs": [
            {
                "list": lst,
                "label": LIST_LABEL[lst],
                "count": lists[lst],
                "selected": lst == state["list"],
                "to": url_of(state, list=lst, row=None),
            }
            for lst in LISTS
        ],
        "filters": [
            {
                "filter": f,
                "label": "All" if f == "all" else MY_IDEAS_FILTER_LABEL[f],
                "short_label": SHORT_FILTER_LABEL.get(f, "All" if f == "all" else MY_IDEAS_FILTER_LABEL[f]),
                "count": counts[f],
                "selected": f == state["filter"],
                "to": url_of(state, filter=f, row=None),
            }
            for f in FILTERS
        ],
        "sorts": [
            {
                "sort": s,
                "label": SORT_LABEL[s],
                "selected": s == state["sort"],
                "to": url_of(state, sort=s, row=None),
            }
            for s in SORTS
        ],
        "sort_cycle": {
            "label": SORTED_BY[state["sort"]],
            "next": SORTS[(SORTS.index(state["sort"]) + 1) % len(SORTS)],
            "to": url_of(state, sort=SORTS[(SORTS.index(state["sort"]) + 1) % len(SORTS)], row=None),
        },
        "copy_link": {"label": "Copy link", "url": url_of(state, row=None), "done": "Link copied"},
    }
    if state["q"]:
        mine_n = sum(1 for row, _ in hits if row["list"] == "yours" and in_filter(row, state["filter"]))
        team_n = sum(1 for row, _ in hits if row["list"] == "teamed" and in_filter(row, state["filter"]))
        best = max(hits, key=lambda rs: (rs[1], rs[0]["_activity"]))[0] if hits else None
        if best is not None:
            sentence = (
                f"Found {count(mine_n + team_n, 'idea')} about “{state['q']}”: {mine_n} of yours and {team_n} you "
                f"teamed up on. Closest: “{best['title']}”."
            )
        else:
            sentence = f"Nothing found for “{state['q']}”."  # NOT DRAWN
        out["search"] = {
            "sentence": sentence,
            "matched_on": ["title", "summary", "reference"],
            "matched_line": "Matched on titles, short summaries and references.",  # NOT DRAWN: plain-text search
            "closest": {"id": best["id"], "title": best["title"], "href": best["href"]} if best else None,
            "clear": {"label": "Clear", "to": url_of(state, q="", row=None)},
        }
    if not rows:
        out["empty"] = {
            "kind": "first_time",
            "title": "Nothing shared yet",
            "line": (
                "Spot something that keeps going wrong? Say it in your own words. It takes about two minutes, and "
                "you’ll see it here with where it is and what happens next."
            ),
            "actions": [{"label": "Share your first problem", "to": "/share", "style": "primary"}],
            "hint": "or press P anywhere",
        }
    elif not shown:
        other = "teamed" if state["list"] == "yours" else "yours"
        actions = []
        if lists[other]:
            # The desktop board only: the phone's empty states offer "Show all ideas" alone (PhoneMyIdeas.md)
            actions.append(
                {
                    "label": f"See {lists[other]} in {LIST_LABEL[other]}",
                    "to": url_of(state, list=other, row=None),
                    "desk_only": True,
                }
            )
        if state["q"] and not hits:
            out["empty"] = {
                "kind": "no_results",
                "title": f"Nothing found for “{state['q']}”.",
                "line": "Try other words, or clear the search.",
                "actions": [{"label": "Clear", "to": url_of(state, q="", row=None)}],
            }
        elif state["filter"] != "all":
            title, line = EMPTY[state["filter"]]
            days = read.promises()["review"]["decide_by_working_days"]
            actions.append({"label": "Show all ideas", "to": url_of(state, filter="all", row=None)})
            phone_line = PHONE_EMPTY_LINE.get(state["filter"])
            out["empty"] = {
                "kind": "filtered",
                "title": title,
                "line": line.format(days=days),
                **({"phone_line": phone_line.format(days=days)} if phone_line else {}),
                "actions": actions,
            }
        else:  # NOT DRAWN: one list empty, the other not
            out["empty"] = {
                "kind": "list",
                "title": "You haven’t teamed up on an idea yet."
                if state["list"] == "teamed"
                else "Nothing shared yet",
                "line": "Find your crew to join colleagues on something similar."
                if state["list"] == "teamed"
                else "Spot something that keeps going wrong? Say it in your own words.",
                "actions": [
                    *actions,
                    {"label": "Find your crew", "to": "/crew"}
                    if state["list"] == "teamed"
                    else {"label": "Share a problem", "to": "/share"},
                ],
            }
    if state["row"] and any(row["id"] == state["row"] for row, _ in shown):
        out["arrival"] = {"line": f"Back where you were: {LIST_LABEL[state['list']]}.", "row": state["row"]}
    return out


def _public_row(row: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """The row as the API sends it, its link carrying the way back to this exact view (P-ROUTES.state)."""
    out = {k: v for k, v in row.items() if not k.startswith("_")}
    out["activity_at"] = row["_activity"].isoformat()
    if state["q"] and row["_summary"]:
        out["snippet"] = snippet(row["_summary"])
    if row["href"].startswith("/ideas/"):
        back = url_of(state, row=row["id"])
        linked = f"{row['href']}?{urlencode({'from': 'my-ideas', 'back': back})}"
        action = dict(out["next_step"]["action"])
        if action.get("to") == row["href"]:
            action["to"] = linked
        out["href"] = linked
        out["next_step"] = {**out["next_step"], "action": action}
    return out


# --- C-SIDEBAR's Your ideas (A-API.me `ideas`): read on every navigation, so one bounded query ----------------------
# The sidebar's drafts are lane C's L-DRAFT read (`saved_labels.sidebar`), so each list has one source.

SHELL_IDEAS = 3  # C-SIDEBAR.anatomy/4: "up to 3, with View all"
# C-SIDEBAR.anatomy/4: warn for needs you, blue for active, grey otherwise. The names are the status colours'
# (F-COLOR.status, C-PILL): the grey dot is `neutral` (`--faint`). Keyed by S-07's own filter groups.
SHELL_DOT = {"needs_you": "warn", "with_review_desk": "blue", "picked_and_building": "blue"}

# The person's own shared ideas (S-07's Yours list without its drafts), in S-07's "Latest activity" order: the latest
# of the status change, the save, the share, the question set's sent and answered times (`read.question_set`) and the
# decision's time, or the committee's when it reversed it (`read.decision`, `track.decided`). Ties keep S-07's
# reading order. The question set's state is all the status dot needs.
_SHELL_IDEAS_SQL = (
    "SELECT i.id, i.idea_id, i.title, i.status, q.state AS qset_state FROM ideas i "
    "LEFT JOIN LATERAL (SELECT s.state, s.sent_at, s.answered_at FROM question_sets s "
    "WHERE s.idea_uuid = i.id AND s.state <> 'queued' ORDER BY s.sent_at DESC NULLS LAST, s.created_at DESC "
    "LIMIT 1) q ON true "
    "LEFT JOIN LATERAL (SELECT CASE WHEN v.id IS NOT NULL AND v.to_choice IS NOT NULL THEN v.at ELSE d.at END "
    "AS at FROM idea_decisions d LEFT JOIN decision_windows w ON w.decision_id = d.id "
    "LEFT JOIN decision_reversals v ON v.window_id = w.id WHERE d.idea_uuid = i.id ORDER BY d.at DESC "
    "LIMIT 1) d ON i.status = ANY(%(decided)s) "
    "WHERE i.contributor_code = (SELECT m.contributor_code FROM contributor_map m JOIN users u ON u.id = m.user_id "
    "WHERE m.user_id = %(user)s AND u.active) "
    "AND i.status <> 'draft' AND (i.idea_id IS NOT NULL OR i.status = 'merged') "
    "ORDER BY greatest(i.status_changed_at, i.saved_at, i.shared_at, q.sent_at, q.answered_at, d.at) DESC NULLS LAST, "
    "coalesce(i.shared_at, i.saved_at, i.created_at) DESC, i.id LIMIT %(n)s"
)


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def shell_lists(conn: Conn, user_id: str) -> dict[str, list[dict[str, str]]]:
    """C-SIDEBAR.anatomy/4 (A-API.me `ideas`): up to three of the person's own shared ideas, each with a status dot
    and S-07's pill words for it (`status_label`, so the dot is never colour alone, F-A11Y.rules/4). The same rows,
    order, titles and links as S-07 lists first (`my_ideas`, list Yours, sort Latest activity); an idea's id is its
    reference (`/ideas/{ref}`). Teamed-up ideas are not the person's own and are not listed. Ideas only: the
    sidebar's drafts are lane C's L-DRAFT read. An unknown or inactive person gets an empty list. The person's own
    titles only; nothing here is logged (non-negotiable 3)."""
    out: dict[str, list[dict[str, str]]] = {"ideas": []}
    if not _is_uuid(user_id):
        return out
    params = {"user": user_id, "n": SHELL_IDEAS, "decided": list(DECIDED_STATUSES)}
    for r in conn.execute(_SHELL_IDEAS_SQL, params).fetchall():
        idea = dict(r)
        qset = {"state": idea["qset_state"]} if idea["qset_state"] else None
        status = display_status(idea, qset, for_sharer=True)  # S-07's needs-you reading
        key = read.key_of(idea)
        out["ideas"].append(
            {
                "id": key,
                "title": idea["title"] or key,
                "status_dot": SHELL_DOT.get(group_of(status), "neutral"),
                "status_label": pill(status)["label"],  # S-07's pill words (C-PILL, E-ENUMS.idea-status)
            }
        )
    return out
