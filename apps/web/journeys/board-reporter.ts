/**
 * The journey board: journey × step, each pass, fail, or fixme with the missing module (lane G). Written to
 * `test-results/journeys/board.md`; the journeys workflow appends it to the job summary.
 */
import fs from "node:fs";
import path from "node:path";

import type { FullResult, Reporter, Suite, TestCase, TestResult } from "@playwright/test/reporter";

import { JOURNEYS, SHOTS_DIR } from "./lib";

type Cell = {
  row: string;
  screen: string;
  title: string;
  outcome: "pass" | "fail" | "fixme" | "skipped";
  note: string;
};

const OUT = path.join(path.dirname(SHOTS_DIR), "board.md");
const MARK = { pass: "✅", fail: "❌", fixme: "⏸", skipped: "⏭" } as const;

function parse(title: string): { journey: string; row: string; screen: string; rest: string } | undefined {
  const m = /^(J-[A-Z]+)\/(\S+) (\S+) · (.*)$/.exec(title);
  return m ? { journey: m[1]!, row: m[2]!, screen: m[3]!, rest: m[4]! } : undefined;
}

export default class BoardReporter implements Reporter {
  private order: string[] = [];
  private cells = new Map<string, Cell>();

  onBegin(_config: unknown, suite: Suite): void {
    fs.rmSync(SHOTS_DIR, { recursive: true, force: true });
    this.order = suite.allTests().map((t) => t.title);
  }

  onTestEnd(test: TestCase, result: TestResult): void {
    const p = parse(test.title);
    if (!p) return;
    const fixme = test.annotations.find((a) => a.type === "fixme");
    let outcome: Cell["outcome"];
    let note = "";
    if (fixme) {
      outcome = "fixme";
      note = (fixme.description ?? "").replace(/^not on main: /, "");
    } else if (result.status === "passed") {
      outcome = "pass";
    } else if (result.status === "skipped") {
      outcome = "skipped";
    } else {
      outcome = "fail";
      note = (result.error?.message ?? result.status)
        .split("\n")[0]!
        .replace(/\u001b\[[0-9;]*m/g, "")
        .slice(0, 160);
    }
    this.cells.set(test.title, { row: p.row, screen: p.screen, title: p.rest, outcome, note });
  }

  onEnd(result: FullResult): void {
    const sha = (process.env.GITHUB_SHA ?? "local").slice(0, 7);
    const when = new Date().toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
      dateStyle: "medium",
      timeStyle: "short",
    });
    const lines = [
      `## Journey board · ${sha} · ${when} IST · ${result.status}`,
      "",
      "✅ pass · ❌ fail · ⏸ fixme (module not on main, or GAP-SEED) · ⏭ skipped",
      "",
      "| Journey | Pass | Fail | Fixme | Steps |",
      "|---|---:|---:|---:|---|",
    ];
    const failures: string[] = [];
    for (const journey of JOURNEYS) {
      const cells = this.order
        .filter((t) => t.startsWith(`${journey}/`))
        .map((t) => this.cells.get(t))
        .filter((c): c is Cell => Boolean(c));
      if (!cells.length) {
        lines.push(`| ${journey} | 0 | 0 | 0 | no spec yet |`);
        continue;
      }
      const count = (o: Cell["outcome"]) => cells.filter((c) => c.outcome === o).length;
      const steps = cells
        .map((c) => `${c.row} ${MARK[c.outcome]}${c.outcome === "fixme" ? ` ${c.note}` : ""}`)
        .join(" · ");
      lines.push(`| ${journey} | ${count("pass")} | ${count("fail")} | ${count("fixme")} | ${steps} |`);
      for (const c of cells.filter((c) => c.outcome === "fail")) {
        failures.push(`- **${journey}/${c.row} ${c.screen}** · ${c.title}: ${c.note.replaceAll("|", "\\|")}`);
      }
    }
    if (failures.length) lines.push("", "### Failures", "", ...failures);
    fs.mkdirSync(path.dirname(OUT), { recursive: true });
    fs.writeFileSync(OUT, `${lines.join("\n")}\n`);
  }

  printsToStdio(): boolean {
    return false;
  }
}
