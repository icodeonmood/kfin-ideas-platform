"""Build a message for one recipient (§3.7 step 4): the template's variables are read from the records the
notification points to, at the moment it is sent or viewed, and tagged text is restored only as far as that
recipient may see it. The submitter sees their own idea's real values; anyone else sees the neutral summary and
neutral labels (non-negotiable 7)."""

from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from core.config import get_settings
from core.crypto import CryptoError, decrypt_json
from core.db import Conn
from pii import vault
from pii.restore import restore
from rules import load_rule

IST = ZoneInfo("Asia/Kolkata")
NEXT_STEPS = {
    "review": "The review desk looks at it next.",
    "clustered": "It will be looked at together with the similar ideas.",
    "qualify": "The core committee looks at the most promising ideas each month.",
    "garage": "A team builds it next.",
    "fix_track": "It goes to the team that can fix it.",
    "closed": "No further steps are planned.",
}
OUTCOMES = {
    "kept": "The review desk's decision stands.",
    "changed": "The core committee changed the review desk's decision.",
}


def _date(ts: dt.datetime | None) -> str:
    return ts.astimezone(IST).strftime("%a %d %b") if ts else ""


def _first_name(conn: Conn, user_id: str) -> str:
    row = conn.execute("SELECT name FROM users WHERE id = %s", (user_id,)).fetchone()
    return str(row["name"]).split()[0] if row and row["name"] else "there"


def _name(conn: Conn, user_id: Any) -> str:
    if not user_id:
        return "The review desk"
    row = conn.execute("SELECT name FROM users WHERE id = %s", (str(user_id),)).fetchone()
    return str(row["name"]) if row and row["name"] else "The review desk"


def _owns(conn: Conn, user_id: str, idea: dict[str, Any]) -> bool:
    row = conn.execute(
        "SELECT 1 FROM contributor_map WHERE user_id = %s AND contributor_code = %s",
        (user_id, idea["contributor_code"]),
    ).fetchone()
    return row is not None


def _restore(conn: Conn, idea_id: str, value: Any, real: bool) -> Any:
    return restore(value, vault.mapping(conn, idea_id), "real" if real else "neutral")


def _decrypt_text(blob: Any, context: str) -> str | None:
    if blob is None:
        return None
    try:
        return str(decrypt_json(bytes(blob), context).get("text") or "")
    except CryptoError:
        return None


