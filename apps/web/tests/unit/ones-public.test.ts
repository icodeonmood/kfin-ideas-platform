/**
 * S-01.rules/3, A-API.ones, P-PRODUCT.privacy (DEC-104, BLD-A179): what signed-out people see of the Ones on Landing.
 * Only Ones whose brief is public; a name only while its owner has not switched it off in Profile (no
 * person_settings row: not switched off).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PublicOne } from "@/server/ones";

const answer = vi.fn<() => Response>();
vi.mock("@/server/worker", () => ({ workerFetch: async () => answer() }));
vi.mock("@/server/log", () => ({ log: { warn: vi.fn(), error: vi.fn(), info: vi.fn() } }));

const { pgWallNameSettings, publicOnes, setWallNameSettings, wallOnes } = await import("@/server/ones");

/** Synthetic Ones, newest first, as the worker's /internal/ones/public gives them. */
function one(no: number, name: string | null, brief: string | null): PublicOne {
  return {
    number: no,
    induction_no: no,
    tier: 1,
    tier_name: "Spark",
    tier_colour: "#F46835",
    name,
    founding: false,
    way_in: "Accepted idea",
    line: `Synthetic idea line ${no}`,
    stage: "Shipped",
    brief,
    measures: {},
  };
}

const worker = (ones: PublicOne[], paused = false) =>
  answer.mockImplementation(() => new Response(JSON.stringify({ paused, ones }), { status: 200 }));

/** person_settings as a map of induction number → show_name_on_wall; a missing number has no row. */
const settings = (rows: Record<number, boolean>) =>
  setWallNameSettings({
    hiddenFor: async (nos) => new Set(nos.filter((n) => rows[n] === false)),
  });

beforeEach(() => {
  answer.mockReset();
});

afterEach(() => {
  setWallNameSettings(pgWallNameSettings);
});

describe("S-01.rules/3 publicOnes(): the Ones on Landing", () => {
  it("shows only Ones with a public (approved) brief", async () => {
    worker([
      one(31, "Synthetic Person A", null),
      one(23, "Synthetic Person B", "Plain words when a transaction is turned back."),
      one(17, "Synthetic Person C", "   "),
      one(9, "Synthetic Person D", "One write-up of a fix other teams can adopt."),
    ]);
    settings({});
    const out = await publicOnes();
    expect(out.paused).toBe(false);
    expect(out.ones.map((o) => o.number)).toEqual([23, 9]);
  });

  it("hides the name of a One who switched it off in Profile; no person_settings row means shown (DEC-104)", async () => {
    worker([one(23, "Synthetic Person B", "Brief B"), one(9, "Synthetic Person D", "Brief D")]);
    settings({ 23: false });
    const out = await publicOnes();
    expect(out.ones.map((o) => [o.number, o.name])).toEqual([
      [23, null],
      [9, "Synthetic Person D"],
    ]);
    settings({ 23: true });
    expect((await publicOnes()).ones.map((o) => o.name)).toEqual([
      "Synthetic Person B",
      "Synthetic Person D",
    ]);
  });

  it("never puts back a name the worker left out", async () => {
    worker([one(23, null, "Brief B")]);
    settings({ 23: true });
    expect((await publicOnes()).ones[0]!.name).toBeNull();
  });

  it("shows no name at all when the switches cannot be read (fail closed)", async () => {
    worker([one(23, "Synthetic Person B", "Brief B"), one(9, "Synthetic Person D", "Brief D")]);
    setWallNameSettings({
      hiddenFor: async () => {
        throw new Error("db down");
      },
    });
    expect((await publicOnes()).ones.map((o) => o.name)).toEqual([null, null]);
  });

  it("shows none while ones.public is off", async () => {
    worker([one(23, "Synthetic Person B", "Brief B")], true);
    expect(await publicOnes()).toEqual({ paused: true, ones: [] });
  });
});

describe("P-PRODUCT.privacy wallOnes(): signed-in surfaces keep every active One, names as chosen", () => {
  it("keeps Ones without a brief and hides switched-off names", async () => {
    worker([one(31, "Synthetic Person A", null), one(23, "Synthetic Person B", "Brief B")]);
    settings({ 31: false });
    const out = await wallOnes();
    expect(out.ones.map((o) => [o.number, o.name])).toEqual([
      [31, null],
      [23, "Synthetic Person B"],
    ]);
  });
});
