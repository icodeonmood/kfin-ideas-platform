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

from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from pii.patterns import scan
from pii.tagger import tag_payload
from rules import load_rule
from scan.pipeline import load_result
from sla.calendar import add_working_days, limit_wd

log = get_logger("scan.save")
CHOICES = ("team_up", "plus_one", "different", "something_changed", "new", "withdraw")


class SaveRefused(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status, self.code = status, code


def _hook_after_idea_update(conn: Conn, idea_uuid: str) -> None:
    """Test seam for AT-B5-08 (an injected failure after the ideas update must roll everything back)."""


def _target(result: dict[str, Any], ref: str | None) -> dict[str, Any] | None:
    if not ref or not ref.startswith("m"):
        return None
    try:
        i = int(ref[1:]) - 1
    except ValueError:
        return None
    cands = (result.get("match") or {}).get("candidates") or []
    if not 0 <= i < len(cands):
        return None
    c: dict[str, Any] = cands[i]
    # Only what the person was shown: same or related, never committee-only.
    return c if c["label"] in ("same", "related") and c["visibility"] != "committee" else None


def save(conn: Conn, idea_uuid: str, contributor_code: str, body: dict[str, Any]) -> dict[str, Any]:
    choice = body.get("choice")
    if choice not in CHOICES:
        raise SaveRefused(400, "choice_required")
    text = str(body.get("text") or "").strip()[:1000]
    canvas_rules = load_rule(get_settings().company_repo_path, "thresholds").data["canvas"]

    with conn.transaction():
        idea = conn.execute(
            "SELECT id, idea_id, stage, contributor_code, visibility FROM ideas WHERE id = %s FOR UPDATE",
            (idea_uuid,),
        ).fetchone()
        if idea is None or idea["contributor_code"] != contributor_code:
            raise SaveRefused(404, "not_found")
        scan_row = conn.execute(
            "SELECT * FROM scans WHERE idea_uuid = %s FOR UPDATE", (idea_uuid,)
        ).fetchone()
        if idea["stage"] != "scanning" or scan_row is None or scan_row["outcome"] != "ready":
            raise SaveRefused(409, "not_available_now")
        result = load_result(scan_row)
        idea_id = idea["idea_id"]

        if choice == "withdraw":
            conn.execute(
                "UPDATE ideas SET stage = 'withdrawn', raw_encrypted = NULL WHERE id = %s", (idea_uuid,)
            )
            conn.execute("UPDATE scans SET result_encrypted = NULL WHERE idea_uuid = %s", (idea_uuid,))
            log.info("scan.saved", idea_uuid=idea_uuid, choice=choice)
            return {"stage": "withdrawn", "idea_id": idea_id}

        card = result.get("confirmed")
        if card is None:
            raise SaveRefused(409, "confirm_first")
        target = _target(result, body.get("ref"))
        if choice in ("team_up", "plus_one", "different", "something_changed") and target is None:
            raise SaveRefused(400, "match_required")
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
        if text and any(m.action == "block" for m in scan(text, kfin_domains=get_settings().kfin_domains)):
            raise SaveRefused(422, "personal_data")
        tagged_text = tag_payload(conn, idea_id, {"t": text}).payload["t"] if text else None

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
        if overrides.get("not_personal_data"):
            flags.append("The person said a personal-data block was wrong; please check.")
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
        if stage == "adoption_requested" and target:
            conn.execute(
                "INSERT INTO comms_log (event, template_version, recipients, channel, state, message_ref) "
                "VALUES ('adoption.requested', 'TPL-adoption-requested@1.0', '{}', 'in_app', 'pending', %s)",
                (f"{idea_id}->{target['cid']}",),
            )  # routed to the owning team by the comms module (BLD-085)
        conn.execute(
            "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES ('idea.submitted', %s, %s, %s)",
            (idea_id, contributor_code, Jsonb({"idea_uuid": idea_uuid, "choice": choice})),
        )
    log.info("scan.saved", idea_uuid=idea_uuid, choice=choice)
    return {"stage": stage, "idea_id": idea_id}
