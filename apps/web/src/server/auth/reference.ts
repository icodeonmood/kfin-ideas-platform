/**
 * The short reference every sign-in failure carries (L-AUTH.rules/8): "SSO-7F3A, 9:42 am". The person reads it to
 * the IT service desk; the server log line for the same failure carries `ref: "SSO-7F3A"` and IDs only, so the
 * desk can find it. Four hex digits are enough to tell apart the failures of one morning; the time narrows it.
 */
import { randomBytes } from "node:crypto";

const REF = /^SSO-[0-9A-F]{4}$/;

export const newFailureRef = () => `SSO-${randomBytes(2).toString("hex").toUpperCase()}`;

export const isFailureRef = (value: unknown): value is string => typeof value === "string" && REF.test(value);

/** "9:42 am", India time. */
export function clockTime(at: Date): string {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  })
    .format(at)
    .toLowerCase();
}

/** "SSO-7F3A, 9:42 am" from the reference and the failure's time (seconds since 1970, from the redirect). */
export function referenceLabel(ref: string, atSeconds: number | null): string {
  if (!atSeconds || !Number.isFinite(atSeconds)) return ref;
  return `${ref}, ${clockTime(new Date(atSeconds * 1000))}`;
}
