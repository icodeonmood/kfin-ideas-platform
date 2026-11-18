/**
 * F-COPY.plurals/3, L-QUESTIONS.clock/1, C-QCARD (BLD-A225): one countdown rule for every place. The browser's
 * `lib/countdown.ts` is held to the same vectors as the worker's `onepc/countdown.py`, label and all, so the Inbox,
 * Home, the questions card, Answer and the desk say the same thing about one deadline. Synthetic dates only.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { countdown, countdownLabel, nextTickMs, officeDay } from "@/lib/countdown";
import * as desk from "@/lib/desk/countdown";

interface Vector {
  why?: string;
  due: string;
  now: string;
  count: string;
  variant: string;
  label: string;
}

const vectors = (
  JSON.parse(
    readFileSync(path.resolve(__dirname, "../../../../services/worker/desk/countdown_vectors.json"), "utf8"),
  ) as { cases: Vector[] }
).cases;

describe("F-COPY.plurals/3 one countdown rule (lib/countdown, BLD-A225)", () => {
  it.each(vectors)("L-QUESTIONS.clock/1 C-QCARD: $due from $now reads $label", (v) => {
    const c = countdown(v.due, new Date(v.now));
    expect({ count: c.count, variant: c.variant, label: countdownLabel(c, "left") }).toEqual({
      count: v.count,
      variant: v.variant,
      label: v.label,
    });
  });

  it("the vectors carry the walk's deadline and the cases the rule turns on", () => {
    const walk = vectors.filter((v) => v.due === "2026-11-20T14:40:00+05:30").map((v) => [v.now, v.label]);
    expect(walk).toEqual(
      expect.arrayContaining([
        ["2026-11-18T13:00:00+05:30", "2 days left"],
        ["2026-11-18T16:00:00+05:30", "2 days left"],
        ["2026-11-19T14:40:00+05:30", "1 day left"],
        ["2026-11-19T14:41:00+05:30", "23:59 left"],
        ["2026-11-20T14:39:00+05:30", "00:01 left"],
        ["2026-11-20T14:40:00+05:30", "Overdue by 1 minute"],
        ["2026-11-20T14:40:30+05:30", "Overdue by 1 minute"],
        ["2026-11-20T19:40:00+05:30", "Overdue by 5 hours"],
        ["2026-11-23T14:40:00+05:30", "Overdue by 3 days"],
      ]),
    );
  });

  it("each place keeps its own words after the count: Desk.md, Answer.md, Inbox.md", () => {
    const due = "2026-11-20T14:40:00+05:30";
    const wed = new Date("2026-11-18T16:00:00+05:30");
    expect(countdownLabel(countdown(due, wed), "to answer")).toBe("2 days to answer");
    expect(countdownLabel(countdown(due, wed), "left to answer")).toBe("2 days left to answer");
    expect(countdownLabel(countdown(due, wed), "left")).toBe("2 days left");
    const late = new Date("2026-11-20T19:40:00+05:30");
    for (const suffix of ["to answer", "left to answer", "left"])
      expect(countdownLabel(countdown(due, late), suffix)).toBe("Overdue by 5 hours");
  });

  it("lib/desk/countdown is the same rule, re-exported for the review side", () => {
    expect(desk.countdown).toBe(countdown);
    expect(desk.countdownLabel).toBe(countdownLabel);
    expect(desk.nextTickMs).toBe(nextTickMs);
    expect(desk.officeDay).toBe(officeDay);
  });
});
