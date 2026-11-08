/** AT-B3-02 (rules) and AT-B3-05 (strength meter), using the real rubric from the seed's rules/thresholds.md. */
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";
import { parse } from "yaml";

import { emptyCanvas, QUESTIONS, type Canvas } from "@/lib/canvas/model";
import { parseFigure, strength, validate, type StrengthRubric } from "@/lib/canvas/rules";

const thresholds = parse(
  /```yaml\n([\s\S]*?)```/.exec(
    readFileSync(path.resolve(__dirname, "../../../../seed/company-repo/rules/thresholds.md"), "utf8"),
  )![1]!,
);
const RUBRIC = thresholds.canvas_strength as StrengthRubric;
const LIMITS = thresholds.canvas as { one_line_max_words: number; details_min_chars: number };

function complete(): Canvas {
  const c = emptyCanvas("full");
  c.kind = "problem";
  c.one_line = "SIP registrations slip because forms are re-checked by hand";
  c.details =
    "Three people re-check every SIP form for missing bank or nominee fields before keying. ".repeat(3);
  c.who = {
    segments: ["kfin_teams", "investors"],
    frequency_or_reach: "daily",
    today_alternative: "Manual re-checks",
  };
  c.value.category = "cost_saving";
  c.value.play = "process_improvement";
  c.value.estimate.hours_saved_per_month = 130;
  c.value.basis = "own_data";
  c.ecosystem.solved_elsewhere = "partly";
  c.ecosystem.our_advantage = "We already run the form intake for most AMCs.";
  c.declarations = { no_personal_data: true, own_work_or_credited: true, ip_terms: true };
  return c;
}

describe("required fields (AT-B3-02)", () => {
  it("a complete full canvas passes", () => expect(validate(complete(), LIMITS)).toEqual([]));

  it("names each missing field", () => {
    const fields = validate(emptyCanvas("full"), LIMITS).map((e) => e.field);
    expect(fields).toEqual(
      expect.arrayContaining([
        "kind",
        "one_line",
        "details",
        "value.category",
        "declarations.no_personal_data",
        "declarations.own_work_or_credited",
        "declarations.ip_terms",
      ]),
    );
  });

  it("limits the one line to 20 words and needs 50 characters of detail", () => {
    const c = complete();
    c.one_line = Array.from({ length: 21 }, (_, i) => `word${i}`).join(" ");
    c.details = "too short";
    const errors = validate(c, LIMITS);
    expect(errors.find((e) => e.field === "one_line")?.message).toMatch(/20 words or fewer \(it has 21\)/);
    expect(errors.find((e) => e.field === "details")?.message).toMatch(/at least 50 characters/);
  });

  it("asks for the fix when the kind says there is one, and a reason for committee-only", () => {
    const c = complete();
    c.kind = "problem_with_solution";
    c.visibility = "committee";
    expect(validate(c, LIMITS).map((e) => e.field)).toEqual(["solution.approach", "visibility_reason"]);
  });

  it("quick capture needs only what it asks: what you noticed, cost or revenue, visibility, declarations", () => {
    const c = emptyCanvas("quick");
    c.details = "Investors call twice because the SIP confirmation SMS arrives a day late.";
    c.value.category = "not_sure";
    c.declarations = { no_personal_data: true, own_work_or_credited: true, ip_terms: true };
    expect(validate(c, LIMITS)).toEqual([]);
  });
});

describe("strength meter (AT-B3-05)", () => {
  it("scores 0 for an empty canvas and 5 for a complete one", () => {
    expect(strength(emptyCanvas("full"), RUBRIC).score).toBe(0);
    expect(strength(complete(), RUBRIC).score).toBe(5);
  });

  it("names the two most useful next additions", () => {
    const c = complete();
    c.value.estimate.hours_saved_per_month = null;
    c.ecosystem.solved_elsewhere = "dont_know";
    const s = strength(c, RUBRIC);
    expect(s.score).toBe(3);
    expect(s.nextBest).toEqual([
      "Add a rough ₹ or hours estimate",
      "Tell us if a competitor or another team already does this",
    ]);
  });

  it("counts a suggested answer only once it is accepted", () => {
    const c = complete();
    c.provenance["value.play"] = "suggested";
    expect(strength(c, RUBRIC).points.whats_it_worth).toBe(false);
    c.provenance["value.play"] = "accepted";
    expect(strength(c, RUBRIC).points.whats_it_worth).toBe(true);
  });

  it("a clean attachment counts as evidence", () => {
    const c = complete();
    c.value.basis = "hunch";
    expect(strength(c, RUBRIC).points.evidence).toBe(false);
    expect(strength(c, RUBRIC, 1).points.evidence).toBe(true);
  });

  it("never blocks: a weak canvas still validates", () => {
    const c = complete();
    c.value.basis = null;
    c.ecosystem.solved_elsewhere = null;
    expect(strength(c, RUBRIC).score).toBeLessThan(5);
    expect(validate(c, LIMITS)).toEqual([]);
  });
});

describe("canvas wording (§4.1)", () => {
  it("keeps the exact questions", () => {
    expect(QUESTIONS.one_line.label).toBe("Say it in one line, as you would to the CEO in a lift");
    expect(QUESTIONS.risks.why).toBe("Naming risks early builds trust. It never counts against the idea");
  });
  it("reads figures leniently but refuses junk", () => {
    expect(parseFigure("₹ 5,00,000")).toBe(500000);
    expect(parseFigure("")).toBeNull();
    expect(parseFigure("-3")).toBe("invalid");
    expect(parseFigure("lots")).toBe("invalid");
  });
});
