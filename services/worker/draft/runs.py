"""Runs: the parts of a draft built again after a message (L-DRAFT.parts, A-API.draft-stream). BLD-C073.

`begin` (inside the caller's transaction) records the run and marks only the parts the message could change as
`updating`, never a part the person pinned. `dispatch` then runs them after the commit, in parallel, each part its
own call through the gateway (`run_agent("draft-part", …)`, non-negotiable 1) on the masked words only
(L-DRAFT.parts/4), and `_finish` writes the receipt and the next prompts. Each part writes its result only while
the part is still this run's and still `updating`: a newer run, or the person's own change, always wins.

With `ai.all` (or `agent.draft-part`) off, no agent part runs: each part being rebuilt is left as it was, or marked
`failed` when it has nothing yet, so the screen offers to fill it by hand (DEC-105, `C-DRAFT-LOADER.failure`).
A run still going after `run_stale_seconds` (a worker restart) is settled the same way on the next read.
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any

from psycopg.types.json import Jsonb

from core import killswitch
from core.db import Conn, connect
from core.logging import get_logger
from draft import adapters, parts
from draft.config import PART_KEYS, rules
from gateway import AgentFailed, run_agent
from gateway.core import DROPPED
from onepc import enums
from onepc.context import open_text
from pii import vault
from pii.restore import restore

log = get_logger("draft.runs")
AGENT = "draft-part"
RUN_TIMEOUT_S = 45.0
MEANS_TTL_S = 60.0
_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="draft-run")
_PART_POOL = ThreadPoolExecutor(max_workers=24, thread_name_prefix="draft-part")
_means_cache: dict[str, Any] = {"at": 0.0, "means": None}


def _open() -> Conn:
    """A connection for work off the request (the run and each part). Tests point it at their database."""
    return connect(autocommit=True)


def scope(idea_uuid: str) -> str:
    """The draft's vault scope, as L-HIDE, the seed and the gateway's auto switch-offs know it (`DRAFT-…`), from
    `hide.core.scope_for` (BLD-C151)."""
    return adapters.vault_scope(idea_uuid)


def ai_on(conn: Conn) -> bool:
    return killswitch.is_on("ai.all", conn) and killswitch.is_on(f"agent.{AGENT}", conn)


def current(conn: Conn, idea_uuid: str) -> dict[str, tuple[str, Any]]:
    rows = conn.execute(
        "SELECT key, state, value FROM idea_parts WHERE idea_uuid = %s", (idea_uuid,)
    ).fetchall()
    return {str(r["key"]): (str(r["state"]), r["value"]) for r in rows}


def values(conn: Conn, idea_uuid: str) -> dict[str, Any]:
    return {k: v for k, (_, v) in current(conn, idea_uuid).items()}


def words(conn: Conn, idea_uuid: str) -> list[dict[str, Any]]:
    """The person's words as every service receives them: masked (DEC-103), one message at a time, with the English
    copy of a voice note or another language as context (DEC-108)."""
    rows = conn.execute(
        "SELECT id, text_encrypted, text_en_encrypted FROM idea_messages WHERE idea_uuid = %s "
        "ORDER BY created_at, seq",
        (idea_uuid,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        mid = str(r["id"])
        text = open_text("idea_messages", "text_encrypted", mid, r["text_encrypted"])
        if not text:
            continue
        item: dict[str, Any] = {"n": len(out) + 1, "text": text}
        english = open_text("idea_messages", "text_en_encrypted", mid, r["text_en_encrypted"])
        if english:
            item["english"] = english
        out.append(item)
    return out


def options_for(key: str) -> dict[str, Any] | None:
    r = rules()
    if key == "who":
        return {"choices": [{"label": o.label, "cues": list(o.cues)} for o in r.affects]}
    if key == "area":
        return {"choices": [{"label": o.label, "cues": list(o.cues)} for o in r.area]}
    if key == "value":
        labels = enums.labels("brings")
        return {"choices": [{"id": b, "label": labels.get(b, b)} for b in enums.BRINGS]}
    return None


# ---- the loader's means (L-DRAFT.parts/6, C-DRAFT-LOADER.maths) ---------------------------------------------------


def means(conn: Conn) -> dict[str, int]:
    """The median time per part over the last `latency_days` (finished runs, real calls only), else the defaults."""
    now = time.monotonic()
    if _means_cache["means"] is not None and now - _means_cache["at"] < MEANS_TTL_S:
        return dict(_means_cache["means"])
    r = rules()
    rows = conn.execute(
        "SELECT e.key, percentile_cont(0.5) WITHIN GROUP (ORDER BY e.value::int) AS p50 "
        "FROM draft_runs d, jsonb_each_text(d.part_ms) e "
        "WHERE d.state = 'done' AND d.started_at > now() - make_interval(days => %s) AND e.value::int > 0 "
        "GROUP BY e.key",
        (r.latency_days,),
    ).fetchall()
    out = dict(r.default_means_ms)
    for row in rows:
        if row["key"] in out and row["p50"] is not None:
            out[str(row["key"])] = int(row["p50"])
    _means_cache.update(at=now, means=out)
    return out


# ---- begin: inside the caller's transaction -----------------------------------------------------------------------


def plan(
    conn: Conn, idea_uuid: str, *, trigger: str, new_text: str = "", only: list[str] | None = None
) -> list[str]:
    """The parts this run builds again (L-DRAFT.parts/4): what the message could change, never a pinned part,
    nothing below `parts_from_chars`; similar ideas from `similar_from_chars`, when the title is rebuilt."""
    r = rules()
    row = conn.execute("SELECT char_count FROM ideas WHERE id = %s", (idea_uuid,)).fetchone()
    chars = int(row["char_count"]) if row else 0
    if chars < r.parts_from_chars:
        return []
    now = current(conn, idea_uuid)
    if only is not None:
        keys = [
            k for k in only if k in parts.AGENT_PARTS and parts.runnable(k, *now.get(k, ("waiting", None)))
        ]
    elif trigger == "message":
        keys = parts.affected(new_text, now, r.affects, r.area)
    else:  # an edited message, a retry or a build after the interview: everything not pinned
        keys = [k for k in parts.AGENT_PARTS if parts.runnable(k, *now.get(k, ("waiting", None)))]
    similar_state = now.get("similar", ("waiting", None))[0]
    if chars >= r.similar_from_chars and only is None and ("title" in keys or similar_state != "filled"):
        keys.append("similar")
    return keys


def begin(
    conn: Conn,
    idea_uuid: str,
    *,
    trigger: str,
    message_id: str | None = None,
    new_text: str = "",
    only: list[str] | None = None,
) -> str | None:
    """Record a run and mark its parts `updating`. None when there is nothing to build yet."""
    keys = plan(conn, idea_uuid, trigger=trigger, new_text=new_text, only=only)
    if not keys:
        return None
    run_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO draft_runs (id, idea_uuid, message_id, state, parts) VALUES (%s, %s, %s, 'running', %s)",
        (run_id, idea_uuid, message_id, keys),
    )
    for key in keys:
        conn.execute(
            "INSERT INTO idea_parts (idea_uuid, key, state, run_id) VALUES (%s, %s, 'updating', %s) "
            "ON CONFLICT (idea_uuid, key) DO UPDATE SET state = 'updating', run_id = EXCLUDED.run_id",
            (idea_uuid, key, run_id),
        )
    if not ai_on(conn):
        # DEC-105: no model. Each agent part keeps what it had, or asks the person to fill it ("failed").
        skipped = [k for k in keys if k in parts.AGENT_PARTS]
        for key in skipped:
            _settle(conn, idea_uuid, key, run_id)
        conn.execute(
            "UPDATE draft_runs SET part_ms = part_ms || %s WHERE id = %s",
            (Jsonb(dict.fromkeys(skipped, 0)), run_id),
        )
        if "similar" not in keys:
            finish(conn, run_id, before=None)
    log.info("draft.run_begun", run_id=run_id, part_count=len(keys), trigger_code=trigger)
    return run_id


def _settle(conn: Conn, idea_uuid: str, key: str, run_id: str) -> bool:
    """A part this run will not build: back to what it showed, or `failed` when it had nothing. False when the part
    is no longer this run's to settle."""
    return (
        conn.execute(
            "UPDATE idea_parts SET state = CASE WHEN value IS NULL OR value IN ('null'::jsonb, '[]'::jsonb, '\"\"'::jsonb) "
            "OR (key = 'title' AND coalesce(value->>'title', '') = '') THEN 'failed' "
            "WHEN key = 'title' AND value->'pinned' @> '[\"title\", \"summary\"]'::jsonb THEN 'pinned' ELSE 'filled' END "
            "WHERE idea_uuid = %s AND key = %s AND run_id = %s AND state = 'updating'",
            (idea_uuid, key, run_id),
        ).rowcount
        > 0
    )


