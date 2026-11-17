import { describe, expect, it } from "vitest";

import { answerDue, clockLabel, dayLabel, deadlineLabel } from "@/lib/desk/when";

const NOW = new Date("2026-11-16T11:20:00+05:30");

describe("review side dates in the browser (twin of desk/when.py and clock.answer_due)", () => {
  it("days, clocks and deadlines read as on the boards", () => {
    expect(dayLabel("2026-11-20T18:00:00+05:30", NOW)).toBe("Friday 20 November");
    expect(dayLabel("2027-02-16T16:58:00+05:30", NOW)).toBe("Tuesday 16 February 2027");
    expect(clockLabel("2026-11-16T12:05:00+05:30")).toBe("12:05 pm");
    expect(clockLabel("2026-11-16T00:00:00+05:30")).toBe("12 am");
    expect(deadlineLabel("2026-11-16T19:00:00+05:30", NOW)).toBe("7 pm today");
    expect(deadlineLabel("2026-11-17T18:00:00+05:30", NOW)).toBe("6 pm tomorrow");
    expect(deadlineLabel("2026-11-19T18:00:00+05:30", NOW)).toBe("Thursday 19 November, 6 pm");
  });

  it("L-QUESTIONS.clock/5 deadlines match the worker's", () => {
    expect(answerDue(NOW, "3d").toISOString()).toBe(new Date("2026-11-19T18:00:00+05:30").toISOString());
    expect(answerDue(NOW, "1w").toISOString()).toBe(new Date("2026-11-23T18:00:00+05:30").toISOString());
    expect(answerDue(NOW, "1d").toISOString()).toBe(new Date("2026-11-17T11:20:00+05:30").toISOString());
    // late at night in India is still the same office day
    const late = new Date("2026-11-16T23:30:00+05:30");
    expect(answerDue(late, "3d").toISOString()).toBe(new Date("2026-11-19T18:00:00+05:30").toISOString());
  });
});
