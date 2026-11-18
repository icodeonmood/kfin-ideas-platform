/**
 * The admin page's "Entered" figures (J-ONE/2, L-IMPACT; lane A, BLD-A210). The form saves `{amount, unit, line}`;
 * the synthetic 1% Club seed saves its older `{value, line}`, which lane E's Wall reader also reads
 * (services/worker/wall/impact.py). Both read as words, and neither shows "NaN". Synthetic figures only.
 */
import { describe, expect, it } from "vitest";

import { figureLines } from "@/app/admin/programme";

describe("J-ONE/2, L-IMPACT: the admin page's entered figures", () => {
  it("reads the form's figures with their units", () => {
    expect(
      figureLines({
        time: { amount: 620, unit: "hours a month" },
        money: { amount: 1800000, unit: "rupees a year" },
        effort: { amount: 2, unit: "fewer steps", line: "Per new mandate" },
        scale: { amount: 1200, unit: "distributors" },
        sentence: "620 hours a month saved",
      }),
    ).toEqual(["620 hours a month", "₹18,00,000 a year", "2 fewer steps", "1,200 distributors"]);
  });

  it("reads the seed's older figures as their own words, never NaN", () => {
    const lines = figureLines({
      time: { value: "620", line: "hours a month" },
      money: { value: "₹18 lakh", line: "a year" },
      effort: { value: "2 fewer steps", line: "per online form" },
      scale: { value: "58,600", line: "distributors reached" },
    });
    expect(lines).toEqual([
      "620 hours a month",
      "₹18 lakh a year",
      "2 fewer steps per online form",
      "58,600 distributors reached",
    ]);
    expect(lines.join(" ")).not.toContain("NaN");
  });

  it("leaves out a figure with nothing in it", () => {
    expect(figureLines({ time: { value: " " }, money: {} })).toEqual([]);
  });
});
