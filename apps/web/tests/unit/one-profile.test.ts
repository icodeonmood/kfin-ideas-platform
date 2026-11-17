/**
 * S-ONE and S-H6, the screens' own rules (lane E): the number and brief fields as V-FIELDS.one has them, the figures'
 * split for Impact so far, the count-up's reading of a figure, and Profile's words and switches (Profile.md, L-NOTIFY).
 */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import OneLoading from "@/app/one/loading";
import {
  briefProblem,
  LOAD_FAILED as ONE_FAILED,
  MSG_BRIEF,
  splitFigure,
  wholeNumber,
} from "@/app/one/rules";
import { OneUnavailable } from "@/app/one/unavailable";
import ProfileLoading from "@/app/profile/loading";
import {
  isReferAs,
  LOAD_FAILED as PROFILE_FAILED,
  pointsText,
  REACH,
  REFER_AS_OPTIONS,
  switchState,
  WALL_LINE,
} from "@/app/profile/rules";
import { ProfileUnavailable } from "@/app/profile/unavailable";
import { figureParts } from "@/components/count-once";

describe("V-FIELDS.one S-ONE: the number and the brief", () => {
  it("V-FIELDS.one/1: a whole number from 1 to 999", () => {
    expect(wholeNumber("1")).toBe(1);
    expect(wholeNumber(" 77 ")).toBe(77);
    expect(wholeNumber("999")).toBe(999);
    for (const bad of ["0", "1000", "-3", "7.5", "seven", "", "12a", "0012"])
      expect(wholeNumber(bad)).toBeNull();
  });

  it("V-FIELDS.one/4: one sentence of 20 to 140 characters, spaces collapsed as the worker does", () => {
    expect(briefProblem("Online forms that fill the city from the pin code.")).toBeNull();
    expect(briefProblem("Too short.")).toBe(MSG_BRIEF);
    expect(briefProblem("x".repeat(141))).toBe(MSG_BRIEF);
    expect(briefProblem("Branches stopped calling us. Investors are happier now too.")).toBe(MSG_BRIEF);
    expect(briefProblem(`  Wrong bank details are   caught before the first debit.  `)).toBeNull();
  });
});

describe("S-ONE.layout/5: Impact so far", () => {
  it("splits a figure into the big number and its words", () => {
    expect(splitFigure("620 hours a month")).toEqual({ big: "620", unit: "hours a month" });
    expect(splitFigure("₹18 lakh a year")).toEqual({ big: "₹18", unit: "lakh a year" });
    expect(splitFigure("₹6.2 lakh a year")).toEqual({ big: "₹6.2", unit: "lakh a year" });
    expect(splitFigure("3 fewer steps")).toEqual({ big: "3", unit: "fewer steps" });
    expect(splitFigure("58,600 distributors")).toEqual({ big: "58,600", unit: "distributors" });
    expect(splitFigure("41")).toEqual({ big: "41", unit: "" });
    expect(splitFigure("About a third")).toEqual({ big: "About a third", unit: "" });
  });

  it("F-MOTION.arrive/5: the count-up reads the digits, keeps the rupee sign, the grouping and the decimals", () => {
    expect(figureParts("620")).toEqual({ pre: "", n: 620, post: "", grouped: false, decimals: 0 });
    expect(figureParts("₹18")).toEqual({ pre: "₹", n: 18, post: "", grouped: false, decimals: 0 });
    expect(figureParts("58,600")).toEqual({ pre: "", n: 58600, post: "", grouped: true, decimals: 0 });
    expect(figureParts("₹6.2")).toEqual({ pre: "₹", n: 6.2, post: "", grouped: false, decimals: 1 });
    expect(figureParts("About a third")).toBeNull();
  });
});

describe("S-H6: Profile's words and switches", () => {
  it("S-H6.layout/3: the Wall switch's line follows its state, word for word", () => {
    expect(WALL_LINE.on).toBe(
      "Your name shows on the Wall next to your shared ideas. It applies to every idea you share, and you can change it here any time.",
    );
    expect(WALL_LINE.off).toBe(
      "Your ideas show on the Wall without your name. It applies to every idea you share, and you can change it here any time.",
    );
  });

  it("S-H6.layout/4, L-NOTIFY/2: Teams, Email and Reminders, in that order", () => {
    expect(REACH.map((r) => r.title)).toEqual([
      "Teams messages",
      "Email",
      "Reminders before a question is due",
    ]);
    expect(REACH.map((r) => r.line)).toEqual([
      "When the review desk asks you something, or one of your ideas moves a stage.",
      "The same updates, for your records.",
      "A day before, and again two hours before.",
    ]);
  });

  it("S-H6.rules/1: a save's answer counts only when it carries that switch as a boolean", () => {
    expect(switchState({ email: false }, "email")).toBe(false);
    expect(switchState({ teams: true }, "teams")).toBe(true);
    expect(switchState({}, "reminders")).toBeUndefined();
    expect(switchState(null, "show_name_on_wall")).toBeUndefined();
  });

  it("DEC-108: she, he, they and Prefer not to say, sent as lane C's wire values", () => {
    expect(REFER_AS_OPTIONS.map((o) => [o.value, o.label])).toEqual([
      ["she", "She"],
      ["he", "He"],
      ["they", "They"],
      ["unset", "Prefer not to say"],
    ]);
    expect(isReferAs("they")).toBe(true);
    expect(isReferAs(null)).toBe(false);
    expect(isReferAs("Female")).toBe(false);
  });

  it("S-H6.layout/2: points in the Indian grouping", () => {
    expect(pointsText(340)).toBe("340");
    expect(pointsText(125000)).toBe("1,25,000");
  });
});

describe("S-ONE and S-H6 loading and error states (C-SKELETON, F-COPY.states)", () => {
  const html = (c: () => unknown) => renderToStaticMarkup(createElement(c as () => null));

  it("S-ONE.states: loading shows bars and one polite line, never a full-screen loader", () => {
    const out = html(OneLoading);
    expect(out).toContain('aria-busy="true"');
    expect(out).toContain('role="status"');
    expect(out).toContain("Loading your One dashboard");
  });

  it("S-ONE.states: a dashboard that cannot be read says so and offers Try again", () => {
    const out = html(OneUnavailable);
    expect(ONE_FAILED).toBe("We can't load your One dashboard just now. Please try again in a minute.");
    expect(out).toContain("We can&#x27;t load your One dashboard just now. Please try again in a minute.");
    expect(out).toContain('<a href="/one" class="btn btn-secondary">Try again</a>');
    expect(out).toContain('aria-current="page"');
  });

  it("S-H6.states: loading shows bars and one polite line", () => {
    const out = html(ProfileLoading);
    expect(out).toContain('aria-busy="true"');
    expect(out).toContain("Loading your profile");
  });

  it("S-H6.states: a profile that cannot be read says so and offers Try again", () => {
    const out = html(ProfileUnavailable);
    expect(PROFILE_FAILED).toBe("We can't load your profile just now. Please try again in a minute.");
    expect(out).toContain('<h1 class="pf-t">Profile and settings</h1>');
    expect(out).toContain('<a href="/profile" class="btn btn-secondary">Try again</a>');
  });
});
