/**
 * Level-1 personal-data check (ARCHITECTURE §4.2 step 2), TypeScript side. Same data as the Python engine:
 * `patterns.json` is generated from services/worker/pii/patterns.yaml (BLD-005). Runs in browser and server.
 * Results carry positions and labels, never the matched value.
 */
import rules from "./patterns.json";

export type Action = "block" | "warn";

export interface PatternMatch {
  patternId: string;
  label: string;
  dataType: string;
  start: number;
  end: number;
  action: Action;
}

interface RawPattern {
  id: string;
  label: string;
  data_type: string;
  regex: string;
  flags?: string;
  action: Action;
  checksum?: "verhoeff" | "luhn";
  context?: string[];
  warn_if_domain_in_env?: string;
  block_if_also?: string[];
  log_ok?: boolean;
}

interface CompiledPattern {
  raw: RawPattern;
  regex: RegExp;
  context: RegExp[];
}

const D = [
  [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
  [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
  [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
  [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
  [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
  [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
  [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
  [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
  [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
  [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
];
const P = [
  [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
  [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
  [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
  [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
  [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
  [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
  [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
  [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
];

export function verhoeffValid(digits: string): boolean {
  let c = 0;
  const reversed = [...digits].reverse();
  reversed.forEach((ch, i) => {
    c = D[c]![P[i % 8]![Number(ch)]!]!;
  });
  return c === 0;
}

export function luhnValid(digits: string): boolean {
  let total = 0;
  [...digits].reverse().forEach((ch, i) => {
    let n = Number(ch);
    if (i % 2 === 1) {
      n *= 2;
      if (n > 9) n -= 9;
    }
    total += n;
  });
  return total % 10 === 0;
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const compiled: CompiledPattern[] = (rules.patterns as RawPattern[]).map((raw) => ({
  raw,
  regex: new RegExp(raw.regex, "g" + (raw.flags?.includes("i") ? "i" : "")),
  context: (raw.context ?? []).map((k) => new RegExp(`(?<![A-Za-z0-9])${escapeRe(k)}(?![A-Za-z0-9])`, "i")),
}));

export const patternVersion: string = rules.version;
export const logRules = rules.log_rules;

function hasContext(text: string, start: number, end: number, keywords: RegExp[]): boolean {
  const w = rules.context_window_chars;
  const around = text.slice(Math.max(0, start - w), start) + " " + text.slice(end, end + w);
  return keywords.some((k) => k.test(around));
}

export function scan(text: string, kfinDomains: string[] = []): PatternMatch[] {
  const domains = kfinDomains.map((d) => d.toLowerCase());
  const found: PatternMatch[] = [];
  for (const p of compiled) {
    p.regex.lastIndex = 0;
    for (const m of text.matchAll(p.regex)) {
      const value = m[0];
      const start = m.index ?? 0;
      const end = start + value.length;
      const digits = value.replace(/[^0-9]/g, "");
      if (p.raw.checksum === "verhoeff" && !verhoeffValid(digits)) continue;
      if (p.raw.checksum === "luhn" && !(digits.length >= 13 && digits.length <= 19 && luhnValid(digits)))
        continue;
      if (p.context.length && !hasContext(text, start, end, p.context)) continue;
      let action: Action = p.raw.action;
      if (p.raw.warn_if_domain_in_env && domains.includes((value.split("@").pop() ?? "").toLowerCase())) {
        action = "warn";
      }
      found.push({ patternId: p.raw.id, label: p.raw.label, dataType: p.raw.data_type, start, end, action });
    }
  }
  const ids = new Set(found.map((f) => f.patternId));
  return found.map((f) => {
    const raw = compiled.find((c) => c.raw.id === f.patternId)!.raw;
    return (raw.block_if_also ?? []).some((other) => ids.has(other)) ? { ...f, action: "block" } : f;
  });
}

/** Pattern IDs in a value that may not appear in a log line (business identifiers marked log_ok are allowed). */
const safeValue = new RegExp(rules.log_rules.safe_value_regex);

export function logValuePatterns(value: string): string[] {
  if (safeValue.test(value)) return [];
  const ok = new Set((rules.patterns as RawPattern[]).filter((p) => p.log_ok).map((p) => p.id));
  return [...new Set(scan(value).map((m) => m.patternId))].filter((id) => !ok.has(id)).sort();
}
