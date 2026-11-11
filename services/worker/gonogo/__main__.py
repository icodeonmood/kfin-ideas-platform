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


def _row(name: str, state: str, evidence: str) -> dict[str, str]:
    return {"criterion": name, "state": state, "evidence": evidence}


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
        """DEC-096: voice notes may launch off (paused with their reason); on, only with the engine on KFin's own
        server. The watch switches them off by itself if the fake speech route is set outside dev and test."""
        s = get_settings()
        with connect(autocommit=True) as conn:
            row = conn.execute(
                "SELECT state, reason FROM kill_switches WHERE name = 'capture.voice'"
            ).fetchone()
        on = row is not None and row["state"] == "on"
        name = "Voice notes: off, or on with the engine on KFin's own server (DEC-096)"
        if not on:
            rows.append(
                _row(name, "met", "off: paused with its reason; the screen says voice notes are coming")
            )
        elif s.speech_mode == "local" and s.speech_model_path:
            rows.append(
                _row(name, "met", "on; SPEECH_MODE local with a model path (IT, InfoSec and DPO cleared)")
            )
        else:
            rows.append(
                _row(name, "not met", f"on with SPEECH_MODE {s.speech_mode}; switch it off or fix the route")
            )
            reasons_b.append("voice notes on without the engine on KFin's own server")

    switches_off: list[str] = []
    section("Gatekeeper: personal-data recall 100%, false blocks under 5%", gatekeeper)
    section('Judge: "same" precision at least 0.85', judge)
    section("Zero leak-check hits across UAT", leaks_and_switches)
    section("Scan time p95 under 15 s at 150 submissions an hour", load_test)
    section("No open high or critical VAPT findings", vapt)
    section("Restore drill completed inside 4 hours", drill)
    section("Privacy notice live", privacy_and_sso)
    section("Voice notes: off, or on with the engine on KFin's own server (DEC-096)", voice_notes)

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
    }


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
    lines.append(f"**Switches off now:** {', '.join(r['switches_off']) or 'none'}.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--since", default="2026-11-16", help="start of the UAT period (YYYY-MM-DD)")
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
