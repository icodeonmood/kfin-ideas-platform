"""The person's choice in Find your crew, and the save (§4.2 steps 7–8). One database transaction:

- `ideas`: stage (`scanned`; `merged` after "Team up" or "+1"; `adoption_requested` after teaming up with a
  solution; `withdrawn`), the confirmed card (tagged), `raw_encrypted` cleared;
- `idea_links`: the originator, plus the joiner, plus-one or adoption link (a join to an idea outside a cluster is
  the must-link pair the weekly batch keeps together, §4.4 A);
- `review_items`: the assistant's proposals, its flags and confidences, the candidates and the person's choice;
- `sla_timers`: review, 5 working days (`rules/sla.md`, `rules/calendar.md`);
- `outbox`: `idea.submitted`, so the repo writer creates the idea file.
A failure anywhere rolls all of it back (AT-B5-08). Withdrawing writes only the idea row.

Choices (AT-B5-06): `team_up` (30+ characters of context for ideas and clusters; on a solution it is an adoption
request with a message to the owning team), `plus_one`, `different` (one line on how), `something_changed`
(for a decision: what changed), `new` (no match chosen), `withdraw`.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from psycopg.types.json import Jsonb

from comms.route import emit
from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from gateway import run_agent
from pii.patterns import scan
from pii.tagger import tag_payload
from rules import load_rule
from scan.matching import shown
from scan.pipeline import about_investor, decide, load_result, thresholds
from sla.calendar import add_working_days, limit_wd

log = get_logger("scan.save")
CHOICES = ("team_up", "plus_one", "different", "something_changed", "new", "withdraw")


class SaveRefused(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status, self.code = status, code


def _hook_after_idea_update(conn: Conn, idea_uuid: str) -> None:
    """Test seam for AT-B5-08 (an injected failure after the ideas update must roll everything back)."""


def _target(conn: Conn, result: dict[str, Any], ref: str | None, owner_code: str) -> dict[str, Any] | None:
    """The candidate behind a card the person was actually shown (same list and numbering as the view)."""
    if not ref:
        return None
    items, _ = shown(conn, result.get("match") or {}, owner_code)
    return next((c for r, c, _row in items if r == ref), None)


def _owned_by(conn: Conn, cid: str, contributor_code: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM idea_links WHERE idea_id = %s AND contributor_code = %s AND link_type = 'originator' "
        "UNION SELECT 1 FROM ideas WHERE idea_id = %s AND contributor_code = %s LIMIT 1",
        (cid, contributor_code, cid, contributor_code),
    ).fetchone()
    return row is not None


def _already_linked(conn: Conn, cid: str, contributor_code: str, link_type: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM idea_links WHERE coalesce(idea_id, cluster_id, solution_id) = %s AND contributor_code = %s "
        "AND link_type = %s LIMIT 1",
        (cid, contributor_code, link_type),
    ).fetchone()
    return row is not None


def _checked_text(conn: Conn, idea_id: str, text: str) -> str:
    """The person's free text on a choice: patterns, then the gatekeeper (outside any transaction), then tags."""
    if any(m.action == "block" for m in scan(text, kfin_domains=get_settings().kfin_domains)):
        raise SaveRefused(422, "personal_data")
    gk = run_agent(
        "gatekeeper", {"mode": "submission", "submission": {"choice_text": text}}, idea_id, conn=conn
    )
    if decide(gk.data, thresholds()) == "blocked":
        raise SaveRefused(422, "personal_data")
    return str(tag_payload(conn, idea_id, {"t": text}).payload["t"])


