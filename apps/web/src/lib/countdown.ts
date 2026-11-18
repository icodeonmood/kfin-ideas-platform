/**
 * One countdown rule for every clock a person reads (F-COPY.plurals/3, L-QUESTIONS.clock/1, C-QCARD; BLD-A225): the
 * Inbox, Home's questions card, Answer, the desk and the committee's window all count the same way and differ only in
 * the words after the count ("left", "to answer", "left to answer"). The browser twin of
 * `services/worker/onepc/countdown.py` `countdown`, so a pill can tick each minute without a reload and still say
 * exactly what the server said. Both are tested against `services/worker/desk/countdown_vectors.json`.
 * `lib/desk/countdown.ts` re-exports it for the review side.
 *
 * A day or more ahead counts calendar days in office time (India); under a day it is "07:38"; once late, how
 * late ("5 hours").
 */
export type CountdownVariant = "normal" | "warn" | "bad";

export interface Countdown {
  seconds: number;
  count: string;
  variant: CountdownVariant;
}

const DAY = 86_400;

function amount(n: number, unit: string): string {
  return `${n} ${unit}${n === 1 ? "" : "s"}`;
}

/** The calendar date in India time, as a day number, so two dates can be subtracted. */
export function officeDay(ms: number): number {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(ms)); // "2026-11-16"
  return Math.round(Date.parse(`${parts}T00:00:00Z`) / (DAY * 1000));
}

export function countdown(dueAt: string | Date, now: Date = new Date()): Countdown {
  const due = typeof dueAt === "string" ? Date.parse(dueAt) : dueAt.getTime();
  const left = Math.trunc((due - now.getTime()) / 1000);
  if (left <= 0) {
    const late = -left;
    if (late < 3600)
      // At most 59: from 3,541 s late, rounding up would say "60 minutes" rather than an hour (BLD-A225 review)
      return {
        seconds: left,
        count: amount(Math.min(59, Math.max(1, Math.ceil(late / 60))), "minute"),
        variant: "bad",
      };
    if (late < DAY) return { seconds: left, count: amount(Math.floor(late / 3600), "hour"), variant: "bad" };
    return { seconds: left, count: amount(Math.floor(late / DAY), "day"), variant: "bad" };
  }
  if (left < DAY) {
    const minutes = Math.max(1, Math.floor(left / 60));
    const hh = String(Math.floor(minutes / 60)).padStart(2, "0");
    const mm = String(minutes % 60).padStart(2, "0");
    return { seconds: left, count: `${hh}:${mm}`, variant: "warn" };
  }
  return {
    seconds: left,
    count: amount(officeDay(due) - officeDay(now.getTime()), "day"),
    variant: "normal",
  };
}

/** "3 days to answer", "07:38 left", "Overdue by 5 hours": the suffix is the place's own words. */
export function countdownLabel(c: Countdown, suffix: string): string {
  return c.variant === "bad" ? `Overdue by ${c.count}` : `${c.count} ${suffix}`;
}

/** Milliseconds to the next whole minute: pills re-render each minute, which is when any label can change. */
export function nextTickMs(nowMs: number = Date.now()): number {
  return 60_000 - (nowMs % 60_000);
}
