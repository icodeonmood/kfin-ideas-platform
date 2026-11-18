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


# Who may open the review desk: `view_review_queue` in policy/rbac.yaml, with its role aliases (a test keeps the
# two in step).
DESK_VIEWERS = frozenset({"reviewer", "core_committee", "core_chair", "admin"})
# Time limits the review desk works to; the rest are the committee's (rules/sla.md).
DESK_STAGES = ("review", "cluster_proposal", "qualify")
BREACH_WORDS = {
    "review": "The review of {idea}",
    "cluster_proposal": "A proposed group of similar ideas",
    "qualify": "The readiness check for {group}",
    "scoring_round": "Committee scoring for {group}",
    "individual_assessment": "Committee members' own assessments for {group}",
    "final_decision": "The committee's decision on {group}",
    "outcome_message": "The outcome message for {group}",
    "appeal_decision": "The appeal decision for {group}",
}
# Where each kind of timed item lives, to find the group it is about.
GROUP_OF = {
    "review_item": "SELECT ref_id AS cluster_id FROM review_items WHERE id::text = %s AND ref_id LIKE 'CL-%%'",
    "scoring_round": "SELECT cluster_id FROM scoring_rounds WHERE id::text = %s",
    "presentation": "SELECT cluster_id FROM presentations WHERE id::text = %s",
    "appeal": "SELECT cluster_id FROM appeals WHERE id::text = %s",
    "decision": "SELECT cluster_id FROM decisions WHERE id::text = %s",
}


def _group(conn: Conn, cluster_id: Any) -> dict[str, Any] | None:
    """A group's name and description as every contributor may read them: checked to hold no tags, names or
    identifiers when written (cluster-summary); any tag that slipped in reads as a neutral label."""
    if not cluster_id:
        return None
    row = conn.execute(
        "SELECT title, summary, member_count, tag_scope FROM clusters WHERE id = %s", (str(cluster_id),)
    ).fetchone()
    if row is None:
        return None
    mapping = vault.mapping(conn, row["tag_scope"]) if row["tag_scope"] else {}
    return {
        "name": restore(row["title"], mapping, "neutral") or "",
        "description": restore((row["summary"] or {}).get("description"), mapping, "neutral") or "",
        "members": int(row["member_count"] or 0),
    }


def _breach_label(conn: Conn, refs: dict[str, Any]) -> str:
    """What is late, in plain words: the idea's reference for the review desk, the group's name for committee
    steps, never a bare number (BLD-157). Older events without a stage keep the label they carried."""
    words = BREACH_WORDS.get(str(refs.get("stage") or ""))
    if words is None:
        return str(refs.get("item_label") or "An item")
    group_name = ""
    query = GROUP_OF.get(str(refs.get("entity_type") or ""))
    if query and refs.get("entity_id") is not None:
        row = conn.execute(query, (str(refs["entity_id"]),)).fetchone()
        group_name = ((_group(conn, row["cluster_id"]) if row else None) or {}).get("name") or ""
    return words.format(
        idea=refs.get("idea_id") or "an idea",
        group=f"the group “{group_name}”" if group_name else "a group",
    )


COMMITTEE_EVENTS = {"cluster.gate_outcome", "round.opened", "shortlist.invited", "round.not_shortlisted",
                    "presentation.confirmed", "decision.accepted", "decision.not_accepted",
                    "decision.not_presented", "appeal.filed", "appeal.decided"}  # fmt: skip
APPEAL_OUTCOME_TEXT = {
    "upheld": "The panel upheld the committee's decision.",
    "re_score": "The panel sent the group back to be scored again, with a direction for the committee.",
    "overturned": "The panel overturned the decision. The group goes back to the committee ahead of the others.",
}