def variables(conn: Conn, user_id: str, event: str, refs: dict[str, Any]) -> dict[str, Any]:
    base = get_settings().app_base_url.rstrip("/")
    data: dict[str, Any] = {"recipient": {"first_name": _first_name(conn, user_id)}, "links": {}}
    idea = None
    if refs.get("idea_id"):
        idea = conn.execute(
            "SELECT id, idea_id, contributor_code, canvas, strength FROM ideas WHERE idea_id = %s",
            (refs["idea_id"],),
        ).fetchone()
    target_id = refs.get("target_id")
    if event == "idea.joined" and target_id and str(target_id).startswith("IDEA-"):
        idea = conn.execute(
            "SELECT id, idea_id, contributor_code, canvas, strength FROM ideas WHERE idea_id = %s",
            (target_id,),
        ).fetchone()
    if idea:
        card = idea["canvas"] or {}
        own = _owns(conn, user_id, idea)
        one_line = (
            _restore(conn, idea["idea_id"], card.get("one_line"), True)
            if own
            else card.get("neutral_summary")
        )
        data["idea"] = {
            "id": idea["idea_id"],
            "one_line": one_line or "your idea",
            "strength": idea["strength"] if idea["strength"] is not None else 0,
            "next_best": list(((card.get("strength") or {}).get("next_best") or [])[:2]),
        }
        data["links"]["idea"] = f"{base}/ideas/{idea['idea_id']}" if own else f"{base}/my-ideas"
        due = conn.execute(
            "SELECT t.due_at FROM sla_timers t JOIN review_items r ON t.entity_id = r.id::text "
            "WHERE r.ref_id = %s AND t.stage = 'review' ORDER BY t.id DESC LIMIT 1",
            (idea["idea_id"],),
        ).fetchone()
        data["review"] = {"due_date": _date(due["due_at"]) if due else ""}
    if refs.get("reviewer_user_id") or event in ("idea.question", "idea.reviewed", "idea.redirected"):
        data["reviewer"] = {"name": _name(conn, refs.get("reviewer_user_id"))}

    if event == "idea.question" and idea:
        q = conn.execute(
            "SELECT id, question_encrypted, due_at FROM idea_questions WHERE id = %s",
            (refs.get("question_id"),),
        ).fetchone()
        text = _decrypt_text(q["question_encrypted"], f"question:{q['id']}") if q else None
        data["question"] = {
            "text": _restore(conn, idea["idea_id"], text or "", _owns(conn, user_id, idea)),
            "due_date": _date(q["due_at"]) if q else "",
        }
    if event == "idea.reviewed":
        grouped = refs.get("outcome") == "grouped"
        data["outcome"] = {"grouped": grouped, "standalone": not grouped}
        data["cluster"] = {
            "name": refs.get("cluster_id") or "",
            "other_count": refs.get("cluster_other_count") or 0,
        }
        data["next_step"] = {"text": NEXT_STEPS.get(str(refs.get("next_step")), NEXT_STEPS["review"])}
        note = None
        if refs.get("note_correction_id") and idea:
            row = conn.execute(
                "SELECT note FROM corrections WHERE id = %s", (refs["note_correction_id"],)
            ).fetchone()
            note = _restore(conn, idea["idea_id"], row["note"], _owns(conn, user_id, idea)) if row else None
        data.setdefault("reviewer", {})["note"] = note
    if event == "idea.redirected":
        targets = load_rule(get_settings().company_repo_path, "redirects").data.get("targets") or {}
        t = targets.get(str(refs.get("redirect_kind"))) or {}
        data["redirect"] = {
            "team": t.get("team") or "",
            "message": t.get("message") or "",
            "url": t.get("url"),
        }
    if event == "idea.reconsidered" and idea:
        item = conn.execute(
            "SELECT veto_reason FROM review_items WHERE id = %s", (refs.get("review_item_id"),)
        ).fetchone()
        reason = (
            _restore(conn, idea["idea_id"], item["veto_reason"], _owns(conn, user_id, idea)) if item else ""
        )
        data["member"] = {"name": _name(conn, refs.get("member_user_id"))}
        data["outcome"] = {
            "text": OUTCOMES.get(str(refs.get("outcome")), OUTCOMES["changed"]),
            "reason": reason,
        }
        data["next_step"] = {"text": NEXT_STEPS.get(str(refs.get("next_step")), NEXT_STEPS["review"])}
    if event == "idea.joined":
        row = conn.execute(
            "SELECT count(DISTINCT contributor_code) AS n FROM idea_links WHERE coalesce(idea_id, cluster_id) = %s "
            "AND link_type IN ('joiner', 'plus_one')",
            (target_id,),
        ).fetchone()
        n = int(row["n"]) if row else 1
        data["join"] = {
            "count": n,
            "count_word": "colleague" if n == 1 else "colleagues",
            "names_visible": False,  # names arrive with consent rules in a later block
        }
    if event == "adoption.requested":
        sol = conn.execute(
            "SELECT summary FROM repo_files WHERE kfin_id = %s LIMIT 1", (refs.get("solution_id"),)
        ).fetchone()
        link = conn.execute(
            "SELECT l.context_text, u.hr_department FROM idea_links l JOIN contributor_map m ON m.contributor_code = "
            "l.contributor_code JOIN users u ON u.id = m.user_id WHERE l.id = %s",
            (refs.get("link_id"),),
        ).fetchone()
        context = (
            _restore(conn, refs["idea_id"], link["context_text"], False)
            if link and link["context_text"]
            else ""
        )
        data["solution"] = {
            "id": refs.get("solution_id"),
            "title": (sol["summary"] if sol else "") or "your solution",
        }
        data["requester"] = {"lob_name": (link["hr_department"] if link else None) or "another team"}
        data["request"] = {"context": context}
        data["links"]["request"] = f"{base}/review"
    if event == "cluster.approved" and refs.get("cluster_id"):
        # The name and description are checked to hold no tags, names or identifiers (cluster-summary), so every
        # contributor may read them as written.
        row = conn.execute(
            "SELECT id, title, summary, member_count, tag_scope FROM clusters WHERE id = %s",
            (refs["cluster_id"],),
        ).fetchone()
        if row and row["tag_scope"]:  # belt and braces: any tag that slipped in reads as a neutral label
            from pii import vault
            from pii.restore import restore

            mapping = vault.mapping(conn, row["tag_scope"])
            row = dict(row) | {
                "title": restore(row["title"], mapping, "neutral"),
                "summary": {
                    "description": restore((row["summary"] or {}).get("description"), mapping, "neutral")
                },
            }
        mine = conn.execute(
            "SELECT i.idea_id FROM ideas i JOIN contributor_map m ON m.contributor_code = i.contributor_code "
            "WHERE i.cluster_id = %s AND m.user_id = %s ORDER BY i.idea_id LIMIT 1",
            (refs["cluster_id"], user_id),
        ).fetchone()
        count = int(row["member_count"]) if row else 0
        data["cluster"] = {
            "id": refs["cluster_id"],
            "name": (row["title"] if row else None) or refs["cluster_id"],
            "description": ((row["summary"] or {}).get("description") if row else None) or "",
            "other_count": max(count - 1, 0),
        }
        data["links"]["idea"] = f"{base}/ideas/{mine['idea_id']}" if mine else f"{base}/my-ideas"
    if event == "sla.reminder":
        timer = conn.execute(
            "SELECT due_at FROM sla_timers WHERE id = %s", (refs.get("timer_id"),)
        ).fetchone()
        data["item"] = {
            "label": refs.get("idea_id") or "An item",
            "due_date": _date(timer["due_at"]) if timer else "",
        }
        data["reminder"] = {"share_percent": int(float(refs.get("share") or 0) * 100)}
        data["links"]["item"] = f"{base}/review"
    if event.startswith("ones."):
        _ones_variables(conn, data, event, refs, base)
    if event.startswith("delivery."):
        _delivery_variables(conn, data, refs, base, user_id)
    if event == "ember.issue":  # the in-app note; the email carries the whole issue (BLD-128)
        row = conn.execute("SELECT month FROM ember_issues WHERE id = %s", (refs.get("issue_id"),)).fetchone()
        if row:
            from ember.service import month_label

            data["ember"] = {"month_label": month_label(row["month"])}
            data["links"]["ember"] = f"{base}/ember/{refs.get('issue_id')}"
    if event == "sla.breached":
        data["breach"] = {"days_late": refs.get("days_late", 0), "limit_wd": refs.get("limit_wd", 0)}
        data["item"] = {
            "label": refs.get("item_label") or "",
            "owner_name": _name(conn, refs.get("owner_user_id")),
        }
        data["links"]["item"] = f"{base}/review"
    return data


