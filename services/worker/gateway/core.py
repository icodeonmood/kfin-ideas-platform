"""`run_agent`: the one way to call a model (non-negotiable 1). The nine steps of ARCHITECTURE §3.2:

1. tag on the way out · 2. leak check · 3. untrusted-input wrapping · 4. cache · 5. rate control ·
6. call and validate (one retry with the problems) · 7. tag check · 8. return tagged (callers store tagged and
restore on view) · 9. one `llm_calls` row with counts, codes and money, never text.

Before step 1 the kill switches (`ai.all`, `agent.<name>`) and the daily budget are checked. Two switches flip
themselves (§7.6): `ai.all` after the leak check fires 3 times in an hour, and `agent.<name>` when its error
rate passes 20% over 15 minutes (with at least 10 calls, BLD-072).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from psycopg.types.json import Jsonb

from core import killswitch
from core.config import get_settings
from core.db import Conn, connect
from core.logging import get_logger
from gateway import cache, checks, limits
from gateway.pricing import cost_inr
from gateway.routes import Refused, RouteError, RouteResult, get_route
from gateway.spec import AgentSpec, load
from pii.detect import Directory, directory
from pii.patterns import scan
from pii.tagger import Tagged, tag_payload, tags_in
from pii.vault import EVAL_SCOPE_LIKE

log = get_logger("gateway")
ACTOR = "process:gateway"
LEAK_WINDOW = "1 hour"
ERROR_WINDOW = "15 minutes"
ERROR_MIN_CALLS = 10


class AgentFailed(Exception):
    """The caller takes its fallback path. `code` is safe to log and store."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class AgentSwitchedOff(AgentFailed):
    pass


class LeakAbort(AgentFailed):
    pass


class RateLimited(AgentFailed):
    pass


@dataclass
class ValidatedOutput:
    agent: str
    version: str
    data: dict[str, Any]  # tagged; store as is, restore on view
    tags_sent: dict[str, str]
    outcome: str
    flags: list[str] = field(default_factory=list)
    latency_ms: int = 0
    sent: dict[str, Any] = field(
        default_factory=dict
    )  # the tagged inputs the model saw (for evals and checks)
    dropped: list[str] = field(
        default_factory=list
    )  # field paths the gateway removed after the re-ask (DEC-095); paths only, never text


# ---- helpers -----------------------------------------------------------------------------------------------


def _strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in _strings(v)]
    if isinstance(node, list):
        return [s for v in node for s in _strings(v)]
    return []


def _defuse_tags(node: Any, tags: set[str]) -> Any:
    if isinstance(node, str):
        for t in tags:
            node = node.replace(t, t.replace("[[", "[ [").replace("]]", "] ]"))
        return node
    if isinstance(node, list):
        return [_defuse_tags(x, tags) for x in node]
    if isinstance(node, dict):
        return {k: _defuse_tags(v, tags) for k, v in node.items()}
    return node


def leak_hits(payload: Any) -> list[str]:
    """Pattern ids still present after tagging. Any hit means detection missed something."""
    return sorted({m.pattern_id for text in _strings(payload) for m in scan(text, kfin_domains=[])})


def _escape_blocks(text: str, names: tuple[str, ...]) -> str:
    """Untrusted text cannot open or close one of our blocks."""
    if not names:
        return text
    rx = re.compile(r"<(\s*/?\s*)(" + "|".join(re.escape(n) for n in names) + r")\b", re.I)
    return rx.sub(lambda m: "&lt;" + m.group(1) + m.group(2), text)


def render_blocks(spec: AgentSpec, payload: dict[str, Any]) -> str:
    names = tuple(dict.fromkeys((*spec.input_blocks, *payload.keys())))
    parts = []
    for name in names:
        if name not in payload:
            continue
        value = payload[name]
        body = (
            value
            if isinstance(value, str)
            else json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1)
        )
        if name in spec.untrusted_blocks:
            body = _escape_blocks(body, names)
        parts.append(f"<{name}>\n{body}\n</{name}>")
    return "\n\n".join(parts)


def system_prompt(spec: AgentSpec) -> str:
    parts = [spec.prompt.strip()]
    chosen = [spec.example(n) for n in spec.prompt_examples]
    if chosen:
        parts.append("## Worked examples (synthetic)")
        for ex in chosen:
            parts.append(
                f"### {ex.description}\n\nInput:\n{render_blocks(spec, ex.input)}\n\n"
                f"Output:\n{json.dumps(ex.output, ensure_ascii=False, indent=1)}"
            )
    return "\n\n".join(parts)