def settle_stale(conn: Conn, idea_uuid: str) -> None:
    """Runs left going by a worker that stopped: failed, and their parts back to what they showed."""
    stale = conn.execute(
        "UPDATE draft_runs SET state = 'failed', finished_at = now() WHERE idea_uuid = %s AND state = 'running' "
        "AND started_at < now() - make_interval(secs => %s) RETURNING id",
        (idea_uuid, rules().run_stale_seconds),
    ).fetchall()
    for row in stale:
        for key in PART_KEYS:
            _settle(conn, idea_uuid, key, str(row["id"]))
        log.warning("draft.run_stale", run_id=str(row["id"]))


# ---- execute: after the commit, off the request ------------------------------------------------------------------


def dispatch(run_id: str | None) -> None:
    if run_id:
        _POOL.submit(_safe_execute, run_id)


def _safe_execute(run_id: str) -> None:
    try:
        execute(run_id)
    except Exception:
        log.exception("draft.run_crashed", run_id=run_id)
        try:
            with _open() as conn:
                row = conn.execute(
                    "UPDATE draft_runs SET state = 'failed', finished_at = now() WHERE id = %s AND state = 'running' "
                    "RETURNING idea_uuid",
                    (run_id,),
                ).fetchone()
                if row:
                    for key in PART_KEYS:
                        _settle(conn, str(row["idea_uuid"]), key, run_id)
        except Exception:
            log.exception("draft.run_settle_failed", run_id=run_id)