def _one_display(number: Any, name: str | None, consent: bool) -> str:
    return f"No. {number}, {name}" if consent and name else f"One No. {number}"


def _ones_variables(conn: Conn, data: dict[str, Any], event: str, refs: dict[str, Any], base: str) -> None:
    """Variables for the Ones messages (DEC-034 to DEC-087). Reasons and messages are read back from their sealed
    rows only for the One they concern; the org-wide announcement names a One only with their consent."""
    from ones.text import unseal
    from ones.tiers import tier_name

    data["links"]["my_ideas"] = f"{base}/my-ideas"
    data["links"]["wall"] = f"{base}/wall"
    proposal = None
    if refs.get("proposal_id"):
        proposal = conn.execute(
            "SELECT * FROM one_proposals WHERE id = %s", (refs["proposal_id"],)
        ).fetchone()
    one_id = refs.get("one_id") or (proposal["one_id"] if proposal else None)
    if one_id:
        one = conn.execute(
            "SELECT o.*, u.name, coalesce(p.public_name_consent, false) AS consent FROM ones o "
            "JOIN users u ON u.id = o.user_id LEFT JOIN comms_prefs p ON p.user_id = o.user_id WHERE o.id = %s",
            (one_id,),
        ).fetchone()
        if one:
            number = one["number"]
            if number is None:  # retired: the number they wore last
                last = conn.execute(
                    "SELECT number FROM one_number_history WHERE one_id = %s ORDER BY from_at DESC LIMIT 1",
                    (one_id,),
                ).fetchone()
                number = last["number"] if last else ""
            data["one"] = {
                "number": number,
                "swap_until": _date(one["swap_until"]),
                "tier": int(one["tier"]),
                "tier_name": tier_name(one["tier"]),
                "display": _one_display(number, one["name"], one["consent"]),
            }
    if event == "ones.removed" and proposal:
        data["removal"] = {
            "reason": unseal(proposal["reason_encrypted"], f"one_proposal:{proposal['id']}:reason")
        }
    if event in ("ones.tier_changed", "ones.message_invited") and proposal:
        glow = conn.execute(
            "SELECT tier_from, tier_to FROM one_glow_ups WHERE proposal_id = %s", (proposal["id"],)
        ).fetchone()
        to = int(proposal["tier_to"])
        frm = int(glow["tier_from"]) if glow else None
        message = None
        if event == "ones.tier_changed":
            m = conn.execute(
                "SELECT id, text_encrypted FROM one_messages WHERE proposal_id = %s AND author_role = 'committee'",
                (proposal["id"],),
            ).fetchone()
            message = unseal(m["text_encrypted"], f"one_message:{m['id']}") if m else None
        data["tier"] = {
            "to": to,
            "to_name": tier_name(to),
            "from_name": tier_name(frm) if frm else "",
            "up": frm is None or to > frm,
            "down": frm is not None and to < frm,
            "committee_message": message,
        }
        data["links"]["write"] = f"{base}/ones/write/{proposal['id']}"
    if event == "ones.announced":
        from core import killswitch
        from views.common import checked_summary

        if not killswitch.is_on("ones.public", conn):
            # Checked again when it is read or sent: nothing about the Ones goes out while they are off the wall.
            raise RuntimeError("ones_paused")
        ids = [int(i) for i in refs.get("one_ids") or []]
        rows = conn.execute(
            "SELECT o.id, o.number, o.brief_encrypted, o.brief_approved_at, u.name, "
            "coalesce(p.public_name_consent, false) AS consent FROM ones o JOIN users u ON u.id = o.user_id "
            "LEFT JOIN comms_prefs p ON p.user_id = o.user_id WHERE o.id = ANY(%s) AND o.status = 'active' "
            "ORDER BY o.number",
            (ids,),
        ).fetchall()
        lines = []
        for r in rows:
            brief = unseal(r["brief_encrypted"], f"one:{r['id']}:brief") if r["brief_approved_at"] else None
            brief = checked_summary(
                conn, brief
            )  # no colleague or client named in an org-wide email (BLD-111)
            who = _one_display(r["number"], r["name"], r["consent"])
            lines.append(f"{who}." + (f" {brief}" if brief else ""))
        data["ones"] = {
            "count": len(lines),
            "count_word": "colleague" if len(lines) == 1 else "colleagues",
            "list": "\n\n".join(lines),
        }


