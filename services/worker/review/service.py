"""Review desk actions (§4.3, AT-B6-03..05). Each action is one transaction:

- `decide`: accept or edit the system tags, change the person's category or play (only with a note that goes back
  to them), attach to a cluster or an idea or mark as new, confirm a strong canvas (strength 4+, earns points).
  Writes the idea, one `corrections` row per field that differs from the assistant's proposal, the item's final
  call, the veto-window timer, `idea.reviewed` in the outbox (the idea file gets `verified: human:REV-…`,
  `status: stable` and a history line) and the message to the submitter.
- `redirect` (to a channel, message from the template), `ask` (needs_info: pauses the review timer, starts a
  7-working-day timer), `visibility` (with a reason, audited), `hold` (spam or abuse: a second reviewer confirms).
Free text from reviewers (notes, questions, reasons) is tagged with the idea's scope before it is stored.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from psycopg.types.json import Jsonb

from comms.route import emit
from core.config import get_settings
from core.crypto import encrypt_json
from core.db import Conn
from core.logging import get_logger
from embeddings import embed
from pii.patterns import scan
from pii.tagger import tag_payload
from rules import load_rule
from sla import engine
from sla.calendar import add_working_days

log = get_logger("review")
SYSTEM_FIELDS = ("areas", "lobs", "systems", "roles_affected", "scope")
IDEA_COLUMNS = {
    "areas": "area_ids",
    "lobs": "lobs",
    "systems": "systems",
    "roles_affected": "roles_affected",
    "scope": "scope",
}
REDIRECT_KINDS = ("it_ticket", "hr_grievance", "complaint", "question")
CATEGORIES = ("cost_saving", "new_revenue", "both", "not_sure")
PLAYS = ("process_improvement", "upsell", "cross_sell", "new_product", "other", None)


def _known_ids() -> dict[str, set[str]]:
    from scan.inputs import _taxonomy

    t = _taxonomy(get_settings().company_repo_path)
    return {k: {str(x["id"]) for x in t[k]} for k in ("areas", "lobs", "roles", "glossary")}


class ActionRefused(Exception):
    def __init__(self, status: int, code: str, audit: tuple[str, str, str, dict[str, Any]] | None = None):
        super().__init__(code)
        self.status, self.code = status, code
        self.audit = audit  # (actor, action, entity, after): written after the rollback, so it survives


@contextmanager
def audited(conn: Conn) -> Iterator[None]:
    """Wrap outside `conn.transaction()`: a refusal that must leave a trace is audited once the work is undone."""
    try:
        yield
    except ActionRefused as exc:
        if exc.audit:
            actor, action, entity, after = exc.audit
            conn.execute(
                "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, %s, %s, %s)",
                (actor, action, entity, Jsonb(after)),
            )
        raise


def staff_code(conn: Conn, user_id: str) -> str:
    """The reviewer's REV-NNNN code, allocated on first use (it signs commits and `verified` entries)."""
    row = conn.execute("SELECT staff_code FROM users WHERE id = %s FOR UPDATE", (user_id,)).fetchone()
    if row is None:
        raise ActionRefused(403, "unknown_reviewer")
    if row["staff_code"]:
        return str(row["staff_code"])
    n = conn.execute("SELECT next_number('REV', '') AS n").fetchone()
    assert n is not None
    code = f"REV-{int(n['n']):04d}"
    conn.execute("UPDATE users SET staff_code = %s WHERE id = %s", (code, user_id))
    return code


def _tagged(conn: Conn, idea_id: str, text: str, min_chars: int = 0) -> str:
    text = text.strip()
    if len(text) < min_chars:
        raise ActionRefused(422, "text_too_short")
    if any(m.action == "block" for m in scan(text, kfin_domains=get_settings().kfin_domains)):
        raise ActionRefused(422, "personal_data")
    return str(tag_payload(conn, idea_id, {"t": text[:2000]}).payload["t"])


