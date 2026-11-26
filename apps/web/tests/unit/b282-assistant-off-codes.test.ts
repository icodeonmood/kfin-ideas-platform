/**
 * DEC-143 (f), BLD-B282: while the assistant is off, the worker's text checks answer 503
 * `{ error: "checks_unavailable", code: "switched_off" }` (api/app.py `_ones_call`, `_delivery_call`; the gateway's
 * `AgentSwitchedOff`, also raised as `daily_budget`). The web app's Ones, Ember and delivery calls show that refusal
 * as `assistant_off`, so the Showcase brief, the Ember note and delivery's notes can say they save once the assistant
 * is back. Any other failure of the checks stays `checks_unavailable`. The worker is a stub; synthetic ids only.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ASSISTANT_OFF, SAVES_ONCE_BACK } from "@/lib/assistant-off";

const reply = vi.hoisted(() => ({ status: 503, body: {} as Record<string, unknown> }));

vi.mock("@/server/worker", () => ({
  workerFetch: async () => new Response(JSON.stringify(reply.body), { status: reply.status }),
}));

const { refusalCode } = await import("@/server/worker-codes");
const { saveShowcase } = await import("@/server/ones");
const { emberNote } = await import("@/server/ember");
const { checkIn, completeFix, fillMeasurement } = await import("@/server/delivery");
const { SubmissionError } = await import("@/server/submissions");
const { ERRORS } = await import("@/app/delivery/actions");

const me = { id: "0b7e6a52-6c1a-4e0e-8f43-0000000000aa", name: "Kavya Menon" } as never;

/** Each save the lead's (f) names, as the web app's server calls the worker. */
const SAVES: Array<[string, () => Promise<unknown>]> = [
  ["the Showcase brief", () => saveShowcase(me, { idea: "Fewer returned forms at the branch." })],
  ["the Ember note", () => emberNote(me, "7", { note: "We look for problems people meet every week." })],
  [
    "a delivery check-in's note",
    () => checkIn(me, "12", { status: "on_track", note: "Two branches are live." }),
  ],
  [
    "the completion's notes",
    () => completeFix(me, "12", { before: 10, after: 2, notes: "Counted at six branches." }),
  ],
  [
    "a result's notes",
    () => fillMeasurement(me, "12", "day_30", { metric_actual: 2, notes: "Counted twice." }),
  ],
];

async function refusal(save: () => Promise<unknown>): Promise<string> {
  const err = await save().then(
    () => null,
    (e: unknown) => e,
  );
  expect(err).toBeInstanceOf(SubmissionError);
  return (err as InstanceType<typeof SubmissionError>).code;
}

beforeEach(() => {
  reply.status = 503;
  reply.body = {};
});

describe("DEC-143 (f), BLD-B282: refusalCode", () => {
  it.each([
    ["switched_off", ASSISTANT_OFF],
    ["daily_budget", ASSISTANT_OFF],
    ["route_unavailable", "checks_unavailable"],
    ["leak_abort", "checks_unavailable"],
    [undefined, "checks_unavailable"],
  ])("checks_unavailable with code %s reads as %s", (code, shown) => {
    expect(refusalCode({ error: "checks_unavailable", code }, "x_unavailable")).toBe(shown);
  });

  it("leaves every other refusal as the worker said it, and falls back when there is none", () => {
    expect(refusalCode({ error: "personal_data", code: "switched_off" }, "x_unavailable")).toBe(
      "personal_data",
    );
    expect(refusalCode({}, "x_unavailable")).toBe("x_unavailable");
  });
});

describe("DEC-143 (f), BLD-B282: the saves the lead names", () => {
  for (const [name, save] of SAVES) {
    it(`${name}: the assistant off is assistant_off; the checks down stay checks_unavailable`, async () => {
      reply.body = { error: "checks_unavailable", code: "switched_off" };
      expect(await refusal(save)).toBe(ASSISTANT_OFF);
      reply.body = { error: "checks_unavailable", code: "route_unavailable" };
      expect(await refusal(save)).toBe("checks_unavailable");
    });
  }

  it("delivery's and the Ember compose page's shared words say it saves once the assistant is back", () => {
    expect(ERRORS[ASSISTANT_OFF]).toBe(SAVES_ONCE_BACK);
    expect(ERRORS.checks_unavailable).toBe(
      "We can't check text just now. Please try again in a few minutes.",
    );
  });
});
