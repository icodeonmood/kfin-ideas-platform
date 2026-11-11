/**
 * BLD-A165: every date or time on screen is India time. Server components render where the server runs, which
 * may be UTC (the dev stack's web container is), so a date formatted without `timeZone` showed "7:29 am" for a
 * draft saved at 12:59 pm. Each `new Date(…).toLocale…String(…)` in the app must name the time zone, or use
 * `day()` / `historyTime()` from lib/dates.ts, which do.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "../../src");

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return files(full);
    return /\.(ts|tsx)$/.test(name) ? [full] : [];
  });
}

/** The argument list of each `new Date(…).toLocale…String(` call, up to its closing bracket. */
function dateCalls(source: string): string[] {
  const out: string[] = [];
  const re = /new Date\([^)]*\)\s*\.toLocale(?:Date|Time)?String\(/g;
  for (let m = re.exec(source); m; m = re.exec(source)) {
    let depth = 1;
    let i = m.index + m[0].length;
    while (i < source.length && depth > 0) {
      if (source[i] === "(") depth += 1;
      if (source[i] === ")") depth -= 1;
      i += 1;
    }
    out.push(source.slice(m.index, i));
  }
  return out;
}

describe("dates on screen are India time (BLD-A165)", () => {
  it("every Date formatted in the app names Asia/Kolkata", () => {
    const missing = files(SRC).flatMap((file) =>
      dateCalls(readFileSync(file, "utf8"))
        .filter((call) => !call.includes('timeZone: "Asia/Kolkata"'))
        .map((call) => `${path.relative(SRC, file)}: ${call.split("\n")[0]}`),
    );
    expect(missing).toEqual([]);
  });

  it("finds the calls it checks", () => {
    expect(dateCalls('x = new Date(a).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });')).toHaveLength(
      1,
    );
    expect(dateCalls('x = new Date(a.b).toLocaleDateString("en-IN");')).toHaveLength(1);
  });
});