MARK_WORDS = {"day_30": "30 days after it went live", "day_90": "90 days after it went live"}


def _delivery_variables(
    conn: Conn, data: dict[str, Any], refs: dict[str, Any], base: str, user_id: str
) -> None:
    """Variables for the delivery messages (§4.8 to §4.11): the idea's checked neutral summary (or a group's ID),
    the plain phase words, and which sentence applies. IDs and codes in, never idea text beyond the summary."""
    from delivery.phases import shown_as
    from views.common import checked_summary

    subject = str(refs.get("subject_id") or "")
    label = subject
    if subject.startswith("IDEA-"):
        row = conn.execute("SELECT canvas FROM ideas WHERE idea_id = %s", (subject,)).fetchone()
        label = (
            checked_summary(conn, ((row["canvas"] if row else None) or {}).get("neutral_summary")) or subject
        )
    elif subject.startswith("CL-"):
        label = f"the group {subject}"
    phase = str(refs.get("phase") or "")
    reason = str(refs.get("reason") or "")
    data["delivery"] = {
        "label": label,
        "phase_words": shown_as(phase) or {"started": "Started", "measured_30": "First results in",
                                           "closed": "Closed", "resolved": "Fixed"}.get(phase, ""),
        "started": phase == "started",
        "building": phase not in ("", "started", "shipped", "resolved", "measured_30", "closed"),
        "shipped": phase == "shipped",
        "resolved": phase == "resolved",
        "measured": phase == "measured_30",
        "closed": phase == "closed",
        "outcome_words": "it met its target" if refs.get("outcome") == "target_met"
        else "it closed short of its target, with the lessons written down",
        "mark_words": MARK_WORDS.get(str(refs.get("mark") or ""), ""),
        "milestone": reason == "milestone",
        "plan_late": reason == "plan_late",
        "blocked": reason == "blocked",
    }  # fmt: skip
    # Contributors are told about their idea, not given the delivery page (it is for the people doing the work):
    # anyone who cannot see the delivery gets My ideas instead.
    link = f"{base}/my-ideas"
    if refs.get("delivery_id"):
        from delivery.service import Refused, _delivery, can_see

        try:
            if can_see(conn, _delivery(conn, refs["delivery_id"]), user_id):
                link = f"{base}/delivery/{int(refs['delivery_id'])}"
        except Refused:
            pass
    data["links"]["delivery"] = link