def _validator(spec: AgentSpec) -> Draft202012Validator:
    return Draft202012Validator(spec.schema)


def _schema_problems(spec: AgentSpec, data: Any) -> list[str]:
    out = []
    for err in sorted(_validator(spec).iter_errors(data), key=lambda e: list(e.absolute_path))[:10]:
        where = ".".join(str(p) for p in err.absolute_path) or "(root)"
        out.append(f"{where}: fails '{err.validator}'")  # never the offending value
    return out


def _record(conn: Conn, spec: AgentSpec, **row: Any) -> None:
    conn.execute(
        "INSERT INTO llm_calls (agent, prompt_version, model, input_tokens, output_tokens, latency_ms, cost_inr, "
        "tags_by_type, outcome, ref_id, cache_read_tokens, error_code) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            spec.name,
            spec.version,
            row.get("model") or "none",
            row.get("input_tokens"),
            row.get("output_tokens"),
            row.get("latency_ms"),
            row.get("cost_inr"),
            Jsonb(row.get("tags_by_type") or {}),
            row["outcome"],
            row.get("ref_id"),
            row.get("cache_read_tokens"),
            row.get("error_code"),
        ),
    )
    log.info(
        "gateway.call",
        agent=spec.name,
        agent_version=spec.version,
        outcome=row["outcome"],
        error_code=row.get("error_code"),
        latency_ms=row.get("latency_ms"),
        ref_id=row.get("ref_id"),
    )


def _thresholds() -> dict[str, Any]:
    from rules import load_rule

    try:
        data = load_rule(get_settings().company_repo_path, "thresholds").data
        return dict(data.get("kill_switch_triggers") or {})
    except Exception:
        return {}


def _alert(conn: Conn, action: str, entity: str, detail: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, %s, %s, %s)",
        (ACTOR, action, entity, Jsonb(detail)),
    )
    log.error("gateway.alert", alert=action, entity=entity)


def _maybe_switch_off(conn: Conn, name: str, reason: str) -> None:
    killswitch.clear_cache()
    if killswitch.is_on(name, conn):
        killswitch.set_switch(conn, name, "off", reason=reason, actor=ACTOR)
        killswitch.clear_cache()
        _alert(conn, "alert.kill_switch_auto", f"kill_switch:{name}", {"state": "off"})


def _after_leak(conn: Conn) -> None:
    # Every live call counts, live drafts included; only golden-set runs (the eval marker) do not (BLD-C034).
    limit = int(_thresholds().get("leak_hits_per_hour_for_ai_all", 3))
    n = conn.execute(
        "SELECT count(DISTINCT ref_id) AS n FROM llm_calls WHERE outcome = 'leak_abort' "
        "AND ref_id NOT LIKE %s AND created_at > now() - %s::interval",
        (EVAL_SCOPE_LIKE, LEAK_WINDOW),
    ).fetchone()
    if n and int(n["n"]) >= limit:
        _maybe_switch_off(conn, "ai.all", f"Automatic: the leak check fired {limit} times within an hour")


def _after_error(conn: Conn, spec: AgentSpec) -> None:
    rate = float(_thresholds().get("agent_error_rate_15min", 0.2))
    row = conn.execute(
        "SELECT count(*) AS total, count(*) FILTER (WHERE outcome IN ('agent_failed', 'route_error')) AS failed "
        "FROM llm_calls WHERE agent = %s AND outcome <> 'switched_off' AND coalesce(ref_id, '') NOT LIKE %s "
        "AND created_at > now() - %s::interval",
        (spec.name, EVAL_SCOPE_LIKE, ERROR_WINDOW),
    ).fetchone()
    if row and int(row["total"]) >= ERROR_MIN_CALLS and int(row["failed"]) / int(row["total"]) > rate:
        _maybe_switch_off(
            conn, f"agent.{spec.name}", f"Automatic: error rate above {int(rate * 100)}% over 15 minutes"
        )


