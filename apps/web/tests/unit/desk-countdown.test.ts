import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { countdown, countdownLabel } from "@/lib/desk/countdown";

interface Vector {
  due: string;
  now: string;
  count: string;
  variant: string;
}

const vectors = (
  JSON.parse(
    readFileSync(path.resolve(__dirname, "../../../../services/worker/desk/countdown_vectors.json"), "utf8"),
  ) as { cases: Vector[] }
).cases;

describe("S-R1.rules/2 live countdowns match the worker's", () => {
  it.each(vectors)("$due from $now reads $count ($variant)", (v) => {
    const c = countdown(v.due, new Date(v.now));
    expect({ count: c.count, variant: c.variant }).toEqual({ count: v.count, variant: v.variant });
  });

  it("labels: the place's words, or how late", () => {
    const now = new Date("2026-11-16T11:20:00+05:30");
    expect(countdownLabel(countdown("2026-11-19T18:00:00+05:30", now), "to answer")).toBe("3 days to answer");
    expect(countdownLabel(countdown("2026-11-16T06:20:00+05:30", now), "to answer")).toBe(
      "Overdue by 5 hours",
    );
    expect(countdownLabel(countdown("2026-11-16T18:58:00+05:30", now), "left")).toBe("07:38 left");
  });
});
