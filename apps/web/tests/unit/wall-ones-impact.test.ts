// @vitest-environment jsdom
/**
 * S-WALL.ones, L-WALL.ones (J-ONE/3, BLD-E050): the Wall's The Ones shows the five newest Ones, newest first, each
 * card an article with its number, name, tier and brief. S-WALL.impact, L-WALL.impact/2 (J-ONE/2): the live fixes
 * are a table, a row per fix under the four column headers. Rendered on the server, as the page renders it.
 * Synthetic people only.
 */
import { createElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));

const { WallScreen } = await import("@/app/wall/wall-screen");
type Props = Parameters<typeof WallScreen>[0];
type Ones = Extract<Props["data"]["ones"], { ok: true }>["data"];
type Impact = Extract<Props["data"]["impact"], { ok: true }>["data"];

// The worker sends the wall order oldest first (wall/ones.py one_cards)
const PEOPLE: Array<[number, string, number, string, string]> = [
  [15, "Gopal Iyengar", 7, "Star", "Founding One"],
  [2, "Aparna Hegde", 6, "Blue flame", "Founding One"],
  [4, "Rekha Saxena", 4, "Blaze", "Founding One"],
  [8, "Dinesh Kamath", 5, "White heat", "Founding One"],
  [30, "Indira Natarajan", 2, "Glow", "One"],
  [21, "Siddharth Rao", 1, "Spark", "One"],
  [11, "Varun Chopra", 3, "Flame", "One"],
];
const ONES = PEOPLE.map(([number, name, tier, tierName, flag]) => ({
  number,
  person: { id: `p-${number}`, name, first_name: name.split(" ")[0], initials: "XX" },
  tier,
  tier_name: tierName,
  tier_label: `Tier ${tier}, ${tierName}`,
  flag: flag === "One" ? "one" : "founding",
  flag_label: flag,
  brief: number === 11 ? "Stopped wrong bank details before a payout goes out." : "A brief.",
})) as unknown as Ones;

const IMPACT = {
  totals: {
    hours_month: 620,
    money_year: 1800000,
    fixes_measured: 1,
    reached: { count: 58600, noun: "Distributors" },
  },
  tiles: [
    { key: "hours_month", value: "620", suffix: "", label: "Hours saved a month" },
    { key: "money_year", value: "₹18", suffix: "lakh", label: "Saved a year, Finance confirmed" },
    { key: "fixes_measured", value: "1", suffix: "", label: "Fixes shipped and measured" },
    { key: "reached", value: "58,600", suffix: "", label: "Distributors reached by a shipped fix" },
  ],
  live: [
    {
      id: "IDEA-2026-000011",
      what: "Flag likely-wrong bank details before a payout",
      change: "620 hours a month saved; bounced payouts down by a third",
      measured: "30d",
      measured_label: "30 days",
      due: null,
      team: "Payout checks team",
    },
  ],
} as unknown as Impact;

function wall(order: "wall" | "leaderboard" = "wall"): HTMLElement {
  const html = renderToStaticMarkup(
    createElement(WallScreen, {
      state: { kind: "all", sort: "newest", more: 0, ones: order, at: null, dy: null },
      data: {
        kindling: { ok: false, paused: null },
        justIn: { ok: false, paused: null },
        ones: { ok: true, data: ONES },
        impact: { ok: true, data: IMPACT },
        ember: { ok: false, paused: null },
      },
    }),
  );
  const host = document.createElement("div");
  host.innerHTML = html;
  return host;
}

describe("S-WALL.ones, L-WALL.ones (J-ONE/3, BLD-E050): the five newest Ones, newest first", () => {
  it("draws five cards, each an article in the list, the newest One first", () => {
    const host = wall();
    const cards = [...host.querySelectorAll('ul[aria-label="The Ones"] > li > article')];
    expect(cards.map((c) => c.querySelector("h3")?.textContent)).toEqual([
      "Varun Chopra",
      "Siddharth Rao",
      "Indira Natarajan",
      "Dinesh Kamath",
      "Rekha Saxena",
    ]);
    expect(cards[0]?.textContent).toContain("Number 11");
    expect(cards[0]?.textContent).toContain("Tier 3, Flame");
    expect(cards[0]?.textContent).toContain("Stopped wrong bank details before a payout goes out.");
  });

  it("the leaderboard keeps every One in the worker's order", () => {
    const host = wall("leaderboard");
    expect(host.querySelectorAll('ul[aria-label="The Ones"] article')).toHaveLength(7);
  });
});

describe("S-WALL.impact, L-WALL.impact/2 (J-ONE/2): the live fixes are a table", () => {
  it("has the four column headers and a row per fix with its cells", () => {
    const host = wall();
    const table = host.querySelector('[role="table"][aria-label="Live fixes and their measured change"]')!;
    expect([...table.querySelectorAll('[role="columnheader"]')].map((h) => h.textContent)).toEqual([
      "Live fix",
      "Measured change",
      "Measured",
      "Team that runs it",
    ]);
    const rows = [...table.querySelectorAll('[role="rowgroup"] + [role="rowgroup"] > [role="row"]')];
    expect(rows).toHaveLength(1);
    expect([...(rows[0]?.querySelectorAll('[role="cell"]') ?? [])].map((c) => c.textContent)).toEqual([
      "Flag likely-wrong bank details before a payout",
      "620 hours a month saved; bounced payouts down by a third",
      "30 days",
      "Payout checks team",
    ]);
    expect(rows[0]?.getAttribute("data-row")).toBe("imp-IDEA-2026-000011");
  });
});
