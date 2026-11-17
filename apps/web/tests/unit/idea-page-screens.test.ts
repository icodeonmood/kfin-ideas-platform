/**
 * S-06 and S-09's pure parts: the card's sentence composed from lane B's decision (S-06.states, BLD-E012) and the
 * stages as C-TRACK draws them (S-06.layout/3, S-09.layout/4). Synthetic data only.
 */
import { describe, expect, it } from "vitest";

import { decisionSentence, type Decided } from "@/app/ideas/[id]/decision";
import { toTrack } from "@/app/ideas/[id]/track";

const NOW_YEAR = new Date().getFullYear();

function decided(
  choice: "pick" | "not_now" | "not_picked",
  extra: Partial<Decided["decision"]> = {},
  returnAt: string | null = null,
) {
  return {
    decision: {
      choice,
      label: "",
      merged_into: null,
      by_line: "by Harish from the review desk, Thursday 12 November",
      reason: "A synthetic reason of more than thirty characters.",
      reason_heading: "The review desk’s reason, as Tanvi read it",
      ...extra,
    },
    decided_at: `${NOW_YEAR}-11-12T08:00:00Z`,
    return_at: returnAt,
  } as unknown as Decided;
}

describe("S-06.states: the card's sentence for a decision", () => {
  it("Picked names who picked it, when, and when the build team is chosen", () => {
    const s = decisionSentence(decided("pick"), "Harish", [
      { stage: "built", state: "now", detail: "Team chosen by Thursday 26 November" },
    ]);
    expect(s?.lead).toBe("Picked. A team is being chosen to build it.");
    expect(s?.rest).toBe(
      "Harish from the review desk picked it on Thursday 12 November. The build team is chosen by Thursday 26 November.",
    );
  });

  it("Picked and joined with another idea says so (S-06.states, Picked)", () => {
    const s = decisionSentence(decided("pick", { merged_into: "IDEA-2026-001412" }), "Meera", []);
    expect(s?.rest).toBe(
      "Meera from the review desk picked it on Thursday 12 November and joined it with IDEA-2026-001412, so one team builds one fix.",
    );
  });

  it("Not now gives the day it comes back and the month, and points to the full reason", () => {
    const s = decisionSentence(decided("not_now", {}, `${NOW_YEAR + 1}-02-16T04:00:00Z`), "Meera", []);
    expect(s?.lead).toBe(
      `Not now. The review desk looks at it again on Tuesday 16 February ${NOW_YEAR + 1}.`,
    );
    expect(s?.rest).toBe(
      "Your idea stays open, with your answers and anyone who teams up, and comes back to the review desk first thing in February. Meera’s full reason is below.",
    );
  });

  it("Not picked on its own says where the words carry on (S-06.states, Not picked)", () => {
    const s = decisionSentence(decided("not_picked", { merged_into: "IDEA-2026-001412" }), "Meera", []);
    expect(s?.lead).toBe("Not picked on its own. Your words carry on in IDEA-2026-001412.");
    expect(s?.rest).toMatch(/^It’s the same problem as an idea the review desk is taking forward\./);
  });

  it("without a reviewer's name it speaks for the review desk", () => {
    expect(decisionSentence(decided("not_picked"), null, [])).toEqual({
      lead: "Not picked.",
      rest: "The review desk’s full reason is below.",
    });
  });
});

describe("C-TRACK from the API's stages", () => {
  it("maps every stage and state, and keeps each detail line", () => {
    const t = toTrack([
      { stage: "shared", state: "done", detail: "Sunday 15 November" },
      { stage: "checked_matched", state: "done", detail: "1 PAN hidden" },
      { stage: "reviewed", state: "not_going_ahead", detail: "Withdrawn before review" },
      { stage: "built", state: "not_going_ahead" },
      { stage: "shipped", state: "to_come", detail: "Then we measure what changed" },
    ]);
    expect(t).toEqual({
      shared: { state: "done", line: "Sunday 15 November" },
      checked: { state: "done", line: "1 PAN hidden" },
      reviewed: { state: "off", line: "Withdrawn before review" },
      built: { state: "off", line: undefined },
      shipped: { state: "next", line: "Then we measure what changed" },
    });
  });

  it("draws nothing for a merged idea, which has no stages of its own", () => {
    expect(toTrack([])).toBeNull();
    expect(toTrack(undefined)).toBeNull();
  });
});