def execute(run_id: str) -> None:
    """Build the run's parts in parallel, then write the receipt. Tests call this directly; the API dispatches it."""
    with _open() as conn:
        run = conn.execute(
            "SELECT idea_uuid, state, parts FROM draft_runs WHERE id = %s", (run_id,)
        ).fetchone()
        if run is None or run["state"] != "running":
            return
        idea_uuid = str(run["idea_uuid"])
        before = values(conn, idea_uuid)
        said = words(conn, idea_uuid)
        ai = ai_on(conn)
        waiting = {
            str(r["key"])
            for r in conn.execute(
                "SELECT key FROM idea_parts WHERE idea_uuid = %s AND run_id = %s AND state = 'updating'",
                (idea_uuid, run_id),
            ).fetchall()
        }  # still this run's: not settled, pinned or taken by a newer run since
        todo = [
            k for k in run["parts"] if k in waiting and (k == "similar" or (ai and k in parts.AGENT_PARTS))
        ]
        futures = [_PART_POOL.submit(_run_part, run_id, idea_uuid, k, said) for k in todo]
        _, pending = wait(futures, timeout=RUN_TIMEOUT_S)
        for f in pending:
            f.cancel()
        for k in todo:  # a part that never answered is settled, not left spinning
            _settle(conn, idea_uuid, k, run_id)
        finish(conn, run_id, before=before)


def _restored(conn: Conn, idea_uuid: str, node: Any) -> Any:
    """Tags back to the masked words they stand for: what the person typed, customer details still hidden."""
    return restore(node, vault.mapping(conn, scope(idea_uuid)), "real")


