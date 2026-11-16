/**
 * Dates as the review side says them, in office time (India), for what the browser shows before the server has
 * answered: the answer deadline while questions are still queued (L-QUESTIONS.ask/4) and dates on the panel.
 * The twin of `services/worker/desk/when.py` and `clock.answer_due`; tested against the same examples.
 */
import type { TimeToAnswer } from "@/lib/contracts";

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

type Parts = { y: number; m: number; d: number; wd: number; h: number; mi: number };

function partsOf(t: Date): Parts {
  const f = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "numeric",
    hourCycle: "h23",
    weekday: "short",
  }).formatToParts(t);
  const get = (k: string) => f.find((p) => p.type === k)?.value ?? "";
  const wd = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(get("weekday"));
  return { y: +get("year"), m: +get("month"), d: +get("day"), wd, h: +get("hour"), mi: +get("minute") };
}

const toDate = (t: string | Date) => (typeof t === "string" ? new Date(t) : t);

/** "6 pm", "6:30 pm", "12:05 pm". */
export function clockLabel(t: string | Date): string {
  const p = partsOf(toDate(t));
  const hour = p.h % 12 || 12;
  const suffix = p.h < 12 ? "am" : "pm";
  return p.mi === 0 ? `${hour} ${suffix}` : `${hour}:${String(p.mi).padStart(2, "0")} ${suffix}`;
}

/** "Friday 20 November"; with the year when it is not this year ("Tuesday 16 February 2027"). */
export function dayLabel(t: string | Date, now: Date = new Date()): string {
  const p = partsOf(toDate(t));
  const year = p.y === partsOf(now).y ? "" : ` ${p.y}`;
  return `${DAYS[p.wd]} ${p.d} ${MONTHS[p.m - 1]}${year}`;
}

/** "7 pm today", "6 pm tomorrow", else "Thursday 19 November, 6 pm". */
export function deadlineLabel(t: string | Date, now: Date = new Date()): string {
  const a = partsOf(toDate(t));
  const b = partsOf(now);
  const gap = Math.round((Date.UTC(a.y, a.m - 1, a.d) - Date.UTC(b.y, b.m - 1, b.d)) / 86_400_000);
  if (gap === 0) return `${clockLabel(t)} today`;
  if (gap === 1) return `${clockLabel(t)} tomorrow`;
  return `${dayLabel(t, now)}, ${clockLabel(t)}`;
}

/** L-QUESTIONS.clock/5: 1 day is 24 hours from sending; 3 days and 1 week end at the deadline hour, office time. */
export function answerDue(
  sentAt: Date,
  time: TimeToAnswer,
  days: Record<TimeToAnswer, number> = { "1d": 1, "3d": 3, "1w": 7 },
  deadlineHour = 18,
): Date {
  const n = days[time];
  if (n === 1) return new Date(sentAt.getTime() + 24 * 3_600_000);
  const p = partsOf(sentAt);
  // The deadline hour in India (UTC+5:30, no daylight saving) on the day n days on.
  return new Date(Date.UTC(p.y, p.m - 1, p.d + n, deadlineHour, 0) - 5.5 * 3_600_000);
}
