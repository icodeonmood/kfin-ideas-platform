/**
 * L-WORTH/2–7: the worth revision's response as the worker returns it. The sample is the worker's own
 * (services/worker/desk/worth_response_sample.json, checked against revise.revise_worth by
 * test_L_WORTH_the_revision_response_matches_the_shared_sample), so the two sides cannot drift: the sharer and the
 * reviewer carry figures, and the person who revised it sits under `reviewer.by`.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import type { WorthFigure, WorthFigures, WorthResponse } from "@/lib/contracts/api";

const sample = JSON.parse(
  readFileSync(
    path.resolve(__dirname, "../../../../services/worker/desk/worth_response_sample.json"),
    "utf8",
  ),
) as WorthResponse & { _about: string };

const FIGURE_KEYS = ["hours_month", "cost_month", "revenue_month"] as const;

function isFigure(x: unknown): x is WorthFigure {
  if (typeof x !== "object" || x === null) return false;
  const f = x as Record<string, unknown>;
  return (
    Object.keys(f).sort().join() === "high,low,text" &&
    typeof f.low === "number" &&
    (f.high === null || typeof f.high === "number") &&
    typeof f.text === "string"
  );
}

function figuresOnly(w: WorthFigures): void {
  for (const k of FIGURE_KEYS) if (w[k] !== undefined) expect(isFigure(w[k]), k).toBe(true);
  if (w.outside_tools !== undefined) expect(["none", "partly", "fully"]).toContain(w.outside_tools);
}

describe("L-WORTH: WorthResponse matches the worker's sample", () => {
  it("has the response's keys and no others", () => {
    const { _about, ...body } = sample;
    expect(_about).toContain("revise.revise_worth");
    expect(Object.keys(body).sort()).toEqual(
      ["area", "idea_id", "kind", "reviewer", "sharer", "tiles", "worth_id"].sort(),
    );
  });

  it("carries figures for the sharer, not a person", () => {
    figuresOnly(sample.sharer);
    expect(Object.keys(sample.sharer).every((k) => [...FIGURE_KEYS, "outside_tools"].includes(k))).toBe(true);
    expect(sample.sharer.hours_month).toEqual({ low: 70, high: 150, text: "70 to 150 hours a month" });
    expect(sample.sharer.cost_month?.high).toBeNull();
  });

  it("carries the revised figures for the reviewer, with the person under `by`", () => {
    const { note, by, at, ...figures } = sample.reviewer;
    figuresOnly(figures);
    expect(typeof note).toBe("string");
    expect(Object.keys(by).sort()).toEqual(["area", "city", "first_name", "id", "initials", "name"]);
    expect(by.first_name).toBe("Meera");
    expect(Number.isNaN(Date.parse(at))).toBe(false);
  });

  it("keeps four tiles with what each was", () => {
    expect(sample.tiles.map((t) => t.measure)).toEqual([
      "hours_month",
      "cost_month",
      "revenue_month",
      "outside_tools",
    ]);
    expect(sample.tiles[0]).toMatchObject({ changed: true, was: "was 70 to 150 hours a month" });
  });
});