def result_of(
    key: str, data: dict[str, Any], said: list[dict[str, Any]], prior: Any
) -> tuple[Any, str | None, str | None, list[str]]:
    """(value, why, source quote, quotes) from one answer, restored first (`_restored`), so its quotes are in the
    person's masked words as `said` is and the "why" finds their sentence. `prior` keeps a pinned title or summary
    as the person left it."""
    quotes = [str(q) for q in data.get("evidence") or []]
    texts = [str(w["text"]) for w in said]
    if key == "title":
        old = prior if isinstance(prior, dict) else {}
        pinned = parts.pinned_fields(old)
        value: Any = {
            "title": old.get("title") if "title" in pinned else data.get("title"),
            "summary": old.get("summary") if "summary" in pinned else data.get("summary"),
            "pinned": sorted(pinned),
        }
        if not value["title"] and not value["summary"]:
            value = None if not pinned else value
    elif key == "value":
        value = list(data.get("worth") or [])
    else:
        value = data.get(key)
    why = parts.why_for(key, value, quotes, data.get("reason"), texts)
    return value, why, (quotes[0] if quotes else None), quotes


def _prior(conn: Conn, idea_uuid: str, key: str) -> tuple[Any, str | None]:
    """What the part shows now, and the quote it came from."""
    row = conn.execute(
        "SELECT value, source_quote FROM idea_parts WHERE idea_uuid = %s AND key = %s", (idea_uuid, key)
    ).fetchone()
    return (row["value"], row["source_quote"]) if row else (None, None)


def _run_part(run_id: str, idea_uuid: str, key: str, said: list[dict[str, Any]]) -> None:
    started = time.monotonic()
    with _open() as conn:
        state, value, why, quote, code = "keep", None, None, None, None
        try:
            if key == "similar":
                title = (values(conn, idea_uuid).get("title") or {}) or {}
                found = adapters.similar_for(
                    conn, idea_uuid, str(title.get("title") or ""), str(title.get("summary") or "")
                )
                if found is not None:
                    state, value = "filled", found[:8]
                else:
                    code = "similar_unavailable"
            else:
                inputs: dict[str, Any] = {"part": key, "words": said}
                opts = options_for(key)
                if opts is not None:
                    inputs["options"] = opts
                out = run_agent(AGENT, inputs, scope(idea_uuid), conn=conn)
                prior, prior_quote = _prior(conn, idea_uuid, key)
                value, why, quote, _ = result_of(key, _restored(conn, idea_uuid, out.data), said, prior)
                if out.dropped:
                    code = DROPPED  # the gateway's own code, on llm_calls as on this line
                texts = [str(w["text"]) for w in said]
                state = parts.landing(key, value, prior, prior_quote, texts, dropped=bool(out.dropped))
                if state == "failed" and key != "title":
                    value = None  # emptied: what it showed is no longer in the words
                if state == "failed":
                    why = quote = None
        except AgentFailed as exc:
            code = exc.code
        took = max(1, int((time.monotonic() - started) * 1000))
        landed = _write(conn, run_id, idea_uuid, key, state, value, why, quote, took, timed=code is None)
        log.info(
            "draft.part_done", run_id=run_id, part=key, state_code=state, error_code=code, latency_ms=took,
            landed=landed,
        )  # fmt: skip


