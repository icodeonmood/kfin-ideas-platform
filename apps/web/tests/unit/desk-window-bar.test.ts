import { describe, expect, it } from "vitest";

import type { CommitteeRow } from "@/lib/contracts";
import { windowBar } from "@/lib/desk/window-bar";

type W = Pick<
  CommitteeRow["window"],
  "state" | "opens_at" | "closes_at" | "max_closes_at" | "extended_times"
>;

// A desk decision on Monday 16 November 2026 at 10:30 office time: 30 days to Wednesday 16 December, at most to
// Tuesday 16 February 2027 (92 days in all). Synthetic dates only.
const fresh: W = {
  state: "open",
  opens_at: "2026-11-16T05:00:00Z",
  closes_at: "2026-12-16T05:00:00Z",
  max_closes_at: "2027-02-16T05:00:00Z",
  extended_times: 0,
};

describe("S-R4 window bar (Committee board view(): Your window)", () => {
  it("S-R4 window bar: while open the fill is the time used out of the full 3 months", () => {
    expect(windowBar(fresh, new Date("2026-11-24T05:00:00Z"))).toEqual({
      tone: "open",
      fill: 8.7,
      ext: null,
    });
  });

  it("S-R4 window bar: amber at 7 days or fewer left, counted in office calendar days", () => {
    expect(windowBar(fresh, new Date("2026-12-08T05:00:00Z")).tone).toBe("open"); // 8 days left
    expect(windowBar(fresh, new Date("2026-12-09T05:00:00Z")).tone).toBe("soon"); // 7 days left
    // 00:30 on 9 December in India is still 8 December in UTC: the office day decides.
    expect(windowBar(fresh, new Date("2026-12-08T19:00:00Z")).tone).toBe("soon");
    expect(windowBar(fresh, new Date("2026-12-16T02:00:00Z")).tone).toBe("soon"); // closes today
  });

  it("S-R4 window bar: an extended window hatches from 30 days to its new close", () => {
    // Decided Monday 12 October, extended once to Friday 11 December; 3 months runs to Tuesday 12 January 2027.
    const w: W = {
      state: "extended",
      opens_at: "2026-10-12T05:00:00Z",
      closes_at: "2026-12-11T05:00:00Z",
      max_closes_at: "2027-01-12T05:00:00Z",
      extended_times: 1,
    };
    expect(windowBar(w, new Date("2026-11-24T05:00:00Z"))).toEqual({
      tone: "open",
      fill: 46.7, // 43 of 92 days
      ext: { left: 32.6, width: 32.6 }, // day 30 to day 60
    });
  });

  it("S-R4 window bar: expired and reversed windows fill to their close, grey and ink", () => {
    const expired: W = {
      state: "expired",
      opens_at: "2026-10-19T05:00:00Z",
      closes_at: "2026-11-18T05:00:00Z",
      max_closes_at: "2027-01-19T05:00:00Z",
      extended_times: 0,
    };
    expect(windowBar(expired, new Date("2026-11-24T05:00:00Z"))).toEqual({
      tone: "done",
      fill: 32.6,
      ext: null,
    });
    const reversed: W = { ...expired, state: "reversed" };
    expect(windowBar(reversed, new Date("2026-11-10T05:00:00Z"))).toEqual({
      tone: "rev",
      fill: 32.6,
      ext: null,
    });
  });

  it("S-R4 window bar: every value stays between 0 and 100", () => {
    expect(windowBar(fresh, new Date("2026-11-01T05:00:00Z")).fill).toBe(0); // before the decision
    expect(windowBar(fresh, new Date("2027-03-01T05:00:00Z")).fill).toBe(100); // after the limit
    const atLimit: W = { ...fresh, state: "extended", closes_at: fresh.max_closes_at, extended_times: 2 };
    const bar = windowBar(atLimit, new Date("2027-02-10T05:00:00Z"));
    expect(bar.ext).toEqual({ left: 32.6, width: 67.4 });
    expect(bar.ext!.left + bar.ext!.width).toBeLessThanOrEqual(100);
    const empty: W = { ...fresh, max_closes_at: fresh.opens_at };
    expect(windowBar(empty, new Date("2026-11-24T05:00:00Z")).fill).toBe(100);
  });
});
