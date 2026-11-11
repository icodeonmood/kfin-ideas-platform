"""Run the scan for one submitted idea (§4.2 steps 3–4; B5 adds matching).

Sync mode runs straight after submit, inside the 20-second limit (`scan.fallback_after_s`). Any agent failure,
a switched-off agent or a slow scan moves the idea to `waiting`: it stays saved as `scanning` with its text
encrypted, `scan.async` retries at 1, 5, 15 and 60 minutes, the person is told they will hear within the hour
and the review desk sees "awaiting scan". When `ai.all` is off the async job waits for it to come back on
without using up its retries. After the last retry the scan is marked `manual` for the review desk.
"""

from __future__ import annotations

import time
from typing import Any

from psycopg.types.json import Jsonb

from core.config import get_settings
from core.crypto import decrypt_json, encrypt_json
from core.db import Conn
from core.logging import get_logger
from embeddings import embed
from gateway import AgentFailed, AgentSwitchedOff, LeakAbort, run_agent
from router.corrections import corrections_for
from router.taxonomy import taxonomy_slice
from rules import load_rule
from scan.inputs import assumptions, canvas_answers, gatekeeper_input
from scan.matching import run_matching

log = get_logger("scan")
REDIRECT_KINDS = ("it_ticket", "hr_grievance", "complaint", "question")
# Spans that identify an investor or customer. Since BLD-082 (option B, 9 Nov 2026) a person can contest these like
# any other gatekeeper block; the item then reaches the review desk marked "check first" (scan/save.py).
# Pattern blocks (§4.2 step 2: PAN, Aadhaar, mobile, folio and the rest) are refused at submit and never get here.
INVESTOR_SPANS = frozenset({"tagged_person_as_investor", "investor_or_customer_name"})


def about_investor(gk: dict[str, Any]) -> bool:
    """Did the gatekeeper read the block as naming an investor or customer?"""
    if gk["investor_context_tags"]:
        return True
    return any(s["data_type"] in INVESTOR_SPANS for s in gk["personal_data"]["spans"])


class TooSlow(Exception):
    pass


# What the review desk reads when the gateway dropped suggestions the person's words did not back (DEC-095).
FLAG_SUMMARY_BLANK = "The short summary for colleagues was left blank; please write one."
FLAG_DROPPED = "Some suggestions were left out because the person's own words did not support them."
MAX_FLAGS = 5


def with_drop_flags(ca: dict[str, Any], dropped: list[str]) -> dict[str, Any]:
    """The canvas-assist output with neutral reviewer flags for what the gateway dropped (paths only, no text)."""
    if not dropped:
        return ca
    flags = [FLAG_SUMMARY_BLANK] if "neutral_summary" in dropped else []
    if any(p != "neutral_summary" for p in dropped):
        flags.append(FLAG_DROPPED)
    kept = [f for f in ca.get("flags_for_reviewer") or [] if f not in flags]
    return {**ca, "flags_for_reviewer": (flags + kept)[:MAX_FLAGS]}


def thresholds() -> dict[str, Any]:
    data = load_rule(get_settings().company_repo_path, "thresholds").data
    return {"gatekeeper": dict(data["gatekeeper"]), "scan": dict(data.get("scan") or {})}


def decide(gk: dict[str, Any], th: dict[str, Any]) -> str:
    """pass | blocked | redirect | held, from the gatekeeper's output and `rules/thresholds.md`."""
    g = th["gatekeeper"]
    pd = gk["personal_data"]
    if (pd["found"] and pd["confidence"] >= g["personal_data_block"]) or gk["investor_context_tags"]:
        return "blocked"
    kind, conf = gk["kind"]["value"], gk["kind"]["confidence"]
    if kind in REDIRECT_KINDS and conf >= g["redirect_suggest"]:
        return "redirect"
    if kind == "spam" and conf >= g["spam_hold"]:
        return "held"
    if gk["abuse"]["value"] and gk["abuse"]["confidence"] >= g["redirect_suggest"]:
        return "held"  # BLD-074: abusive text waits for a person
    return "pass"