def _write(
    conn: Conn, run_id: str, idea_uuid: str, key: str, state: str, value: Any, why: str | None,
    quote: str | None, took: int, *, timed: bool,
) -> bool:  # fmt: skip
    """One part's result, written only while the part is still this run's and `updating`. `keep` settles it back to
    what it showed. The run's `part_ms` (the loader's means, and the stream's "this part has landed") records the
    time of an answer that was used, 0 for a part that failed or was dropped (the means leave those out), and
    nothing for a write a newer run or the person's own change overtook (BLD-C033)."""
    with conn.transaction():
        if state == "keep":
            # Keeps a value it had; failed only when there was none.
            landed = _settle(conn, idea_uuid, key, run_id)
            if landed:
                conn.execute(
                    "UPDATE idea_parts SET took_ms = %s WHERE idea_uuid = %s AND key = %s AND run_id = %s",
                    (took, idea_uuid, key, run_id),
                )
        else:
            row_state = (
                "pinned" if key == "title" and parts.pinned_fields(value) >= {"title", "summary"} else state
            )
            landed = (
                conn.execute(
                    "UPDATE idea_parts SET state = %s, value = %s, why = %s, source_quote = %s, took_ms = %s "
                    "WHERE idea_uuid = %s AND key = %s AND run_id = %s AND state = 'updating'",
                    (row_state, Jsonb(value) if value is not None else None, why, quote, took, idea_uuid, key,
                     run_id),
                ).rowcount
                > 0
            )  # fmt: skip
        if landed:
            conn.execute(
                "UPDATE draft_runs SET part_ms = part_ms || jsonb_build_object(%s::text, %s::int) WHERE id = %s",
                (key, took if timed else 0, run_id),
            )
    return landed


# ---- finish: the receipt (L-DRAFT.parts/8) -----------------------------------------------------------------------


def ready(conn: Conn, idea_uuid: str) -> bool:
    """L-DRAFT.parts/7 and /3: title, summary and area present, the words at the minimum to check, and nothing
    still building ("Move to Review" waits for all six, C-DRAFT-LOADER.maths/8)."""
    row = conn.execute("SELECT char_count FROM ideas WHERE id = %s", (idea_uuid,)).fetchone()
    if row is None or int(row["char_count"]) < rules().min_chars_to_check:
        return False
    now = current(conn, idea_uuid)
    if any(state == "updating" for state, _ in now.values()):
        return False
    title = now.get("title", ("waiting", None))[1] or {}
    area = now.get("area", ("waiting", None))[1]
    return bool(isinstance(title, dict) and title.get("title") and title.get("summary") and area)


def finish(conn: Conn, run_id: str, *, before: dict[str, Any] | None) -> None:
    run = conn.execute(
        "SELECT r.idea_uuid, r.message_id, r.parts, i.channel, "
        "(SELECT count(*) FROM draft_runs o WHERE o.idea_uuid = r.idea_uuid AND o.started_at < r.started_at) AS earlier "
        "FROM draft_runs r JOIN ideas i ON i.id = r.idea_uuid WHERE r.id = %s",
        (run_id,),
    ).fetchone()
    if run is None:
        return
    idea_uuid = str(run["idea_uuid"])
    now = current(conn, idea_uuid)
    after = {k: v for k, (_, v) in now.items()}
    hidden = [
        str(r["masked"])
        for r in conn.execute(
            "SELECT masked FROM hidden_details WHERE source = 'message' AND source_id = %s ORDER BY span_start",
            (str(run["message_id"]),),
        ).fetchall()
    ] if run["message_id"] else []  # fmt: skip
    built = [k for k in run["parts"] if k in parts.AGENT_PARTS]
    all_failed = (
        bool(built) and ai_on(conn) and all(now.get(k, ("waiting", None))[0] == "failed" for k in built)
    )
    similar_found = 0
    if "similar" in run["parts"] and now.get("similar", ("", None))[0] == "filled":
        similar_found = len(now["similar"][1] or [])
    is_ready = ready(conn, idea_uuid)
    lines = parts.receipt(
        before if before is not None else after,
        after,
        hidden_masked=hidden,
        similar_found=similar_found,
        ready=is_ready,
        all_failed=all_failed,
        email=run["channel"] == "email" and int(run["earlier"]) == 0,
    )
    conn.execute(
        "UPDATE draft_runs SET state = 'done', receipt = %s, suggestions = %s, ready = %s, finished_at = now() "
        "WHERE id = %s AND state = 'running'",
        (Jsonb(lines), Jsonb(parts.suggestions(after)), is_ready, run_id),
    )
    log.info("draft.run_done", run_id=run_id, ready=is_ready, line_count=len(lines))
