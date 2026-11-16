/**
 * The launch surfaces' pure parts: the office screen (S-OFFICE, L-DISPLAY.office), "Share another way" (S-H3)
 * and "What happens after you share" (S-H4). Synthetic Ones only.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  countLine,
  digitsOf,
  dustField,
  flagWords,
  headlineFigure,
  lightLabel,
  lightSize,
  officeOrder,
  placeInSky,
  position,
  secondsPerOne,
  sparkShape,
  starStyle,
  tierLine,
  type PublicOneInput,
} from "@/lib/display";
import { stages } from "@/lib/how-it-works";
import { can, canSeePage, decide, effectiveRoles } from "@/lib/rbac";

const one = (over: Partial<PublicOneInput>): PublicOneInput => ({
  number: 17,
  induction_no: 2,
  name: "Synthetic Person",
  founding: false,
  tier: 2,
  tier_name: "Glow",
  tier_colour: "#FF4313",
  brief: "Distributors see why a registration is stuck.",
  measures: { time: { value: 620, unit: "hours a month" } },
  ...over,
});

describe("S-OFFICE: the office screen (L-DISPLAY.office)", () => {
  it("S-OFFICE/2: rotates in induction order, Founding Ones first, and skips a One without a number", () => {
    const list = officeOrder([
      one({ number: 17, induction_no: 3 }),
      one({ number: 1, induction_no: 1, founding: true, name: "Founding Synthetic" }),
      one({ number: null, induction_no: 2 }),
    ]);
    expect(list.map((o) => o.number)).toEqual([1, 17]);
    expect(list[0]).toMatchObject({ flag: "founding", first_name: "Founding" });
    expect(flagWords(list[0]!.flag)).toBe("Founding One");
    expect(flagWords(list[1]!.flag)).toBe("One");
  });

  it("S-OFFICE/2: the label, the tier line, the count and the position, in the board's words", () => {
    const [o] = officeOrder([
      one({ number: 1, induction_no: 1, name: "Rohit Synthetic", tier: 4, tier_name: "Blaze" }),
    ]);
    expect(lightLabel(o!)).toBe("No. 1 · Rohit");
    expect(tierLine(o!)).toBe("Tier 4 · Blaze");
    expect(countLine(7)).toBe("7 Ones so far. Each one shipped something that changed how we work.");
    expect(countLine(1)).toBe("1 One so far. Each one shipped something that changed how we work.");
    expect(position(0, 7)).toBe("1 of 7");
  });

  it("names nobody who has not said yes: the light reads 'No. 17' alone", () => {
    const [o] = officeOrder([one({ name: null })]);
    expect(o!.first_name).toBeNull();
    expect(lightLabel(o!)).toBe("No. 17");
  });

  it("the headline figure is the first measure, as a sentence; none without one", () => {
    expect(headlineFigure({ time: { value: 620, unit: "hours a month" } })).toBe(
      "620 hours a month given back.",
    );
    expect(headlineFigure({ scale: { value: 4, unit: "teams use it" } })).toBe("4 teams use it.");
    expect(headlineFigure({})).toBeNull();
    expect(headlineFigure(null)).toBeNull();
  });

  it("S-OFFICE/3: seconds per One is 4 to 20, default 8; the background is sparks unless dots are asked for", () => {
    expect(secondsPerOne(undefined)).toBe(8);
    expect(secondsPerOne("12")).toBe(12);
    expect(secondsPerOne("1")).toBe(4);
    expect(secondsPerOne("99")).toBe(20);
    expect(secondsPerOne("soon")).toBe(8);
    expect(starStyle(undefined)).toBe("sparks");
    expect(starStyle("dots")).toBe("dots");
    expect(starStyle(["dots", "sparks"])).toBe("dots");
  });

  it("a One's light keeps its place (DEC-039) inside the field the words leave clear", () => {
    for (let n = 1; n < 200; n++) {
      const at = placeInSky(n);
      expect(at.x).toBeGreaterThanOrEqual(44);
      expect(at.x).toBeLessThanOrEqual(92);
      expect(at.y).toBeGreaterThanOrEqual(18);
      expect(at.y).toBeLessThanOrEqual(68);
      expect(placeInSky(n)).toEqual(at);
    }
    expect(sparkShape(5)).toEqual(sparkShape(5));
    expect(sparkShape(5).points).toMatch(/^10\.0,92\.0 /);
  });

  it("the current One's light is the brightest, in both styles", () => {
    expect(lightSize("sparks", 4, true)).toMatchObject({ box: 96, halo: 132, opacity: 1 });
    expect(lightSize("sparks", 4, false)).toMatchObject({ box: 64, opacity: 0.8 });
    expect(lightSize("dots", 4, true)).toMatchObject({ box: 30, halo: 72 });
    expect(lightSize("dots", 4, false).box).toBe(18);
  });

  it("the counter rolls each digit; the dust is the same 90 stars every time", () => {
    expect(digitsOf(1)).toEqual([1]);
    expect(digitsOf(217)).toEqual([2, 1, 7]);
    expect(dustField()).toHaveLength(90);
    expect(dustField()).toEqual(dustField());
  });
});

describe("L-DISPLAY: who may open a display (BLD-A190)", () => {
  const roles = (role?: string) => effectiveRoles(role ? [{ role, scope_id: null }] : []);
  it("the display role and admins, nobody else", () => {
    expect(can(roles("display"), "open_display")).toBe(true);
    expect(can(roles("admin"), "open_display")).toBe(true);
    for (const r of [undefined, "reviewer", "core_committee", "infosec", "hr", "ceo"]) {
      expect(can(roles(r), "open_display")).toBe(false);
    }
  });
  it("covers both screens and the office data", () => {
    expect(canSeePage(roles("display"), "/display/launch")).toBe(true);
    expect(canSeePage(roles("display"), "/display/office")).toBe(true);
    expect(canSeePage(roles(), "/display/office")).toBe(false);
    expect(decide(roles("display"), "GET", "/api/display/office").kind).toBe("allow");
    expect(decide(roles(), "GET", "/api/display/office").kind).toBe("deny");
    // the older /launch stays admin only until lane E retires it
    expect(canSeePage(roles("display"), "/launch")).toBe(false);
  });
  it("S-H3 and S-H4 are for everyone signed in", () => {
    expect(canSeePage(roles(), "/share/other-ways")).toBe(true);
    expect(canSeePage(roles(), "/how-it-works")).toBe(true);
    expect(decide(roles(), "POST", "/api/me/app-news").kind).toBe("allow");
  });
});

describe("S-H4: the stages and their promises", () => {
  it("S-H4/1: five stages in order, with the review promise from configuration (S-H4/3)", () => {
    const s = stages(5);
    expect(s.map((x) => x.title)).toEqual(["Shared", "Checked and matched", "Reviewed", "Built", "Shipped"]);
    expect(s.map((x) => x.when)).toEqual([
      "About two minutes",
      "Automatic, minutes",
      "Within 5 working days",
      "Depends on the fix",
      "After it’s live",
    ]);
    expect(stages(7)[2]!.when).toBe("Within 7 working days");
    expect(stages(1)[2]!.when).toBe("Within 1 working day");
  });
});

describe("S-H3: the other ways in stay closed until IT gives their addresses", () => {
  afterEach(() => {
    vi.resetModules();
    vi.doUnmock("@/server/killswitch");
  });

  it("takes a well-formed mailbox and an https Teams link only", async () => {
    const { intakeAddresses } = await import("@/server/ways");
    expect(intakeAddresses({})).toEqual({ address: null, link: null });
    expect(
      intakeAddresses({
        INTAKE_EMAIL_ADDRESS: "1pc@example.test",
        TEAMS_APP_LINK: "https://teams.example.test/l/app/1",
      }),
    ).toEqual({ address: "1pc@example.test", link: "https://teams.example.test/l/app/1" });
    expect(
      intakeAddresses({ INTAKE_EMAIL_ADDRESS: "[1% Club address]", TEAMS_APP_LINK: "javascript:alert(1)" }),
    ).toEqual({ address: null, link: null });
  });

  it("DEC-105: a way is open only with its switch on and its address given; an unknown switch is off", async () => {
    let states = new Map<string, "on" | "off">();
    vi.doMock("@/server/killswitch", () => ({
      switchStates: async () => states,
      isOn: (s: Map<string, string>, name: string) => s.get(name) === "on",
    }));
    const { channels } = await import("@/server/ways");
    vi.stubEnv("INTAKE_EMAIL_ADDRESS", "1pc@example.test");
    vi.stubEnv("TEAMS_APP_LINK", "https://teams.example.test/l/app/1");
    try {
      expect(await channels()).toMatchObject({ email: { on: false }, teams: { on: false } });
      states = new Map([
        ["intake.email", "on"],
        ["intake.teams", "off"],
      ]);
      expect(await channels()).toMatchObject({ email: { on: true }, teams: { on: false } });
      vi.stubEnv("INTAKE_EMAIL_ADDRESS", "");
      expect((await channels()).email.on).toBe(false);
    } finally {
      vi.unstubAllEnvs();
    }
  });
});
