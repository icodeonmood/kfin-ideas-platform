import { describe, expect, it } from "vitest";

import { measureList, oneName } from "@/lib/measures";
import { sparkFor } from "@/lib/spark";

describe("a One's spark (DEC-039)", () => {
  it("is the same every time for the same induction number, and stays inside its ranges", () => {
    expect(sparkFor(17)).toEqual(sparkFor(17));
    expect(sparkFor(17)).not.toEqual(sparkFor(18));
    for (let n = 1; n <= 500; n++) {
      const s = sparkFor(n);
      expect(s.angle).toBeGreaterThanOrEqual(38);
      expect(s.angle).toBeLessThanOrEqual(71);
      expect(s.x).toBeGreaterThan(0);
      expect(s.x).toBeLessThan(1);
      expect(s.y).toBeLessThan(0.8);
    }
  });
});

describe("measures in plain words (DEC-071)", () => {
  it("writes rupees with Indian grouping and keeps a fixed order", () => {
    expect(
      measureList({
        scale: { value: 30000, unit: "folios a month" },
        money: { value: 450000, unit: "rupees a year", finance_confirmed: true },
        time: { value: 120, unit: "hours a month" },
      }),
    ).toEqual([
      ["Time", "120 hours a month given back"],
      ["Money", "₹4,50,000 a year"],
      ["Scale", "30,000 folios a month"],
    ]);
    expect(measureList(undefined)).toEqual([]);
  });

  it("names a One only when they said yes", () => {
    expect(oneName(17, "Ananya Rao")).toBe("Ananya Rao");
    expect(oneName(17, null)).toBe("One No. 17");
  });
});
