/**
 * The states S-07 and S-09 list that the seed cannot show in a browser: My ideas when its list cannot load, and a
 * colleague's idea that was withdrawn (BLD-E011). Rendered on the server, as the pages render them. Synthetic data.
 */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: () => undefined, push: () => undefined, refresh: () => undefined }),
  usePathname: () => "/my-ideas",
}));

import { ColleagueScreen } from "@/app/ideas/[id]/colleague-screen";
import { MyIdeasScreen } from "@/app/my-ideas/my-ideas-screen";
import type { ColleagueView } from "@/lib/contracts/api";

describe("S-07.states: the list cannot load", () => {
  it("keeps the title and says so in one alert, with nothing else to act on", () => {
    const html = renderToStaticMarkup(createElement(MyIdeasScreen, { data: null }));
    expect(html).toContain(">My ideas</h1>");
    expect(html).toMatch(/role="alert"/);
    expect(html).toContain("We can&#x27;t load your ideas just now. Please try again in a minute.");
    expect(html).not.toContain('role="tablist"');
  });
});

describe("S-09.rules/2, BLD-E011: a withdrawn idea for someone who was on its crew", () => {
  it("shows its reference and one line: no title, summary, crew or track", () => {
    const view = {
      view: "colleague",
      screen: "S-09",
      idea: { id: "IDEA-2026-900001", ref: "IDEA-2026-900001", status: "withdrawn" },
      page: {
        state: "withdrawn",
        back: { from: "my-ideas", label: "Back to My ideas", to: "/my-ideas?list=teamed" },
        pill: { status: "withdrawn", label: "Withdrawn", variant: "neutral" },
        team_up: {
          state: "withdrawn",
          line: "The person who shared it withdrew it, so nobody else can see it now.",
          can_team_up: false,
        },
      },
    } as unknown as ColleagueView;
    const html = renderToStaticMarkup(createElement(ColleagueScreen, { view }));
    expect(html).toContain(">IDEA-2026-900001</h1>");
    expect(html).toContain("The person who shared it withdrew it, so nobody else can see it now.");
    expect(html).toContain('href="/my-ideas?list=teamed"');
    expect(html).not.toContain("Where it is");
    expect(html).not.toContain("Team up on this idea");
  });
});
