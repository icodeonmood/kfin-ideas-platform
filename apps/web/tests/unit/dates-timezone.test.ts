/**
 * BLD-A165: every date or time on screen is India time. Server components render where the server runs, which
 * may be UTC (the dev stack's web container is), so a date formatted without `timeZone` showed "7:29 am" for a
 * draft saved at 12:59 pm. Every date formatting call in the app must name the time zone, or use `day()` /
 * `historyTime()` from lib/dates.ts, which do.
 *
 * A call counts as date formatting when it is `toLocaleDateString`, `toLocaleTimeString` or
 * `Intl.DateTimeFormat`, or a `toLocaleString` that either asks for a date or time part or is called on a
 * `Date`. A bare `x.toLocaleString("en-IN")` on a variable holding a date is the one shape it cannot see; use
 * `day()` or pass the options.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "../../src");
const DATE_PARTS = /\b(dateStyle|timeStyle|weekday|year|month|day|hour|minute)\s*:/;

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return files(full);
    return /\.(ts|tsx)$/.test(name) ? [full] : [];
  });
}

/** From an opening bracket's index + 1, the index just past its closing bracket. */
function closeOf(source: string, from: number): number {
  let depth = 1;
  let i = from;
  while (i < source.length && depth > 0) {
    if (source[i] === "(") depth += 1;
    if (source[i] === ")") depth -= 1;
    i += 1;
  }
  return i;
}

/** The expression a method is called on: back from the dot over brackets and names, to where it starts. */
function receiverOf(source: string, dot: number): string {
  let i = dot - 1;
  let depth = 0;
  while (i >= 0) {
    const c = source[i];
    if (c === ")") depth += 1;
    else if (c === "(") {
      if (depth === 0) break;
      depth -= 1;
    } else if (depth === 0 && !/[\w.$\s]/.test(c)) break;
    i -= 1;
  }
  return source.slice(i + 1, dot);
}

/** Every date formatting call in a source file, as written. */
export function dateCalls(source: string): string[] {
  const out: string[] = [];
  const re = /(\.toLocale(Date|Time)?String|\bIntl\.DateTimeFormat)\(/g;
  for (let m = re.exec(source); m; m = re.exec(source)) {
    const end = closeOf(source, m.index + m[0].length);
    const call = source.slice(m.index, end);
    const isDate =
      m[1].startsWith("Intl") ||
      m[2] !== undefined ||
      DATE_PARTS.test(call) ||
      /\bnew Date\b|\bDate\.now\b/.test(receiverOf(source, m.index));
    if (isDate) out.push(`${receiverOf(source, m.index).trim()}${call}`);
  }
  return out;
}

describe("dates on screen are India time (BLD-A165)", () => {
  it("every date formatted in the app names Asia/Kolkata", () => {
    const missing = files(SRC).flatMap((file) =>
      dateCalls(readFileSync(file, "utf8"))
        .filter((call) => !call.includes('timeZone: "Asia/Kolkata"'))
        .map((call) => `${path.relative(SRC, file)}: ${call.split("\n")[0]}`),
    );
    expect(missing).toEqual([]);
  });

  it("sees each shape of date call, and not numbers", () => {
    const seen = (code: string) => dateCalls(code).length;
    expect(seen('a = new Date(f(x, y)).toLocaleString("en-IN");')).toBe(1); // a call inside the constructor
    expect(seen('a = new Date(Date.now() + g(1)).toLocaleString("en-IN");')).toBe(1);
    expect(seen('a = when.toLocaleDateString("en-IN");')).toBe(1); // a date on a variable
    expect(seen('a = t.toLocaleTimeString("en-IN", { hour: "2-digit" });')).toBe(1);
    expect(seen('a = d.toLocaleString("en-IN", { dateStyle: "medium" });')).toBe(1);
    expect(seen('f = new Intl.DateTimeFormat("en-IN", { day: "numeric" });')).toBe(1);
    expect(seen('a = `₹${Math.round(n).toLocaleString("en-IN")}`;')).toBe(0); // rupees, not a date
    expect(seen('a = count.toLocaleString("en-IN");')).toBe(0);
  });
});