def _set(conn: Conn, idea_uuid: str, **cols: Any) -> None:
    sets = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(f"UPDATE scans SET {sets} WHERE idea_uuid = %s", (*cols.values(), idea_uuid))  # noqa: S608


def _save_result(conn: Conn, idea_uuid: str, result: dict[str, Any]) -> None:
    _set(conn, idea_uuid, result_encrypted=encrypt_json(result, f"scan:{idea_uuid}"))


def load_result(row: dict[str, Any]) -> dict[str, Any]:
    blob = row.get("result_encrypted")
    return decrypt_json(bytes(blob), f"scan:{row['idea_uuid']}") if blob else {}


def _attachments(conn: Conn, idea_uuid: str) -> list[dict[str, Any]]:
    """Research files for canvas assist, with any digest that is ready. Digests are stored tagged under the
    idea's scope; they are restored here so the gateway tags them again consistently (§3.2 step 1)."""
    from pii import vault
    from pii.restore import restore

    rows = conn.execute(
        "SELECT a.id, a.name, a.state, a.digest, i.idea_id FROM attachments a JOIN ideas i ON i.id = a.idea_uuid "
        "WHERE a.idea_uuid = %s AND a.state <> 'rejected' ORDER BY a.created_at",
        (idea_uuid,),
    ).fetchall()
    mapping = vault.mapping(conn, rows[0]["idea_id"]) if rows and rows[0]["idea_id"] else {}
    return [
        {"id": r["id"], "name": r["name"], "state": "processing" if r["state"] == "quarantine" else r["state"],
         "digest": restore(r["digest"], mapping, "real") if r["state"] == "clean" and r["digest"] else None}
        for r in rows
    ]  # fmt: skip


def go_async(conn: Conn, idea_uuid: str, code: str) -> None:
    _set(conn, idea_uuid, state="waiting", error_code=code[:60])
    conn.execute(
        "INSERT INTO jobs (type, payload, run_at, dedupe_key) VALUES ('scan.async', %s, now() + interval '1 minute', %s) "
        "ON CONFLICT DO NOTHING",
        (Jsonb({"idea_uuid": idea_uuid}), f"scan-async:{idea_uuid}:{int(time.time())}"),
    )
    log.warning("scan.waiting", idea_uuid=idea_uuid, error_code=code[:60])


