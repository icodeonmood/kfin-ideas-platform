"""Go/no-go report against §9.3 (AT-B8 evidence). Reads what the platform can check for itself and lists what
people must confirm, then names the launch mode the evidence supports.

    uv run python -m gonogo [--since 2026-11-16] [--vapt-open-high N] [--sso-ready yes|no] [--out FILE]

Sources: the latest golden-set reports (`eval/reports/`), `llm_calls` leak aborts since --since, the latest load
test report (`.data/loadtest/`), the latest restore drill (`.data/ops/`), the privacy notice version, kill
switches and reconcile drift. Numbers and states only; no idea text.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.config import REPO_ROOT, get_settings
from core.db import connect

ROOT = REPO_ROOT or Path.cwd().parents[1]


def _latest(folder: Path, pattern: str) -> dict[str, Any] | None:
    files = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime)
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def _row(name: str, state: str, evidence: str) -> dict[str, str]:
    return {"criterion": name, "state": state, "evidence": evidence}


def collect(args: argparse.Namespace) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    reasons_b: list[str] = []
    reasons_c: list[str] = []

    rows.append(_row("Every B1–B7 acceptance test passes in UAT", "confirm", "CI report from the UAT run"))

    gk = _latest(ROOT / "eval" / "reports", "gatekeeper-*.json")
    if gk is None or gk.get("route") == "fake":
        rows.append(_row("Gatekeeper: personal-data recall 100%, false blocks under 5%", "not met",
                         "no real-route golden-set run yet (model route not approved, D1)"))  # fmt: skip
        reasons_b.append("no real-route golden-set run")
    else:
        m = gk["metrics"]
        ok = m["personal_data_recall"] >= 1.0 and m["false_block_rate"] < 0.05
        rows.append(_row("Gatekeeper: personal-data recall 100%, false blocks under 5%", "met" if ok else "not met",
                         f"{gk['version']} on {gk['route']}: recall {m['personal_data_recall']:.0%}, "
                         f"false blocks {m['false_block_rate']:.1%}"))  # fmt: skip
        if not ok:
            reasons_b.append("gatekeeper golden set below target")

    jd = _latest(ROOT / "eval" / "reports", "judge-*.json")
    if jd is None or jd.get("route") == "fake":
        rows.append(
            _row('Judge: "same" precision at least 0.85', "not met", "no real-route golden-set run yet")
        )
        reasons_b.append("no real-route judge run")
    else:
        p = jd["metrics"].get("same_precision")
        ok = p is not None and p >= 0.85
        rows.append(_row('Judge: "same" precision at least 0.85', "met" if ok else "not met",
                         f"{jd['version']} on {jd['route']}: precision {p}"))  # fmt: skip
        if not ok:
            reasons_b.append("judge golden set below target")

    with connect(autocommit=True) as conn:
        leaks = conn.execute(
            "SELECT count(*) AS n FROM llm_calls WHERE outcome = 'leak_abort' AND created_at >= %s",
            (args.since,),
        ).fetchone()
        switches = conn.execute("SELECT name, state FROM kill_switches ORDER BY name").fetchall()
    n = int(leaks["n"]) if leaks else 0
    rows.append(_row("Zero leak-check hits across UAT", "met" if n == 0 else "not met",
                     f"{n} leak aborts in llm_calls since {args.since}"))  # fmt: skip
    if n:
        reasons_b.append("leak-check hits in UAT")

    load = _latest(ROOT / ".data" / "loadtest", "report-*.json")
    if load is None:
        rows.append(
            _row("Scan time p95 under 15 s at 150 submissions an hour", "confirm", "no load test report")
        )
    else:
        full = load["settings"]["scale"] >= 1.0
        scan = (load.get("scan") or {}).get("p95_s")
        ok = bool(load["pass"]["scan_p95"]) and full
        rows.append(_row("Scan time p95 under 15 s at 150 submissions an hour", "met" if ok else "not met",
                         f"p95 {scan:.1f} s, error rate {load['error_rate']:.2%}, "
                         f"{'full hour' if full else f'rehearsal at scale {load['settings']['scale']}'} "
                         f"against {load['settings']['base_url']}" if scan is not None else "no scans measured"))  # fmt: skip

    if args.vapt_open_high is None:
        rows.append(_row("No open high or critical VAPT findings", "confirm", "InfoSec"))
    else:
        ok = args.vapt_open_high == 0
        rows.append(_row("No open high or critical VAPT findings", "met" if ok else "not met",
                         f"{args.vapt_open_high} open (InfoSec)"))  # fmt: skip
        if not ok:
            reasons_c.append("VAPT high findings open")

    drill = _latest(ROOT / ".data" / "ops", "restore-drill-*.json")
    if drill is None:
        rows.append(_row("Restore drill completed inside 4 hours", "confirm", "IT, in UAT"))
    else:
        ok = drill["passed"] and drill["seconds"] < 4 * 3600
        rows.append(_row("Restore drill completed inside 4 hours", "met" if ok else "not met",
                         f"{drill['seconds'] // 60} min on {drill['where']} at {drill['at']}"))  # fmt: skip

    version = get_settings().privacy_notice_version
    live = not version.endswith("draft")
    rows.append(_row("Privacy notice live", "met" if live else "not met", f"version {version} (Legal / DPO)"))
    if not live:
        reasons_c.append("privacy notice still a draft")
    if args.sso_ready == "no":
        reasons_c.append("SSO or environments not ready")

    mode = "C. Preview" if reasons_c else "B. Capture first" if reasons_b else "A. Full"
    if mode == "A. Full" and any(r["state"] != "met" for r in rows):
        mode = "A. Full, once every 'confirm' row is confirmed"
    return {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rows": rows,
        "mode": mode,
        "why": reasons_c or reasons_b,
        "switches_off": [s["name"] for s in switches if s["state"] == "off"],
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
    args = parser.parse_args()
    text = render(collect(args))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