def refuse_own(conn: Conn, user_id: str, idea: dict[str, Any], action: str) -> None:
    """Nobody reviews, holds or vetoes their own idea (conflict of interest); the attempt is audited."""
    own = conn.execute(
        "SELECT 1 FROM contributor_map WHERE user_id = %s AND contributor_code = %s",
        (user_id, idea["contributor_code"]),
    ).fetchone()
    if own:
        raise ActionRefused(
            409,
            "own_idea",
            (f"user:{user_id}", "review.own_idea_refused", f"idea:{idea['idea_id']}", {"action": action}),
        )


def _load(conn: Conn, item_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
    item = conn.execute("SELECT * FROM review_items WHERE id = %s FOR UPDATE", (item_id,)).fetchone()
    if item is None or item["item_type"] != "idea":
        raise ActionRefused(404, "not_found")
    idea = conn.execute("SELECT * FROM ideas WHERE idea_id = %s FOR UPDATE", (item["ref_id"],)).fetchone()
    if idea is None:
        raise ActionRefused(404, "not_found")
    return dict(item), dict(idea)


def _card_text(idea: dict[str, Any]) -> str:
    c = idea.get("canvas") or {}
    return "\n".join(str(c.get(k) or "") for k in ("one_line", "details")).strip()


def _correction(
    conn: Conn,
    item_id: int,
    field: str,
    proposed: Any,
    final: Any,
    reviewer: str,
    note: str | None,
    vec: list[float],
) -> int:
    row = conn.execute(
        "INSERT INTO corrections (review_item_id, field, proposed, final, reviewer_id, note, card_embedding) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s::vector) RETURNING id",
        (item_id, field, Jsonb(proposed), Jsonb(final), reviewer, note, str(vec)),
    ).fetchone()
    assert row is not None
    return int(row["id"])


def _open_for_action(item: dict[str, Any], reviewer: str) -> None:
    if item["state"] in ("decided", "closed"):
        raise ActionRefused(409, "already_decided")
    if item["state"] == "awaiting_second_reviewer":
        raise ActionRefused(409, "awaiting_hold_confirmation")  # only a second reviewer's confirmation now
    if item["assigned_to"] and str(item["assigned_to"]) != reviewer:
        raise ActionRefused(409, "assigned_to_someone_else")  # e.g. a vetoing core committee member


def act(
    conn: Conn, item_id: int, reviewer: str, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.UTC)
    action = body.get("action")
    with audited(conn), conn.transaction():
        item, idea = _load(conn, item_id)
        refuse_own(conn, reviewer, idea, str(action))
        rev = staff_code(conn, reviewer)
        idea_id = idea["idea_id"]
        if action == "decide":
            return _decide(conn, item, idea, reviewer, rev, body, now)
        _open_for_action(item, reviewer)
        if action == "redirect":
            kind = body.get("kind")
            if kind not in REDIRECT_KINDS:
                raise ActionRefused(400, "redirect_kind_required")
            conn.execute("UPDATE ideas SET stage = 'redirected' WHERE id = %s", (idea["id"],))
            _close(conn, item, reviewer, {"action": "redirect", "kind": kind}, now)
            _reviewed_event(conn, idea_id, rev, "redirected")
            emit(
                conn,
                "idea.redirected",
                {"idea_id": idea_id, "redirect_kind": kind, "reviewer_user_id": reviewer},
            )
            return {"state": "decided", "stage": "redirected"}
        if action == "ask":
            question = _tagged(conn, idea_id, str(body.get("question") or ""), min_chars=10)
            due = add_working_days(
                now, int(load_rule(get_settings().company_repo_path, "sla").data["needs_info"]["limit_wd"])
            )
            q = conn.execute(
                "INSERT INTO idea_questions (idea_uuid, review_item_id, asked_by, question_encrypted, due_at) "
                "VALUES (%s, %s, %s, '\\x00', %s) RETURNING id",
                (idea["id"], item["id"], reviewer, due),
            ).fetchone()
            assert q is not None
            conn.execute(
                "UPDATE idea_questions SET question_encrypted = %s WHERE id = %s",
                (encrypt_json({"text": question}, f"question:{q['id']}"), q["id"]),
            )
            conn.execute("UPDATE ideas SET stage = 'needs_info' WHERE id = %s", (idea["id"],))
            conn.execute(
                "UPDATE review_items SET state = 'in_progress', assigned_to = %s WHERE id = %s",
                (reviewer, item["id"]),
            )
            engine.pause(conn, "review_item", str(item["id"]), "review", now=now)
            engine.start(conn, "idea", idea_id, "needs_info", now=now)
            emit(
                conn,
                "idea.question",
                {"idea_id": idea_id, "question_id": q["id"], "reviewer_user_id": reviewer},
            )
            return {"state": "in_progress", "stage": "needs_info"}
        if action == "visibility":
            vis = body.get("visibility")
            if vis not in ("org", "committee"):
                raise ActionRefused(400, "visibility_required")
            reason = _tagged(conn, idea_id, str(body.get("reason") or ""), min_chars=10)
            conn.execute(
                "UPDATE ideas SET visibility = %s, visibility_reason = %s WHERE id = %s",
                (vis, reason, idea["id"]),
            )
            vec = embed([_card_text(idea)])[0]
            _correction(conn, item["id"], "visibility", idea["visibility"], vis, reviewer, reason, vec)
            conn.execute(
                "INSERT INTO audit_log (actor, action, entity, before, after, reason) VALUES (%s, 'idea.visibility', %s, %s, %s, %s)",
                (
                    rev,
                    f"idea:{idea_id}",
                    Jsonb({"visibility": idea["visibility"]}),
                    Jsonb({"visibility": vis}),
                    reason,
                ),
            )
            _reviewed_event(conn, idea_id, rev, "visibility_changed", verify=False)
            return {"state": item["state"], "stage": idea["stage"]}
        if action == "hold":
            kind = body.get("kind")
            if kind not in ("spam", "abuse"):
                raise ActionRefused(400, "hold_kind_required")
            conn.execute(
                "UPDATE review_items SET state = 'awaiting_second_reviewer', final = %s WHERE id = %s",
                (Jsonb({"hold": kind, "requested_by": reviewer}), item["id"]),
            )
            conn.execute(
                "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'review.hold_requested', %s, %s)",
                (rev, f"idea:{idea_id}", Jsonb({"hold": kind})),
            )
            return {"state": "awaiting_second_reviewer", "stage": idea["stage"]}
        raise ActionRefused(400, "unknown_action")


def confirm_hold(conn: Conn, item_id: int, reviewer: str, now: dt.datetime | None = None) -> dict[str, Any]:
    """A second, different reviewer confirms a spam or abuse hold (AT-B6-05)."""
    now = now or dt.datetime.now(dt.UTC)
    with audited(conn), conn.transaction():
        item, idea = _load(conn, item_id)
        refuse_own(conn, reviewer, idea, "confirm_hold")
        rev = staff_code(conn, reviewer)
        final = item["final"] or {}
        if item["state"] != "awaiting_second_reviewer" or "hold" not in final:
            raise ActionRefused(409, "no_hold_to_confirm")
        if str(final.get("requested_by")) == reviewer:
            raise ActionRefused(409, "second_reviewer_needed")
        conn.execute("UPDATE ideas SET stage = 'declined' WHERE id = %s", (idea["id"],))
        _close(conn, item, reviewer, {"action": "hold", "hold": final["hold"], "confirmed_by": reviewer,
                                       "requested_by": final.get("requested_by")}, now)  # fmt: skip
        conn.execute(
            "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'review.hold_confirmed', %s, %s)",
            (rev, f"idea:{idea['idea_id']}", Jsonb({"hold": final["hold"]})),
        )
        return {"state": "decided", "stage": "declined"}


def _close(conn: Conn, item: dict[str, Any], reviewer: str, final: dict[str, Any], now: dt.datetime) -> None:
    conn.execute(
        "UPDATE review_items SET state = 'decided', decided_by = %s, decided_at = %s, final = %s WHERE id = %s",
        (reviewer, now, Jsonb(final), item["id"]),
    )
    engine.stop(conn, "review_item", str(item["id"]), "review")
    engine.stop(conn, "idea", str(item["ref_id"]), "needs_info")  # a decision ends any wait for an answer
    if item.get("vetoed_by") is None:  # a committee member's final call after a veto is not vetoed again
        engine.start(conn, "review_item", str(item["id"]), "veto_window", now=now)


def _same_outcome(before: dict[str, Any] | None, after: dict[str, Any]) -> bool:
    keys = ("stage", "attach", "system")
    return bool(before) and all((before or {}).get(k) == after.get(k) for k in keys)


def _reviewed_event(conn: Conn, idea_id: str, rev: str, word: str, verify: bool = True) -> None:
    payload: dict[str, Any] = {"history": [{"event": word, "by": rev}]}
    if verify:
        payload["verified_by"] = rev
    conn.execute(
        "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES ('idea.reviewed', %s, %s, %s)",
        (idea_id, rev, Jsonb(payload)),
    )


def _decide(
    conn: Conn,
    item: dict[str, Any],
    idea: dict[str, Any],
    reviewer: str,
    rev: str,
    body: dict[str, Any],
    now: dt.datetime,
) -> dict[str, Any]:
    _open_for_action(item, reviewer)
    allowed = ("scanned", "merged", "adoption_requested", "reviewed", "in_cluster")
    if idea["stage"] not in allowed + (("redirected", "declined") if item.get("vetoed_by") else ()):
        raise ActionRefused(409, "not_ready_for_review")
    idea_id = idea["idea_id"]
    proposal = (item["proposal"] or {}).get("system") or {}
    given = body.get("system") or {}
    if not isinstance(given, dict) or not isinstance(body.get("attach") or {}, dict):
        raise ActionRefused(400, "bad_request")
    final_system = {k: given.get(k, proposal.get(k)) for k in SYSTEM_FIELDS}
    known = _known_ids()
    for k, group in (
        ("areas", "areas"),
        ("lobs", "lobs"),
        ("roles_affected", "roles"),
        ("systems", "glossary"),
    ):
        values = final_system[k] or []
        if not isinstance(values, list) or any(
            str(v) not in known[group] and v not in (proposal.get(k) or []) for v in values
        ):
            raise ActionRefused(400, f"unknown_{k}")
    enums: dict[str, tuple[str | None, ...]] = {"category": CATEGORIES, "play": PLAYS}
    for f, choices in enums.items():
        if f in body and body[f] not in choices:
            raise ActionRefused(400, f"bad_{f}")
    for k in ("areas", "lobs", "systems", "roles_affected"):
        final_system[k] = [str(x) for x in (final_system[k] or [])]
    if final_system["scope"] not in (None, "lob", "cross-lob", "org-wide"):
        raise ActionRefused(400, "bad_scope")
    card = dict(idea["canvas"] or {})
    value = dict(card.get("value") or {})
    changes = {f: body[f] for f in ("category", "play") if f in body and body[f] != value.get(f)}
    note = None
    if changes:
        note = _tagged(
            conn, idea_id, str(body.get("note") or ""), min_chars=10
        )  # AT-B6-04: the note is required
    vec = embed([_card_text(idea)])[0]
    note_id = None
    for k in SYSTEM_FIELDS:
        if final_system[k] != (
            proposal.get(k) if k == "scope" else [str(x) for x in (proposal.get(k) or [])]
        ):
            _correction(
                conn, item["id"], f"system.{k}", proposal.get(k), final_system[k], reviewer, None, vec
            )
    for f, v in changes.items():
        note_id = _correction(conn, item["id"], f"value.{f}", value.get(f), v, reviewer, note, vec)
        value[f] = v
    card["value"] = value
    card.setdefault("provenance", {}).update({f"value.{f}": "reviewer" for f in changes})

    attach = body.get("attach") or {"type": "new"}
    stage, cluster_id, outcome = "reviewed", idea["cluster_id"], "standalone"
    if attach.get("type") == "cluster":
        cid = str(attach.get("id") or "")
        if not conn.execute("SELECT 1 FROM clusters WHERE id = %s", (cid,)).fetchone():
            raise ActionRefused(400, "cluster_not_found")
        stage, cluster_id, outcome = "in_cluster", cid, "grouped"
        conn.execute(
            "INSERT INTO idea_links (cluster_id, from_idea_id, contributor_code, link_type) VALUES (%s, %s, %s, 'joiner') "
            "ON CONFLICT DO NOTHING",
            (cid, idea_id, idea["contributor_code"]),
        )
    elif attach.get("type") == "idea":
        target = str(attach.get("id") or "")
        if (
            target == idea_id
            or not conn.execute("SELECT 1 FROM ideas WHERE idea_id = %s", (target,)).fetchone()
        ):
            raise ActionRefused(400, "idea_not_found")
        outcome = "grouped"
        conn.execute(
            "INSERT INTO idea_links (idea_id, from_idea_id, contributor_code, link_type) VALUES (%s, %s, %s, 'joiner') "
            "ON CONFLICT DO NOTHING",
            (target, idea_id, idea["contributor_code"]),
        )  # a must-link pair for the weekly batch (§4.4 A)
    if attach.get("type") in ("cluster", "idea") and attach.get("id") != (item["proposal"] or {}).get(
        "best_same"
    ):
        _correction(
            conn, item["id"], "match", (item["proposal"] or {}).get("best_same"), attach, reviewer, None, vec
        )

    conn.execute(
        "UPDATE ideas SET stage = %s, canvas = %s, category = %s, play = %s, area_ids = %s, lobs = %s, systems = %s, "
        "roles_affected = %s, scope = %s, cluster_id = %s WHERE id = %s",
        (
            stage, Jsonb(card), value.get("category"), value.get("play"), final_system["areas"], final_system["lobs"],
            final_system["systems"], final_system["roles_affected"], final_system["scope"], cluster_id, idea["id"],
        ),
    )  # fmt: skip
    if body.get("strong_canvas"):
        if (idea["strength"] or 0) < 4:
            raise ActionRefused(409, "canvas_not_strong")
        _award(conn, idea["contributor_code"], "strong_canvas", idea_id)
    _close(
        conn, item, reviewer,
        {"action": "decide", "system": final_system, "attach": attach, "stage": stage, "previous_stage": idea["stage"],
         "changed": sorted(changes), "strong_canvas": bool(body.get("strong_canvas"))},
        now,
    )  # fmt: skip
    _reviewed_event(conn, idea_id, rev, "reviewed")
    if item.get("vetoed_by") is not None:
        # After a veto the person hears only the final outcome, and only if it changed (§4.3).
        decided = {"stage": stage, "attach": attach, "system": final_system}
        if not _same_outcome((item.get("reasons") or {}).get("vetoed_decision"), decided):
            emit(
                conn,
                "idea.reconsidered",
                {"idea_id": idea_id, "review_item_id": item["id"], "outcome": "changed", "member_user_id": reviewer,
                 "next_step": "clustered" if outcome == "grouped" else "qualify"},
            )  # fmt: skip
        log.info("review.final_after_veto", review_item_id=item["id"], stage_name=stage)
        return {"state": "decided", "stage": stage}
    emit(
        conn,
        "idea.reviewed",
        {"idea_id": idea_id, "outcome": outcome, "cluster_id": cluster_id, "reviewer_user_id": reviewer,
         "cluster_other_count": _others_in(conn, cluster_id, idea_id) if cluster_id else 0,
         "next_step": "clustered" if outcome == "grouped" else "qualify", "note_correction_id": note_id},
    )  # fmt: skip
    log.info("review.decided", review_item_id=item["id"], stage_name=stage, correction_count=len(changes))
    return {"state": "decided", "stage": stage}


def _others_in(conn: Conn, cluster_id: str, idea_id: str) -> int:
    row = conn.execute(
        "SELECT count(*) AS n FROM ideas WHERE cluster_id = %s AND idea_id <> %s", (cluster_id, idea_id)
    ).fetchone()
    return int(row["n"]) if row else 0


def _award(conn: Conn, contributor_code: str, event: str, ref_id: str) -> None:
    """Through the points ledger: the sync's lock, caps in points per month, recorded once (Ember review)."""
    from points.ledger import award

    award(conn, contributor_code, event, ref_id)


def answer(
    conn: Conn, idea_uuid: str, contributor_code: str, text: str, now: dt.datetime | None = None
) -> dict[str, Any]:
    """The submitter answers a reviewer's question. Also reopens an idea withdrawn for want of an answer."""
    now = now or dt.datetime.now(dt.UTC)
    with conn.transaction():
        idea = conn.execute("SELECT * FROM ideas WHERE id = %s FOR UPDATE", (idea_uuid,)).fetchone()
        if idea is None or idea["contributor_code"] != contributor_code:
            raise ActionRefused(404, "not_found")
        q = conn.execute(
            "SELECT * FROM idea_questions WHERE idea_uuid = %s AND answered_at IS NULL ORDER BY id DESC LIMIT 1 FOR UPDATE",
            (idea_uuid,),
        ).fetchone()
        if q is None or idea["stage"] not in ("needs_info", "withdrawn"):
            raise ActionRefused(409, "no_open_question")
        tagged = _tagged(conn, idea["idea_id"], text, min_chars=5)
        conn.execute(
            "UPDATE idea_questions SET answer_encrypted = %s, answered_at = %s WHERE id = %s",
            (encrypt_json({"text": tagged}, f"answer:{q['id']}"), now, q["id"]),
        )
        conn.execute("UPDATE ideas SET stage = 'scanned' WHERE id = %s", (idea_uuid,))
        engine.stop(conn, "idea", idea["idea_id"], "needs_info")
        if q["review_item_id"]:
            conn.execute("UPDATE review_items SET state = 'open' WHERE id = %s", (q["review_item_id"],))
            engine.resume(conn, "review_item", str(q["review_item_id"]), "review", now=now)
        return {"stage": "scanned"}


def disagree(conn: Conn, idea_uuid: str, contributor_code: str, text: str) -> dict[str, Any]:
    """ "Disagree with this?": a `disagreement` item in the core committee's view (§4.12 day one, AT-B6-09)."""
    with conn.transaction():
        idea = conn.execute(
            "SELECT idea_id, contributor_code FROM ideas WHERE id = %s", (idea_uuid,)
        ).fetchone()
        if idea is None or idea["contributor_code"] != contributor_code or not idea["idea_id"]:
            raise ActionRefused(404, "not_found")
        stage = conn.execute("SELECT stage FROM ideas WHERE id = %s", (idea_uuid,)).fetchone()
        if stage is None or stage["stage"] not in (
            "reviewed",
            "in_cluster",
            "declined",
            "redirected",
            "parked",
        ):
            raise ActionRefused(409, "nothing_to_disagree_with")
        if conn.execute(
            "SELECT 1 FROM review_items WHERE item_type = 'disagreement' AND ref_id = %s AND state = 'open'",
            (idea["idea_id"],),
        ).fetchone():
            raise ActionRefused(409, "already_raised")  # one open disagreement per idea
        reason = _tagged(conn, idea["idea_id"], text, min_chars=15)
        row = conn.execute(
            "INSERT INTO review_items (item_type, ref_id, reasons) VALUES ('disagreement', %s, %s) RETURNING id",
            (idea["idea_id"], Jsonb({"person_says": reason})),
        ).fetchone()
        assert row is not None
        return {"item_id": int(row["id"])}