def _appeal_text(dec: dict[str, Any] | None) -> str:
    """Whether a committee decision can be appealed, in plain words (§4.12: a decline, or a second park)."""
    if not dec or dec.get("outcome") not in ("parked", "declined"):
        return ""
    if dec.get("appeal_window_closes"):
        return (
            f"You can appeal this decision until {_date(dec['appeal_window_closes'])} from the Appeals page."
        )
    return "Parked groups come back for review in a later cycle; a second park can be appealed."


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
    if event == "idea.joined" and target_id:
        # The recipient's own idea on what was joined: the idea itself if it is theirs, their idea in the group, or
        # the idea they joined it with. Never the newcomer's idea, which `idea_id` points to, and never someone
        # else's idea called "your idea" (BLD-157). None found: the message leaves the line out.
        idea = conn.execute(
            "SELECT i.id, i.idea_id, i.contributor_code, i.canvas, i.strength FROM ideas i JOIN contributor_map m "
            "ON m.contributor_code = i.contributor_code WHERE m.user_id = %s AND (i.idea_id = %s "
            "OR i.cluster_id = %s OR i.idea_id IN (SELECT l.from_idea_id FROM idea_links l "
            "WHERE coalesce(l.idea_id, l.cluster_id) = %s AND l.contributor_code = i.contributor_code)) "
            "ORDER BY (i.idea_id = %s) DESC, i.idea_id LIMIT 1",
            (user_id, target_id, target_id, target_id, target_id),
        ).fetchone()
    if idea:
        card = idea["canvas"] or {}
        own = _owns(conn, user_id, idea)
        if own:
            one_line = _restore(conn, idea["idea_id"], card.get("one_line"), True)
        else:  # someone else's idea: only its checked short summary, never their words (non-negotiable 7)
            from views.common import checked_summary

            one_line = checked_summary(conn, card.get("neutral_summary"))
        data["idea"] = {
            "id": idea["idea_id"],
            "one_line": one_line or ("your idea" if own else "a colleague's idea"),
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
    # DEC-111 (BLD-A222): the review desk writes as a whole and signs as the desk, so the reviewer's name is never
    # read for a message, even when the event carries `reviewer_user_id`; no template can name them.

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
        # Put in a group: the group's name, never its reference number, and a sentence without a name while the
        # group has none (BLD-157). Attached to a single idea that is not in a group yet: "linked".
        grouped = refs.get("outcome") == "grouped"
        group = _group(conn, refs.get("cluster_id")) if grouped else None
        named = bool((group or {}).get("name"))
        data["outcome"] = {
            "grouped": group is not None and named,
            "grouped_unnamed": group is not None and not named,
            "linked": grouped and group is None,
            "standalone": not grouped,
        }
        data["cluster"] = {
            "name": (group or {}).get("name") or "",
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
        # Everyone else on it now: whoever first raised it and everyone who joined or added +1, not counting the
        # recipient. A running total, so the message says "now", never "more" (BLD-157).
        row = conn.execute(
            "SELECT count(DISTINCT m.user_id) AS n FROM idea_links l JOIN contributor_map m "
            "ON m.contributor_code = l.contributor_code WHERE coalesce(l.idea_id, l.cluster_id) = %s "
            "AND l.link_type IN ('originator', 'joiner', 'plus_one') AND m.user_id <> %s",
            (target_id, user_id),
        ).fetchone()
        n = max(int(row["n"]) if row else 1, 1)  # the colleague who has just joined is always one of them
        data["join"] = {
            "count": n,
            "one": n == 1,
            "many": n > 1,
            "count_word": "colleague" if n == 1 else "colleagues",
            "names_visible": False,  # names arrive with consent rules in a later block
        }
        if "idea" not in data:
            data["links"]["idea"] = f"{base}/my-ideas"
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
        # The request sits in the review desk's queue. Only people who may open the desk get a link to it. Who
        # asked is not in the message (revealing a name is for admins), so it says the 1% Club team can put them
        # in touch (BLD-157).
        from ones.service import roles

        if roles(conn, user_id) & DESK_VIEWERS:
            data["links"]["request"] = f"{base}/review"
    if event == "cluster.approved" and refs.get("cluster_id"):
        # The name and description are checked to hold no tags, names or identifiers (cluster-summary), so every
        # contributor may read them as written; the name stands in for the reference number (BLD-157).
        group = _group(conn, refs["cluster_id"]) or {}
        mine = conn.execute(
            "SELECT i.idea_id FROM ideas i JOIN contributor_map m ON m.contributor_code = i.contributor_code "
            "WHERE i.cluster_id = %s AND m.user_id = %s ORDER BY i.idea_id LIMIT 1",
            (refs["cluster_id"], user_id),
        ).fetchone()
        others = max(int(group.get("members") or 0) - 1, 0)
        data["cluster"] = {
            "id": refs["cluster_id"],
            "name": group.get("name") or "",
            "named": bool(group.get("name")),
            "unnamed": not group.get("name"),
            "description": group.get("description") or "",
            "other_count": others,
            "one_other": others == 1,
            "many_others": others > 1,
        }
        data["links"]["idea"] = f"{base}/ideas/{mine['idea_id']}" if mine else f"{base}/my-ideas"
    if event in COMMITTEE_EVENTS and refs.get("cluster_id"):
        # Committee messages (§3.7). The group's name and description hold no tags, names or IDs (cluster-summary,
        # BLD-213); any reason text the chair wrote is restored as neutral labels for everyone.
        cl = conn.execute(
            "SELECT id, title, summary, tag_scope FROM clusters WHERE id = %s", (refs["cluster_id"],)
        ).fetchone()
        mapping = vault.mapping(conn, cl["tag_scope"]) if cl and cl["tag_scope"] else {}
        data["cluster"] = {
            "id": refs["cluster_id"],
            "name": restore((cl or {}).get("title"), mapping, "neutral") or refs["cluster_id"],
            "description": restore(((cl or {}).get("summary") or {}).get("description"), mapping, "neutral")
            or "",
        }
        mine = conn.execute(
            "SELECT i.idea_id FROM ideas i JOIN contributor_map m ON m.contributor_code = i.contributor_code "
            "WHERE i.cluster_id = %s AND m.user_id = %s ORDER BY i.idea_id LIMIT 1",
            (refs["cluster_id"], user_id),
        ).fetchone()
        data["links"]["idea"] = f"{base}/ideas/{mine['idea_id']}" if mine else f"{base}/my-ideas"
        data["links"]["appeals"] = f"{base}/appeals"
        codes = {
            c["code"]: c["plain_words"]
            for c in load_rule(get_settings().company_repo_path, "reason-codes").data["codes"]
        }
        if refs.get("reason_code"):
            data["outcome"] = {"text": codes.get(str(refs["reason_code"]), "")}
        if refs.get("round_id"):
            rnd = conn.execute(
                "SELECT closes_at FROM scoring_rounds WHERE id = %s", (refs["round_id"],)
            ).fetchone()
            data["round"] = {"due_date": _date(rnd["closes_at"]) if rnd else ""}
            data["links"]["round"] = f"{base}/committee/rounds/{refs['round_id']}"
        pres = conn.execute(
            "SELECT id, reply_due, slot_at FROM presentations WHERE cluster_id = %s ORDER BY created_at DESC LIMIT 1",
            (refs["cluster_id"],),
        ).fetchone()
        if pres:
            data["presentation"] = {
                "reply_due": _date(pres["reply_due"]) if pres["reply_due"] else "",
                "slot": pres["slot_at"].astimezone(IST).strftime("%-d %B, %-I:%M %p")
                if pres["slot_at"]
                else "",
            }
            data["links"]["presentation"] = f"{base}/presentations/{pres['id']}"
        if refs.get("decision_id"):
            dec = conn.execute(
                "SELECT plain_reason, what_would_change, outcome, appeal_window_closes FROM decisions WHERE id = %s",
                (refs["decision_id"],),
            ).fetchone()
            data["decision"] = {
                "reason": restore((dec or {}).get("plain_reason"), mapping, "neutral") or "",
                "what_would_change": restore((dec or {}).get("what_would_change"), mapping, "neutral") or "",
                "appeal_text": _appeal_text(dec),
            }
        if refs.get("appeal_id"):
            apl = conn.execute(
                "SELECT due_at, hearing_requested, outcome, reasons FROM appeals WHERE id = %s",
                (refs["appeal_id"],),
            ).fetchone()
            reasons = restore((apl or {}).get("reasons"), mapping, "neutral") or ""
            data["appeal"] = {
                "due_date": _date(apl["due_at"]) if apl else "",
                "hearing_text": "The colleagues asked for a 10-minute hearing: please arrange it with them."
                if apl and apl["hearing_requested"]
                else "",
                "outcome_text": " ".join(
                    x for x in (APPEAL_OUTCOME_TEXT.get(str((apl or {}).get("outcome")), ""), reasons) if x
                ),
            }
            data["links"]["appeal"] = f"{base}/appeals/{refs['appeal_id']}"
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
        _ones_variables(conn, data, event, refs, base, user_id)
    if event.startswith("delivery."):
        _delivery_variables(conn, data, refs, base, user_id)
    if event == "ember.issue":  # the in-app note; the email carries the whole issue (BLD-128)
        row = conn.execute("SELECT month FROM ember_issues WHERE id = %s", (refs.get("issue_id"),)).fetchone()
        if row:
            from ember.service import month_label

            data["ember"] = {"month_label": month_label(row["month"])}
            data["links"]["ember"] = f"{base}/ember/{refs.get('issue_id')}"
    if event == "sla.breached":
        # Sent the moment the limit passes, so the message gives the limit, not a count of days late. It names a
        # person only when one is handling the item (BLD-157).
        stage = str(refs.get("stage") or "")
        # An event queued before BLD-157 has no stage, and its owner was the first reviewer on the desk, not
        # necessarily anyone handling it: no owner sentence for it.
        owner = refs.get("owner_user_id") if stage else None
        data["breach"] = {"days_late": refs.get("days_late", 0), "limit_wd": refs.get("limit_wd", 0)}
        data["item"] = {
            "label": _breach_label(conn, refs),
            "owner_name": _name(conn, owner) if owner else "",
            "unassigned": not owner and stage in DESK_STAGES,
        }
        committee = bool(stage) and stage not in DESK_STAGES
        data["links"]["item"] = f"{base}/committee" if committee else f"{base}/review"
    return data


def _one_display(number: Any, name: str | None, shown: bool) -> str:
    return f"No. {number}, {name}" if shown and name else f"One No. {number}"


# The "Your number" block shows only to the One it belongs to, and only when the number is the news (Ember review):
# never in a peer's invitation or in a removal.
YOUR_NUMBER_EVENTS = ("ones.inducted", "ones.tier_changed")


def _ones_variables(
    conn: Conn, data: dict[str, Any], event: str, refs: dict[str, Any], base: str, user_id: str
) -> None:
    """Variables for the Ones messages (DEC-034 to DEC-087). Reasons and messages are read back from their sealed
    rows only for the One they concern; the org-wide announcement names a One unless they hid their name
    (person_settings.show_name_on_wall, shown when there is no row: DEC-104, P-PRODUCT.privacy)."""
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
            "SELECT o.*, u.name, coalesce(s.show_name_on_wall, true) AS shown FROM ones o "  # DEC-104
            "JOIN users u ON u.id = o.user_id LEFT JOIN person_settings s ON s.user_id = o.user_id WHERE o.id = %s",
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
                "display": _one_display(number, one["name"], one["shown"]),
                "show_number": event in YOUR_NUMBER_EVENTS and str(one["user_id"]) == str(user_id),
            }
    if event == "ones.removed" and proposal:
        data["removal"] = {
            "reason": unseal(proposal["reason_encrypted"], f"one_proposal:{proposal['id']}:reason")
        }
    if event == "ones.tier_changed" and proposal:  # the colleague's invitation is retired (BLD-E049)
        # The direction comes from the decision itself; the old tier from the event (BLD-157), else the glow-up
        # row, which exists only for a step up. A step down must never read as a step up.
        to = int(proposal["tier_to"])
        frm: int | None = None
        if refs.get("tier_from") is not None:
            frm = int(refs["tier_from"])
        else:
            glow = conn.execute(
                "SELECT tier_from FROM one_glow_ups WHERE proposal_id = %s", (proposal["id"],)
            ).fetchone()
            frm = int(glow["tier_from"]) if glow else None
        kind = str(proposal.get("kind") or "")
        up = kind == "tier_up" if kind in ("tier_up", "tier_down") else (frm is None or to > frm)
        m = conn.execute(
            "SELECT id, text_encrypted FROM one_messages WHERE proposal_id = %s AND author_role = 'committee'",
            (proposal["id"],),
        ).fetchone()
        message = unseal(m["text_encrypted"], f"one_message:{m['id']}") if m else None
        data["tier"] = {
            "to": to,
            "to_name": tier_name(to),
            "from_name": tier_name(frm) if frm else "",
            "up": up,
            "down": not up,
            "committee_message": message,
        }
    if event == "ones.announced":
        from core import killswitch
        from views.common import checked_summary

        if not killswitch.is_on("ones.public", conn):
            # Checked again when it is read or sent: nothing about the Ones goes out while they are off the wall.
            raise RuntimeError("ones_paused")
        ids = [int(i) for i in refs.get("one_ids") or []]
        rows = conn.execute(
            "SELECT o.id, o.number, o.brief_encrypted, o.brief_approved_at, u.name, "
            "coalesce(s.show_name_on_wall, true) AS shown FROM ones o JOIN users u ON u.id = o.user_id "  # DEC-104
            "LEFT JOIN person_settings s ON s.user_id = o.user_id WHERE o.id = ANY(%s) AND o.status = 'active' "
            "ORDER BY o.number",
            (ids,),
        ).fetchall()
        lines = []
        for r in rows:
            brief = unseal(r["brief_encrypted"], f"one:{r['id']}:brief") if r["brief_approved_at"] else None
            brief = checked_summary(
                conn, brief
            )  # no colleague or client named in an org-wide email (BLD-111)
            who = _one_display(r["number"], r["name"], r["shown"])
            lines.append(f"{who}." + (f" {brief}" if brief else ""))
        data["ones"] = {
            "count": len(lines),
            "count_word": "colleague" if len(lines) == 1 else "colleagues",
            "list": "\n\n".join(lines),
        }


MARK_WORDS = {"day_30": "30 days after it went live", "day_90": "90 days after it went live"}
# Step words in messages: the start and the end of the work; the build steps in between are the plain words of
# §4.9 (`delivery.phases.plain_step`), never the build team's own steps such as "Building: QA" (BLD-157).
PHASE_MESSAGE_WORDS = {
    "started": "Started",
    "shipped": "Shipped",
    "resolved": "Fixed",
    "measured_30": "First results in",
    "closed": "Closed",
}
GROUP_LABEL_FALLBACK = "Group of similar ideas"


def _delivery_label(conn: Conn, subject: str) -> str:
    """How a delivery message names its work: the idea's checked neutral summary, else its reference number (the
    submitter already has it from "Your idea is in"); a group's name, else its first idea's checked summary. Never a
    group reference number (BLD-157). The label opens sentences and subjects, so it is never a lowercase phrase."""
    from views.common import checked_summary

    if subject.startswith("IDEA-"):
        row = conn.execute("SELECT canvas FROM ideas WHERE idea_id = %s", (subject,)).fetchone()
        summary = ((row["canvas"] if row else None) or {}).get("neutral_summary")
        return checked_summary(conn, summary) or subject
    if subject.startswith("CL-"):
        name = (_group(conn, subject) or {}).get("name")
        if name:
            return str(name)
        first = conn.execute(
            "SELECT canvas FROM ideas WHERE cluster_id = %s ORDER BY submitted_at NULLS LAST, idea_id LIMIT 1",
            (subject,),
        ).fetchone()
        summary = ((first["canvas"] if first else None) or {}).get("neutral_summary")
        return checked_summary(conn, summary) or GROUP_LABEL_FALLBACK
    return "This work"


def _delivery_variables(
    conn: Conn, data: dict[str, Any], refs: dict[str, Any], base: str, user_id: str
) -> None:
    """Variables for the delivery messages (§4.8 to §4.11): how the work is named (`_delivery_label`), the plain
    step words, and which sentence applies. IDs and codes in, never idea text beyond the summary."""
    from delivery.phases import plain_step

    subject = str(refs.get("subject_id") or "")
    label = _delivery_label(conn, subject)
    phase = str(refs.get("phase") or "")
    reason = str(refs.get("reason") or "")
    data["delivery"] = {
        "label": label,
        "phase_words": PHASE_MESSAGE_WORDS.get(phase) or plain_step(phase) or "",
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
    decision = str(refs.get("decision") or "")  # solution write-ups (BLD-133)
    data["writeup"] = {
        "approved": decision == "approved",
        "sent_back": decision == "sent_back",
        "solution_id": str(refs.get("solution_id") or ""),
    }
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