def run(conn: Conn, idea_uuid: str, *, mode: str = "sync") -> str:
    """Returns the scan state after this run: done, waiting, or skipped."""
    idea = conn.execute(
        "SELECT id, idea_id, stage, raw_encrypted FROM ideas WHERE id = %s", (idea_uuid,)
    ).fetchone()
    if idea is None or idea["stage"] != "scanning" or idea["raw_encrypted"] is None:
        return "skipped"
    conn.execute("INSERT INTO scans (idea_uuid) VALUES (%s) ON CONFLICT DO NOTHING", (idea_uuid,))
    row = conn.execute("SELECT * FROM scans WHERE idea_uuid = %s", (idea_uuid,)).fetchone()
    assert row is not None
    if row["state"] == "done":
        return "done"
    started = time.monotonic()
    _set(conn, idea_uuid, state="running", attempts=row["attempts"] + 1)
    conn.execute(
        "UPDATE scans SET started_at = coalesce(started_at, now()) WHERE idea_uuid = %s", (idea_uuid,)
    )
    th = thresholds()
    limit = float(th["scan"].get("fallback_after_s", 20))
    canvas = decrypt_json(bytes(idea["raw_encrypted"]), str(idea_uuid))
    result = load_result(row)
    overrides = row["overrides"] or {}
    ref = str(idea["idea_id"])

    def finish(outcome: str, stage: str | None = None) -> str:
        _set(
            conn, idea_uuid, state="done", step="done", outcome=outcome, error_code=None,
            duration_ms=int((time.monotonic() - started) * 1000),
        )  # fmt: skip
        conn.execute("UPDATE scans SET finished_at = now() WHERE idea_uuid = %s", (idea_uuid,))
        if stage:
            conn.execute(
                "UPDATE ideas SET stage = %s WHERE id = %s AND stage = 'scanning'", (stage, idea_uuid)
            )
        log.info("scan.finished", idea_uuid=idea_uuid, outcome=outcome, scan_mode=mode)
        return "done"

    try:
        if "gatekeeper" not in result:
            _set(conn, idea_uuid, step="gatekeeper")
            gk = run_agent("gatekeeper", gatekeeper_input(canvas), ref, conn=conn)
            result["gatekeeper"] = gk.data
            _save_result(conn, idea_uuid, result)
            conn.execute(
                "UPDATE ideas SET language = %s WHERE id = %s", (gk.data["language"]["primary"], idea_uuid)
            )
        decision = decide(result["gatekeeper"], th)
        # A contested block goes through, flagged for the reviewer (§4.2 step 3).
        if decision == "blocked" and not overrides.get("not_personal_data"):
            return finish("blocked", "blocked")
        if decision == "redirect" and not overrides.get("is_an_idea"):
            return finish("redirect")
        if decision == "held":
            return finish("held")
        if mode == "sync" and time.monotonic() - started > limit:
            raise TooSlow()
        if "canvas_assist" not in result:
            _set(conn, idea_uuid, step="canvas_assist")
            text = " ".join(str(v) for v in gatekeeper_input(canvas)["submission"].values())
            gk_out = result["gatekeeper"]
            ca = run_agent(
                "canvas-assist",
                {
                    "canvas_answers": canvas_answers(canvas, _attachments(conn, idea_uuid)),
                    "taxonomy_slice": taxonomy_slice(conn, text),
                    "gatekeeper": {"kind": gk_out["kind"], "language": gk_out["language"]},
                    "past_corrections": corrections_for(conn, embed([text])[0]),
                    "assumptions": assumptions(),
                },
                ref,
                conn=conn,
            )
            result["canvas_assist"] = with_drop_flags(ca.data, ca.dropped)
            _save_result(conn, idea_uuid, result)
        if mode == "sync" and time.monotonic() - started > limit:
            raise TooSlow()
        _set(conn, idea_uuid, step="matching")
        result["match"] = run_matching(conn, ref, result["canvas_assist"])
        _save_result(conn, idea_uuid, result)
        if mode == "sync" and time.monotonic() - started > limit:
            raise TooSlow()
        return finish("ready")
    except LeakAbort:
        # Detection missed something in this idea: retrying would only repeat it. A person takes over.
        give_up(conn, idea_uuid, code="leak_check")
        return "manual"
    except AgentSwitchedOff as exc:
        if mode == "sync":
            go_async(conn, idea_uuid, exc.code)
            return "waiting"
        _set(conn, idea_uuid, state="waiting", error_code=exc.code[:60])
        raise
    except Exception as exc:  # agent failures, a slow scan, and anything unexpected: never leave it running
        code = (
            exc.code
            if isinstance(exc, AgentFailed)
            else ("too_slow" if isinstance(exc, TooSlow) else "scan_error")
        )
        if code == "scan_error":
            log.error("scan.error", idea_uuid=idea_uuid, error_type=type(exc).__name__)
        if mode == "sync":
            go_async(conn, idea_uuid, code)
            return "waiting"
        _set(conn, idea_uuid, state="waiting", error_code=code[:60])
        raise


def give_up(conn: Conn, idea_uuid: str, code: str = "retries_exhausted") -> None:
    """Every async retry failed, or retrying cannot help: the review desk handles this scan by hand."""
    _set(conn, idea_uuid, state="manual", error_code=code)
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity) VALUES ('process:scan', 'alert.scan_manual', %s)",
        (f"idea:{idea_uuid}",),
    )
    log.error("scan.manual", idea_uuid=idea_uuid)
