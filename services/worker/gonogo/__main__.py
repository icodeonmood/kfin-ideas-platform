"""Go/no-go report against §9.3 (AT-B8 evidence). Reads what the platform can check for itself and lists what
people must confirm, then names the launch mode the evidence supports.

    uv run python -m gonogo [--since 2026-11-16] [--vapt-open-high N] [--sso-ready yes|no] [--out FILE]

Sources: the latest golden-set reports (EVAL_REPORTS_DIR, else `eval/reports/`), `llm_calls` leak aborts since --since, the latest load
test report (`.data/loadtest/`), the latest restore drill (`.data/ops/`), the privacy notice version, kill
switches and reconcile drift. Numbers and states only; no idea text.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.config import REPO_ROOT, get_settings
from core.db import connect
from core.speech_route import hosted_problem, key_set, voice_problem
from core.watch import SARVAM_KEY_MISSING

ROOT = REPO_ROOT or Path.cwd()  # in the worker container there is no repo root: /app


class Unreadable(Exception):
    pass


def _latest(folder: Path, pattern: str) -> dict[str, Any] | None:
    files = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime)
    if not files:
        return None
    try:
        data = json.loads(files[-1].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Unreadable(files[-1].name) from None
    if not isinstance(data, dict):
        raise Unreadable(files[-1].name)
    return data


# Switches that start off on purpose: the report shows them as expected, not as a problem, so nobody "fixes" them
# on. Voice left this list with DEC-108 (on at launch through Sarvam). The channels built and switched off until
# IT or InfoSec approve them (DEC-105: Teams, email intake, email-code sign-in) join it as their switches land.
OFF_BY_DESIGN: dict[str, str] = {
    # Migration 20261122100100 (BLD-E002): the email-code route of sign-in waits for InfoSec.
    "auth.email_code": "Off until InfoSec approves sign-in by email code (BLD-E002, DEC-105)",
    # Matches its reason in migration 20261122300100 (lane C, BLD-C064).
    "files.blackout": "Off until black-out passes review (DEC-107)",
}

VOICE = "Voice: on at launch through Sarvam, or the on-server engine behind the isolated service (DEC-108)"
HOSTED = "Hosted speech (Sarvam): switch, approval reference and key match the route (DEC-108)"


def _row(name: str, state: str, evidence: str) -> dict[str, str]:
    return {"criterion": name, "state": state, "evidence": evidence}


def voice_rows(
    voice_on: bool,
    hosted_on: bool,
    speech_mode: str,
    engine_url: str,
    approval: str,
    key: bool,
    *,
    voice_reason: str | None = None,
    hosted_reason: str | None = None,
) -> tuple[list[dict[str, str]], list[str]]:
    """DEC-108: voice is on at launch through Sarvam (speech to text and Listen; India-hosted, no retention). The
    on-server engine behind the isolated speech service (BLD-C012) stays an allowed fallback; the fake route never
    is. Off is a row for the product lead to confirm, not "off as expected". The route rules are shared with the
    smoke check (`core.speech_route`). Returns the rows and any reasons that rule out Mode A."""
    rows: list[dict[str, str]] = []
    reasons: list[str] = []
    problem = voice_problem(voice_on, hosted_on, speech_mode, engine_url, approval, key)
    if not voice_on and voice_reason == SARVAM_KEY_MISSING:  # the watch's key guard flipped it (BLD-C115)
        rows.append(_row(VOICE, "not met", f"off: {SARVAM_KEY_MISSING}"))
        reasons.append("voice switched off by the watch: the Sarvam key is missing")
    elif not voice_on:
        evidence = (
            "off: DEC-108 plans voice on at launch; switch it on, or launch without it (typing still works)"
        )
        rows.append(_row(VOICE, "confirm", evidence))
    elif problem:
        rows.append(_row(VOICE, "not met", problem))
        reasons.append("voice on without a working route")
    elif speech_mode == "sarvam":
        rows.append(
            _row(VOICE, "met", "on; SPEECH_MODE sarvam, speech.hosted on, approval reference and key set")
        )
    else:
        rows.append(
            _row(VOICE, "met", "on; SPEECH_MODE local through the isolated speech service (BLD-C012)")
        )
    hosted = hosted_problem(hosted_on, approval, key)
    if not hosted_on and hosted_reason == SARVAM_KEY_MISSING:
        rows.append(_row(HOSTED, "not met", f"off: {SARVAM_KEY_MISSING}"))
        reasons.append("hosted speech switched off by the watch: the Sarvam key is missing")
    elif hosted:
        rows.append(_row(HOSTED, "not met", hosted))
        reasons.append("hosted speech on without its approval reference or key")
    elif hosted_on:
        rows.append(_row(HOSTED, "met", "on with an approval reference and the key set (DEC-108)"))
    elif speech_mode == "sarvam":
        rows.append(
            _row(HOSTED, "confirm", "off while SPEECH_MODE is sarvam: switch it on with voice (DEC-108)")
        )
    else:
        rows.append(_row(HOSTED, "met", f"off; SPEECH_MODE {speech_mode or 'unset'} does not use it"))
    return rows, reasons


def collect(args: argparse.Namespace) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    reasons_b: list[str] = []
    reasons_c: list[str] = []

    rows.append(_row("Every B1–B7 acceptance test passes in UAT", "confirm", "CI report from the UAT run"))

    def section(name: str, check: Any) -> None:
        """One criterion; an odd or unreadable report makes it a 'confirm' row instead of a crash."""
        try:
            check()
        except (Unreadable, KeyError, TypeError, ValueError) as exc:
            rows.append(_row(name, "confirm", f"report unreadable ({type(exc).__name__})"))

    def gatekeeper() -> None:
        gk = _latest(args.reports_dir, "gatekeeper-*.json")
        name = "Gatekeeper: personal-data recall 100%, false blocks under 5%"
        if gk is None or gk.get("route") == "fake":
            rows.append(
                _row(name, "not met", "no real-route golden-set run yet (model route not approved, D1)")
            )
            reasons_b.append("no real-route golden-set run")
            return
        m = gk["metrics"]
        ok = m["personal_data_recall"] >= 1.0 and m["false_block_rate"] < 0.05
        rows.append(_row(name, "met" if ok else "not met", f"{gk['version']} on {gk['route']}: recall "
                         f"{m['personal_data_recall']:.0%}, false blocks {m['false_block_rate']:.1%}"))  # fmt: skip
        if not ok:
            reasons_b.append("gatekeeper golden set below target")

    def judge() -> None:
        jd = _latest(args.reports_dir, "judge-*.json")
        name = 'Judge: "same" precision at least 0.85'
        if jd is None or jd.get("route") == "fake":
            rows.append(_row(name, "not met", "no real-route golden-set run yet"))
            reasons_b.append("no real-route judge run")
            return
        p = jd["metrics"].get("same_precision")
        ok = p is not None and p >= 0.85
        rows.append(
            _row(name, "met" if ok else "not met", f"{jd['version']} on {jd['route']}: precision {p}")
        )
        if not ok:
            reasons_b.append("judge golden set below target")

    def leaks_and_switches() -> None:
        with connect(autocommit=True) as conn:
            leaks = conn.execute(
                "SELECT count(*) AS n FROM llm_calls WHERE outcome = 'leak_abort' AND created_at >= %s "
                "AND ref_id NOT LIKE 'DRAFT-%%'",  # golden-set runs use DRAFT- scopes, as the gateway's own count
                (args.since,),
            ).fetchone()
            switches_off.extend(
                r["name"]
                for r in conn.execute("SELECT name FROM kill_switches WHERE state = 'off' ORDER BY name")
            )
        n = int(leaks["n"]) if leaks else 0
        rows.append(_row("Zero leak-check hits across UAT", "met" if n == 0 else "not met",
                         f"{n} leak aborts in llm_calls since {args.since}"))  # fmt: skip
        if n:
            reasons_b.append("leak-check hits in UAT")

    def load_test() -> None:
        load = _latest(args.loadtest_dir, "report-*.json")
        name = "Scan time p95 under 15 s at 150 submissions an hour"
        if load is None:
            rows.append(_row(name, "confirm", "no load test report"))
            return
        st = load["settings"]
        full = st["scale"] >= 1.0 and st["submissions_per_hour"] >= 150 and st["sign_ins"] >= 3000
        scan = (load.get("scan") or {}).get("p95_s")
        ok = full and all(load["pass"].values())
        where = "the full hour at launch rates" if full else f"a rehearsal (scale {st['scale']})"
        detail = (
            "no scans measured"
            if scan is None
            else f"p95 {scan:.1f} s, operation error rate {load['error_rate']:.2%}"
        )
        rows.append(_row(name, "met" if ok else "not met", f"{detail}; {where} against {st['base_url']}"))
        if not ok:
            reasons_b.append("load test not passed at launch rates")

    def vapt() -> None:
        name = "No open high or critical VAPT findings"
        if args.vapt_open_high is None:
            rows.append(_row(name, "confirm", "InfoSec"))
            return
        ok = args.vapt_open_high == 0
        rows.append(_row(name, "met" if ok else "not met", f"{args.vapt_open_high} open (InfoSec)"))
        if not ok:
            reasons_c.append("VAPT high findings open")

    def drill() -> None:
        d = _latest(args.drill_dir, "restore-drill-*.json")
        name = "Restore drill completed inside 4 hours"
        if d is None:
            rows.append(_row(name, "confirm", "IT, in UAT"))
            return
        ok = bool(d["passed"]) and int(d["seconds"]) < 4 * 3600
        rows.append(
            _row(
                name,
                "met" if ok else "not met",
                f"{int(d['seconds']) // 60} min on {d['where']} at {d['at']}",
            )
        )
        if not ok:
            reasons_c.append("restore drill not passed")

    def privacy_and_sso() -> None:
        version = get_settings().privacy_notice_version
        live = not version.endswith("draft")
        rows.append(
            _row("Privacy notice live", "met" if live else "not met", f"version {version} (Legal / DPO)")
        )
        if not live:
            reasons_c.append("privacy notice still a draft")
        name = "SSO and environments ready"
        if args.sso_ready is None:
            rows.append(_row(name, "confirm", "IT"))
        else:
            rows.append(_row(name, "met" if args.sso_ready == "yes" else "not met", "IT"))
            if args.sso_ready == "no":
                reasons_c.append("SSO or environments not ready")

    def voice_notes() -> None:
        """DEC-108: voice on at launch through Sarvam; see voice_rows."""
        s = get_settings()
        with connect(autocommit=True) as conn:
            found = conn.execute(
                "SELECT name, state, reason FROM kill_switches WHERE name IN ('capture.voice', 'speech.hosted')"
            ).fetchall()
        states = {r["name"]: r["state"] for r in found}
        reasons = {r["name"]: r["reason"] for r in found}
        got, why = voice_rows(
            states.get("capture.voice") == "on",
            states.get("speech.hosted") == "on",
            s.speech_mode,
            s.speech_engine_url,
            s.speech_hosted_approval,
            key_set(s),
            voice_reason=reasons.get("capture.voice"),
            hosted_reason=reasons.get("speech.hosted"),
        )
        rows.extend(got)
        reasons_b.extend(why)

    switches_off: list[str] = []
    section("Gatekeeper: personal-data recall 100%, false blocks under 5%", gatekeeper)
    section('Judge: "same" precision at least 0.85', judge)
    section("Zero leak-check hits across UAT", leaks_and_switches)
    section("Scan time p95 under 15 s at 150 submissions an hour", load_test)
    section("No open high or critical VAPT findings", vapt)
    section("Restore drill completed inside 4 hours", drill)
    section("Privacy notice live", privacy_and_sso)
    section(VOICE, voice_notes)

    try:
        assist = canvas_assist_shares(args)
    except Exception as exc:  # the report still prints; this block says it could not read the calls
        assist = [{"window": "canvas-assist calls", "error": type(exc).__name__}]

    mode = "C. Preview" if reasons_c else "B. Capture first" if reasons_b else "A. Full"
    if mode == "A. Full" and any(r["state"] == "not met" for r in rows):
        mode = "B. Capture first"  # no Mode A while any criterion is not met (B8 review)
        reasons_b.extend(r["criterion"] + " not met" for r in rows if r["state"] == "not met")
    elif mode == "A. Full" and any(r["state"] != "met" for r in rows):
        mode = "A. Full, once every 'confirm' row is confirmed"
    return {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rows": rows,
        "mode": mode,
        "why": reasons_c or reasons_b,
        "switches_off": switches_off,
        "canvas_assist": assist,
    }


def canvas_assist_shares(args: argparse.Namespace) -> list[dict[str, Any]]:
    """How often the gateway dropped canvas-assist suggestions the person's words did not back
    (`ungrounded_dropped`) and refused its answer outright (`invalid_output`), over the last 24 hours, since launch
    (live calls) and in golden-set runs since --since (DRAFT- scopes, as the gateway's own counts tell them apart).
    A high invalid share would trip the automatic switch-off (20% of calls over 15 minutes, BLD-072). Counts only."""
    windows = [
        ("last 24 hours", "now() - interval '24 hours'", False),
        (f"since launch ({args.launch})", "%(launch)s::date", False),
        (f"golden-set runs since {args.since}", "%(since)s::date", True),
    ]
    out = []
    with connect(autocommit=True) as conn:
        for label, start, eval_runs in windows:
            row = conn.execute(
                "SELECT count(*) FILTER (WHERE outcome NOT IN ('switched_off', 'cached')) AS asked, "  # noqa: S608
                "count(*) FILTER (WHERE error_code = 'ungrounded_dropped') AS dropped, "
                "count(*) FILTER (WHERE error_code = 'invalid_output') AS invalid "
                f"FROM llm_calls WHERE agent = 'canvas-assist' AND created_at >= {start} "
                "AND (coalesce(ref_id, '') LIKE 'DRAFT-%%') = %(eval_runs)s",
                {"launch": args.launch, "since": args.since, "eval_runs": eval_runs},
            ).fetchone()
            assert row is not None  # an aggregate always returns a row
            out.append(
                {"window": label, "asked": int(row["asked"]), "dropped": int(row["dropped"]),
                 "invalid": int(row["invalid"])}
            )  # fmt: skip
    return out


def _share(part: int, whole: int) -> str:
    return f"{part} of {whole} ({part / whole:.0%})" if whole else "0 of 0"


def render(r: dict[str, Any]) -> str:
    lines = [
        f"# Go/no-go evidence ({r['at']})",
        "",
        "| Criterion (§9.3) | State | Evidence |",
        "|---|---|---|",
    ]
    lines += [f"| {x['criterion']} | {x['state']} | {x['evidence']} |" for x in r["rows"]]
    lines += ["", f"**Mode the evidence supports:** {r['mode']}"]
    if r["why"]:
        lines.append(f"**Because:** {'; '.join(r['why'])}.")
    by_design = [n for n in r["switches_off"] if n in OFF_BY_DESIGN]
    other = [n for n in r["switches_off"] if n not in OFF_BY_DESIGN]
    lines.append(f"**Switches off now:** {', '.join(other) or 'none'}.")
    if by_design:  # off on purpose until their approvals land; do not switch on
        lines.append(f"**Off as expected (by design):** {', '.join(by_design)}.")
    lines += [
        "",
        "**canvas-assist answers (DEC-095, DEC-097):** check on the first real-route golden-set run and before launch;",
        "the automatic switch-off acts when failed calls pass 20% over 15 minutes.",
        "",
        "| Window | Answers | Suggestions dropped (`ungrounded_dropped`) | Refused (`invalid_output`) |",
        "|---|---|---|---|",
    ]
    for w in r.get("canvas_assist") or []:
        if "error" in w:
            lines.append(f"| {w['window']} | could not read ({w['error']}) | | |")
        else:
            lines.append(
                f"| {w['window']} | {w['asked']} | {_share(w['dropped'], w['asked'])} | "
                f"{_share(w['invalid'], w['asked'])} |"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--since", default="2026-11-16", help="start of the UAT period (YYYY-MM-DD)")
    parser.add_argument("--launch", default="2026-11-20", help="launch day, for live canvas-assist shares")
    parser.add_argument("--vapt-open-high", type=int)
    parser.add_argument("--sso-ready", choices=("yes", "no"))
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--reports-dir", type=Path, default=None, help="golden-set reports (default: EVAL_REPORTS_DIR)"
    )
    parser.add_argument("--loadtest-dir", type=Path, default=ROOT / ".data" / "loadtest")
    parser.add_argument("--drill-dir", type=Path, default=ROOT / ".data" / "ops")
    args = parser.parse_args()
    if args.reports_dir is None:  # the same place the eval runner writes to
        args.reports_dir = Path(os.environ.get("EVAL_REPORTS_DIR") or ROOT / "eval" / "reports")
    text = render(collect(args))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
