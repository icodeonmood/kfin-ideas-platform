/**
 * S-R4 "Your window" bar (board Committee, `view()`): how much of a decision's window has gone, out of the most it
 * can run (3 months from the decision). Decorative: the words beside it already say the days left.
 *
 * - total: opens → max_closes; used: opens → now; base: opens → closes.
 * - The fill is used/total while the window is open, else base/total.
 * - An extended window shows its extension hatched, from the first 30 days to base.
 * - Every value is a percentage clamped to 0–100, to one decimal.
 * - Tone: "soon" (7 days or fewer left, office calendar days as the "N days left" line counts them), "done" once
 *   expired, "rev" once reversed.
 */
import type { CommitteeRow } from "@/lib/contracts";

import { officeDay } from "./countdown";

export type WindowBarTone = "open" | "soon" | "done" | "rev";

export interface WindowBar {
  tone: WindowBarTone;
  fill: number; // % of the track
  ext: { left: number; width: number } | null; // % of the track; null when never extended
}

type WindowFacts = Pick<
  CommitteeRow["window"],
  "state" | "opens_at" | "closes_at" | "max_closes_at" | "extended_times"
>;

const DAY_MS = 86_400_000;
const FIRST_WINDOW_MS = 30 * DAY_MS; // L-COMMITTEE.rules/1: 30 days from the decision
const SOON_DAYS = 7;

export function windowBar(w: WindowFacts, now: Date): WindowBar {
  const opens = Date.parse(w.opens_at);
  const closes = Date.parse(w.closes_at);
  const total = Date.parse(w.max_closes_at) - opens;
  const used = now.getTime() - opens;
  const base = closes - opens;
  const pct = (ms: number) =>
    total > 0 ? Math.round(Math.max(0, Math.min(100, (ms / total) * 100)) * 10) / 10 : 100;

  const open = w.state === "open" || w.state === "extended";
  const tone: WindowBarTone =
    w.state === "reversed"
      ? "rev"
      : !open
        ? "done"
        : officeDay(closes) - officeDay(now.getTime()) <= SOON_DAYS
          ? "soon"
          : "open";

  return {
    tone,
    fill: pct(open ? used : base),
    ext: w.extended_times > 0 ? { left: pct(FIRST_WINDOW_MS), width: pct(base - FIRST_WINDOW_MS) } : null,
  };
}
