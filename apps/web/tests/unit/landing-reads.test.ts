/**
 * S-01.rules/2-3, BLD-A172: Landing's two reads never hold the front door. Each waits at most LANDING_WAIT_MS, then
 * the page draws as it would if the read failed: who reviews without when, and no Ones slab.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const reads = {
  promises: vi.fn<() => Promise<unknown>>(),
  publicOnes: vi.fn<(timeoutMs?: number) => Promise<unknown>>(),
};
vi.mock("@/server/promises", () => ({ promises: () => reads.promises() }));
vi.mock("@/server/ones", () => ({ publicOnes: (ms?: number) => reads.publicOnes(ms) }));

const { atMost, LANDING_WAIT_MS, landingOnes, reviewDays } = await import("@/server/landing");

const never = () => new Promise<never>(() => {});
const one = (n: number) => ({ number: n, induction_no: n, brief: "Synthetic brief" });

beforeEach(() => {
  reads.promises.mockReset();
  reads.publicOnes.mockReset();
});

describe("S-01.rules/2-3, BLD-A172: Landing's reads wait at most a moment", () => {
  it("waits 1.5 to 2 seconds at most", () => {
    expect(LANDING_WAIT_MS).toBeGreaterThanOrEqual(1_500);
    expect(LANDING_WAIT_MS).toBeLessThanOrEqual(2_000);
  });

  it("a worker that answers in time gives the review days and the three newest Ones", async () => {
    reads.promises.mockResolvedValue({ review: { decide_by_working_days: 5 } });
    reads.publicOnes.mockResolvedValue({ paused: false, ones: [one(31), one(23), one(17), one(9)] });
    expect(await reviewDays(50)).toBe(5);
    expect((await landingOnes(50)).map((o) => o.number)).toEqual([31, 23, 17]);
    expect(reads.publicOnes).toHaveBeenCalledWith(50); // the worker call itself is cut off too
  });

  it("a worker that hangs: no review time and no Ones, after the wait and not the 30-second timeout", async () => {
    reads.promises.mockImplementation(never);
    reads.publicOnes.mockImplementation(never);
    const t0 = Date.now();
    expect(await Promise.all([reviewDays(50), landingOnes(50)])).toEqual([null, []]);
    expect(Date.now() - t0).toBeLessThan(1_000);
  });

  it("a read that fails degrades the same way", async () => {
    reads.promises.mockRejectedValue(new Error("promises_unavailable"));
    reads.publicOnes.mockRejectedValue(new Error("ones_unavailable"));
    expect(await reviewDays(50)).toBeNull();
    expect(await landingOnes(50)).toEqual([]);
  });

  it("atMost returns the answer when it is in time, else the fallback", async () => {
    expect(await atMost(async () => "on time", "late", 50)).toBe("on time");
    expect(await atMost(never, "late", 10)).toBe("late");
  });
});