def save(conn: Conn, idea_uuid: str, contributor_code: str, body: dict[str, Any]) -> dict[str, Any]:
    choice = body.get("choice")
    if choice not in CHOICES:
        raise SaveRefused(400, "choice_required")
    needs_text = choice in ("team_up", "different", "something_changed")
    text = str(body.get("text") or "").strip()[:1000] if needs_text else ""
    canvas_rules = load_rule(get_settings().company_repo_path, "thresholds").data["canvas"]

    # Checks first, with no lock held: they may call the gatekeeper.
    idea = conn.execute(
        "SELECT id, idea_id, stage, contributor_code FROM ideas WHERE id = %s", (idea_uuid,)
    ).fetchone()
    if idea is None or idea["contributor_code"] != contributor_code:
        raise SaveRefused(404, "not_found")
    scan_row = conn.execute("SELECT * FROM scans WHERE idea_uuid = %s", (idea_uuid,)).fetchone()
    if idea["stage"] != "scanning" or scan_row is None or scan_row["outcome"] != "ready":
        raise SaveRefused(409, "not_available_now")
    idea_id = idea["idea_id"]
    result = load_result(scan_row)
    target: dict[str, Any] | None = None
    tagged_text: str | None = None
    if choice != "withdraw":
        if result.get("confirmed") is None:
            raise SaveRefused(409, "confirm_first")
        if choice in ("team_up", "plus_one", "different", "something_changed"):
            target = _target(conn, result, body.get("ref"), contributor_code)
            if target is None:
                raise SaveRefused(400, "match_required")
            if target["type"] == "idea" and _owned_by(conn, target["cid"], contributor_code):
                raise SaveRefused(409, "own_idea")
            kind = {
                "team_up": "adoption" if target["type"] == "solution" else "joiner",
                "plus_one": "plus_one",
            }
            if choice in kind and _already_linked(conn, target["cid"], contributor_code, kind[choice]):
                raise SaveRefused(409, "already_on_it")
        if (
            choice == "team_up"
            and target
            and target["type"] in ("idea", "cluster")
            and len(text) < int(canvas_rules["join_context_min_chars"])
        ):
            raise SaveRefused(422, "context_too_short")
        if choice in ("different", "something_changed") and len(text.split()) < 3:
            raise SaveRefused(422, "one_line_required")
        if choice == "team_up" and target and target["type"] == "decision":
            raise SaveRefused(400, "not_for_decisions")
        if text:
            tagged_text = _checked_text(conn, idea_id, text)

    with conn.transaction():
        locked = conn.execute(
            "SELECT i.stage, s.outcome, s.updated_at FROM ideas i JOIN scans s ON s.idea_uuid = i.id "
            "WHERE i.id = %s FOR UPDATE OF i, s",
            (idea_uuid,),
        ).fetchone()
        if (
            locked is None
            or locked["stage"] != "scanning"
            or locked["outcome"] != "ready"
            or (locked["updated_at"] != scan_row["updated_at"])
        ):
            raise SaveRefused(409, "not_available_now")  # saved, withdrawn or re-confirmed meanwhile

        if choice == "withdraw":
            conn.execute(
                "UPDATE ideas SET stage = 'withdrawn', raw_encrypted = NULL WHERE id = %s", (idea_uuid,)
            )
            conn.execute("UPDATE scans SET result_encrypted = NULL WHERE idea_uuid = %s", (idea_uuid,))
            log.info("scan.saved", idea_uuid=idea_uuid, choice=choice)
            return {"stage": "withdrawn", "idea_id": idea_id}
        card = dict(result["confirmed"])
        # The person's own words as first submitted (tagged), shown beside the confirmed card on review (§4.3).
        card["original_text"] = (result.get("canvas_assist") or {}).get("details")

        stage = "scanned"
        link: tuple[str, str] | None = None  # (link_type, target column)
        if choice == "team_up" and target:
            if target["type"] == "solution":
                stage, link = "adoption_requested", ("adoption", "solution_id")
            else:
                stage, link = "merged", ("joiner", "cluster_id" if target["type"] == "cluster" else "idea_id")
        elif choice == "plus_one" and target:
            if target["type"] not in ("idea", "cluster"):
                raise SaveRefused(400, "not_for_this_match")
            stage, link = "merged", ("plus_one", "cluster_id" if target["type"] == "cluster" else "idea_id")

        ca = result["canvas_assist"]
        value = card.get("value") or {}
        conn.execute(
            "UPDATE ideas SET stage = %s, canvas = %s, raw_encrypted = NULL, kind = %s, category = %s, play = %s, "
            "basis = %s, cluster_id = %s WHERE id = %s",
            (
                stage, Jsonb(card), card.get("kind"), value.get("category"), value.get("play"), value.get("basis"),
                target["cid"] if target and link and link[1] == "cluster_id" else None, idea_uuid,
            ),
        )  # fmt: skip
        _hook_after_idea_update(conn, idea_uuid)

        conn.execute(
            "INSERT INTO idea_links (idea_id, contributor_code, link_type) VALUES (%s, %s, 'originator') "
            "ON CONFLICT DO NOTHING",
            (idea_id, contributor_code),
        )
        if link and target:
            conn.execute(
                f"INSERT INTO idea_links ({link[1]}, from_idea_id, contributor_code, link_type, context_text) "  # noqa: S608 - column from a fixed set
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (target["cid"], idea_id, contributor_code, link[0], tagged_text),
            )

        overrides = scan_row["overrides"] or {}
        flags = list(ca.get("flags_for_reviewer") or [])
        # A contested block (§4.2 step 3, BLD-082 option B): a code only. The desk sees it in plain words, and an
        # item the check read as naming an investor or customer goes to the top of the queue.
        contested = None
        if overrides.get("not_personal_data"):
            gk = result.get("gatekeeper")
            contested = "investor_or_customer" if gk and about_investor(gk) else "personal_data"
        if overrides.get("is_an_idea"):
            flags.append("The person said this is an idea, not a request for another team.")
        now = dt.datetime.now(dt.UTC)
        due = add_working_days(now, limit_wd("review"))
        item = conn.execute(
            "INSERT INTO review_items (item_type, ref_id, proposal, confidence, reasons, due_at) "
            "VALUES ('idea', %s, %s, %s, %s, %s) RETURNING id",
            (
                idea_id,
                Jsonb(
                    {
                        "system": ca.get("system"),
                        "suggested_action": {
                            "scanned": "review",
                            "merged": "confirm_join",
                            "adoption_requested": "route_adoption",
                        }[stage],
                        "candidates": (result.get("match") or {}).get("candidates") or [],
                        "best_same": (result.get("match") or {}).get("best_same"),
                        "choice": {"choice": choice, "target": target["cid"] if target else None},
                    }
                ),
                Jsonb(ca.get("confidence") or {}),
                Jsonb(
                    {
                        "flags_for_reviewer": flags,
                        "contested": contested,
                        "person_says": tagged_text,
                        "edited_after_scan": bool(result.get("confirmed") is not None),
                    }
                ),
                due,
            ),
        ).fetchone()
        assert item is not None
        conn.execute(
            "INSERT INTO sla_timers (entity_type, entity_id, stage, started_at, due_at) "
            "VALUES ('review_item', %s, 'review', %s, %s)",
            (str(item["id"]), now, due),
        )
        emit(conn, "idea.submitted", {"idea_id": idea_id})
        if link and target and link[0] in ("joiner", "plus_one"):
            emit(
                conn,
                "idea.joined",
                {"target_id": target["cid"], "joiner_code": contributor_code, "idea_id": idea_id},
            )
        if stage == "adoption_requested" and target:
            row = conn.execute(
                "SELECT l.id, (SELECT lobs[1] FROM repo_files WHERE kfin_id = %s LIMIT 1) AS team FROM idea_links l "
                "WHERE l.from_idea_id = %s AND l.solution_id = %s",
                (target["cid"], idea_id, target["cid"]),
            ).fetchone()
            emit(
                conn,
                "adoption.requested",
                {
                    "idea_id": idea_id,
                    "solution_id": target["cid"],
                    "owner_team": row["team"] if row else None,
                    "link_id": row["id"] if row else None,
                },
            )  # routed to the owning team's LOB committee, else the review desk (BLD-088)
        conn.execute(
            "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES ('idea.submitted', %s, %s, %s)",
            (idea_id, contributor_code, Jsonb({"idea_uuid": idea_uuid, "choice": choice})),
        )
    log.info("scan.saved", idea_uuid=idea_uuid, choice=choice)
    return {"stage": stage, "idea_id": idea_id}
