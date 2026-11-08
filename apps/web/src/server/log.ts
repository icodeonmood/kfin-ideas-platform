/**
 * Structured JSON logging that carries IDs only (non-negotiable 3), mirroring services/worker/core/logging.py.
 * There is no free-text message: the first argument is an event name. Fields named like text or personal
 * data, and values matching a personal-data pattern, throw in dev and test and are dropped in UAT and prod.
 */
import { logRules, logValuePatterns } from "@/lib/pii/patterns";

type Scalar = string | number | boolean | null | undefined;
type Fields = Record<string, Scalar | Array<string | number>>;

const eventRe = new RegExp(logRules.event_name_regex);
const forbiddenRe = new RegExp(
  logRules.forbidden_field_regex,
  logRules.forbidden_field_flags.includes("i") ? "i" : "",
);
const forbiddenNames = new Set(logRules.forbidden_field_names.map((n: string) => n.toLowerCase()));
const allowedNames = new Set((logRules.allowed_field_names ?? []).map((n: string) => n.toLowerCase()));

export class LogPolicyError extends Error {}

export function fieldIsForbidden(name: string): boolean {
  const lowered = name.toLowerCase();
  if (allowedNames.has(lowered)) return false;
  return forbiddenNames.has(lowered) || forbiddenRe.test(name);
}

const strict = () => !["uat", "prod"].includes(process.env.APP_ENV ?? "dev");

function clean(fields: Fields): { out: Record<string, unknown>; dropped: string[] } {
  const out: Record<string, unknown> = {};
  const dropped: string[] = [];
  for (const [key, value] of Object.entries(fields)) {
    if (fieldIsForbidden(key)) {
      dropped.push(key);
      continue;
    }
    const strings = Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [value];
    if (strings.some((v) => typeof v === "string" && logValuePatterns(v).length > 0)) {
      dropped.push(key);
      continue;
    }
    out[key] = value;
  }
  return { out, dropped };
}

function emit(level: "info" | "warn" | "error", event: string, fields: Fields = {}): void {
  if (!eventRe.test(event)) {
    if (strict()) throw new LogPolicyError("log event must be a dotted snake_case name");
    event = "log.event_dropped";
    fields = {};
  }
  const { out, dropped } = clean(fields);
  if (dropped.length) {
    if (strict()) throw new LogPolicyError(`log fields refused: ${dropped.sort().join(", ")}`);
    out.dropped_fields = dropped.sort();
  }
  const line = JSON.stringify({ ts: new Date().toISOString(), level, logger: "web", event, ...out });
  (level === "error" ? process.stderr : process.stdout).write(line + "\n");
}

export const log = {
  info: (event: string, fields?: Fields) => emit("info", event, fields),
  warn: (event: string, fields?: Fields) => emit("warn", event, fields),
  error: (event: string, fields?: Fields) => emit("error", event, fields),
};