def _spent_today(conn: Conn) -> float:
    row = conn.execute(
        "SELECT coalesce(sum(cost_inr), 0) AS spent FROM llm_calls "
        "WHERE created_at >= (date_trunc('day', now() AT TIME ZONE 'Asia/Kolkata') AT TIME ZONE 'Asia/Kolkata')"
    ).fetchone()
    return float(row["spent"]) if row else 0.0


# ---- run_agent ---------------------------------------------------------------------------------------------


def run_agent(
    name: str,
    inputs: dict[str, Any],
    ref_id: str,
    *,
    conn: Conn | None = None,
    agents_dir: Path | None = None,
    wait_s: float = 2.0,
    d: Directory | None = None,
    use_cache: bool = True,
) -> ValidatedOutput:
    """Run one agent on `inputs` (real values) for the idea or cluster `ref_id`. Returns tagged output.
    `use_cache=False` is for the eval runner, which measures the model, not the cache."""
    own = conn is None
    c = conn or connect(autocommit=True)
    try:
        return _run(c, load(name, agents_dir), inputs, ref_id, wait_s, d, use_cache)
    finally:
        if own:
            c.close()


def _run(
    conn: Conn,
    spec: AgentSpec,
    inputs: dict[str, Any],
    ref_id: str,
    wait_s: float,
    d: Directory | None,
    use_cache: bool = True,
) -> ValidatedOutput:
    started = time.monotonic()
    unknown = set(inputs) - set(spec.input_blocks)
    if unknown:
        raise AgentFailed("unknown_input_block")

    # Kill switches and the daily budget, before any text is touched.
    if not (killswitch.is_on("ai.all", conn) and killswitch.is_on(f"agent.{spec.name}", conn)):
        _record(conn, spec, outcome="switched_off", ref_id=ref_id, error_code="kill_switch")
        raise AgentSwitchedOff("switched_off")
    if _spent_today(conn) >= get_settings().llm_daily_budget_inr:
        _record(conn, spec, outcome="switched_off", ref_id=ref_id, error_code="daily_budget")
        recent = conn.execute(
            "SELECT 1 FROM audit_log WHERE action = 'alert.llm_budget' AND at > now() - interval '1 hour' LIMIT 1"
        ).fetchone()
        if recent is None:  # one alert an hour, not one per refused call
            _alert(conn, "alert.llm_budget", "gateway", {"budget": "daily"})
        raise AgentSwitchedOff("daily_budget")

    # 1. Tag. 2. Leak check.
    d = d or directory(conn)
    tagged: Tagged = tag_payload(conn, ref_id, inputs, d=d)
    hits = leak_hits(tagged.payload)
    if hits:
        _record(
            conn, spec, outcome="leak_abort", ref_id=ref_id, error_code=hits[0], tags_by_type=tagged.counts()
        )
        _alert(conn, "alert.leak_check", f"agent:{spec.name}", {"patterns": hits, "ref_id": ref_id})
        _after_leak(conn)
        raise LeakAbort("leak_check")

    # 3. Wrap. 4. Cache.
    route = get_route()
    model = spec.model
    k = cache.key(spec, model, tagged.payload)
    hit = cache.get(conn, k) if use_cache else None
    if hit is not None:
        latency = int((time.monotonic() - started) * 1000)
        _record(
            conn, spec, outcome="cached", ref_id=ref_id, latency_ms=latency, model=model,
            tags_by_type=tagged.counts(), input_tokens=0, output_tokens=0, cost_inr=0,
        )  # fmt: skip
        return ValidatedOutput(
            spec.name, spec.version, hit, tagged.tags, "cached", [], latency, tagged.payload
        )
    system = system_prompt(spec)
    messages: list[dict[str, Any]] = [{"role": "user", "content": render_blocks(spec, tagged.payload)}]

    # 5. Rate control. 6. Call and validate, retrying once with the problems.
    totals = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
    result: RouteResult | None = None
    data: Any = None
    problems: list[str] = []
    attempts = 0
    try:
        with limits.limiter().slot(spec.tier, wait_s):
            for attempt in range(1 + spec.retries_on_invalid):
                attempts = attempt + 1
                result = route.call(spec, system, messages, tagged.payload)
                totals["input"] += result.input_tokens
                totals["output"] += result.output_tokens
                totals["cache_write"] += result.cache_write_tokens
                totals["cache_read"] += result.cache_read_tokens
                try:
                    data = json.loads(result.text)
                    problems = _schema_problems(spec, data)
                except json.JSONDecodeError:
                    data, problems = None, ["the output is not valid JSON"]
                if result.stop_reason == "max_tokens":
                    problems = ["the output was cut off; return a shorter JSON object", *problems]
                if not problems:
                    problems = checks.run(spec.name, tagged.payload, data, d)
                if not problems and leak_hits(data):
                    problems = [
                        "the output contains a value that looks like an identifier; use the tags or leave it out"
                    ]
                if not problems:
                    break
                messages = [
                    *messages,
                    {"role": "assistant", "content": result.text or "{}"},
                    {
                        "role": "user",
                        "content": "That output did not pass validation:\n- "
                        + "\n- ".join(problems)
                        + "\nReturn the corrected JSON object only.",
                    },
                ]
    except limits.Saturated:
        _record(conn, spec, outcome="route_error", ref_id=ref_id, error_code="rate_limited")
        raise RateLimited("rate_limited") from None
    except Refused:
        latency = int((time.monotonic() - started) * 1000)
        _record(conn, spec, outcome="agent_failed", ref_id=ref_id, error_code="refusal", latency_ms=latency)
        _after_error(conn, spec)
        raise AgentFailed("refusal") from None
    except RouteError as exc:
        latency = int((time.monotonic() - started) * 1000)
        _record(conn, spec, outcome="route_error", ref_id=ref_id, error_code=exc.code, latency_ms=latency)
        _after_error(conn, spec)
        raise AgentFailed(exc.code) from None

    latency = int((time.monotonic() - started) * 1000)
    assert result is not None
    money = cost_inr(
        result.model, totals["input"], totals["output"], totals["cache_write"], totals["cache_read"]
    )
    common = {
        "ref_id": ref_id, "latency_ms": latency, "model": result.model, "input_tokens": totals["input"],
        "output_tokens": totals["output"], "cost_inr": money, "cache_read_tokens": totals["cache_read"],
        "tags_by_type": tagged.counts(),
    }  # fmt: skip
    # After the one re-ask, an agent with a repair (canvas-assist, DEC-095) drops just the suggestions it could not
    # back with the person's own words. The mended output must then pass every check, or the call fails as before.
    dropped_paths: list[str] = []
    mended = _repaired(spec, tagged.payload, data, problems, d)
    if mended is not None:
        data, dropped_paths = mended
        problems = []
    if problems:
        _record(conn, spec, outcome="agent_failed", error_code="invalid_output", **common)
        _after_error(conn, spec)
        raise AgentFailed("invalid_output")

    # 7. Tag check: only tags that were sent may come back. Others are flagged and defused, so a tag the model
    # invented can never be restored, even if the idea's vault happens to hold that number (BLD-081).
    flags: list[str] = []
    unknown = tags_in(data) - set(tagged.tags)
    if unknown:
        flags.append("unknown_tags")
        data = _defuse_tags(data, unknown)
    outcome = "tag_mismatch" if flags else ("ok" if attempts == 1 else "ok_after_retry")
    if not flags and mended is None and use_cache:  # a mended answer is not cached: the next ask tries again
        cache.put(conn, k, spec, data)
    # 9. Log. Dropped suggestions are counted by code only; the field paths stay with the caller.
    code = flags[0] if flags else (DROPPED if dropped_paths else None)
    _record(conn, spec, outcome=outcome, error_code=code, **common)
    # 8. Tagged output back to the caller, which stores it tagged and restores on view.
    return ValidatedOutput(
        spec.name, spec.version, data, tagged.tags, outcome, flags, latency, tagged.payload, dropped_paths
    )


DROPPED = "ungrounded_dropped"


def _repaired(
    spec: AgentSpec, sent: dict[str, Any], data: Any, problems: list[str], d: Directory | None
) -> tuple[dict[str, Any], list[str]] | None:
    """The mended output and the dropped paths, or None when there is nothing to mend or mending is not enough."""
    if not problems or not isinstance(data, dict) or _schema_problems(spec, data):
        return None
    mended = checks.repair(spec.name, sent, data)
    if mended is None or mended[0] is data:  # nothing changed: nothing to mend
        return None
    fixed, paths = mended  # paths may be empty: corrected assumption words drop nothing (BLD-C048)
    if _schema_problems(spec, fixed) or checks.run(spec.name, sent, fixed, d) or leak_hits(fixed):
        return None
    return fixed, paths
