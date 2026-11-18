// @vitest-environment jsdom
/**
 * S-03's crew card (C-CREW-DECK.card, F-TYPE; BLD-C186): the hue sits on the card's top block, not the whole card,
 * as Home.dc.html:287-289 and PhoneHome.dc.html:289-291 draw `.pc-top.hue1` and `.pc-top.hue2`. The card carries
 * `hue1` or `hue2` (lane D's d/crew-hue, BLD-D015; these checks fail until it is on main, so the hue can never
 * silently not show) and its top block takes the board's gradient from home.css. jsdom applies
 * no stylesheet, so the rules are read from the file; the look itself is checked by lane G's walk. Synthetic data.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import { CrewCardView } from "@/app/home/crew-card";
import type { CrewCard, PersonRef } from "@/lib/contracts";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const person = (id: string, name: string, initials: string) => ({ id, name, initials }) as PersonRef;
const card = (hue: 1 | 2) =>
  ({
    id: "IDEA-2026-001490",
    title: "Synthetic: message codes confuse investors",
    status: "with_review_desk",
    area: "Investor service",
    city: "Hyderabad",
    shared_at: "2026-11-14T06:00:00.000Z",
    lead: person("p-1", "Ravi Nair", "RN"),
    crew_faces: [person("p-2", "Asha Shetty", "AS")],
    crew_count: 2,
    in_their_words: "Investors get a code, not a reason, and then they call us.",
    hue,
    reason_kind: "close_to_yours",
    reason: "Same code as your idea from Saturday",
  }) as CrewCard;

const css = (file: string) => readFileSync(path.resolve(__dirname, "../../src/app", file), "utf8");
/** The declarations of one rule, whitespace folded. */
function rule(sheet: string, selector: string): string {
  const at = sheet.indexOf(`${selector} {`);
  expect(at, `${selector} in the stylesheet`).toBeGreaterThan(-1);
  return sheet
    .slice(at + selector.length + 2, sheet.indexOf("}", at))
    .replace(/\s+/g, " ")
    .trim();
}

/** The board's stops (Home.dc.html:288-289), as prettier writes them. */
const STOPS = {
  1: "radial-gradient(120% 150% at 0% 0%, rgba(57, 93, 237, 0.2), rgba(57, 93, 237, 0) 60%), radial-gradient(120% 150% at 100% 0%, rgba(244, 104, 53, 0.16), rgba(244, 104, 53, 0) 60%), #ffffff;",
  2: "radial-gradient(120% 150% at 0% 0%, rgba(146, 128, 255, 0.24), rgba(146, 128, 255, 0) 60%), radial-gradient(120% 150% at 100% 0%, rgba(57, 93, 237, 0.14), rgba(57, 93, 237, 0) 60%), #ffffff;",
} as const;

let host: HTMLDivElement;
let root: Root;

afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

function render(hue: 1 | 2) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  act(() => root.render(createElement(CrewCardView, { card: card(hue), onTeamUp: () => undefined })));
  return host.querySelector(".hm-pcard")!;
}

describe("S-03 crew card hue on the top block (C-CREW-DECK.card, F-TYPE; BLD-C186)", () => {
  for (const hue of [1, 2] as const) {
    it(`hue ${hue}: the card carries hue${hue}, and its top block is the first block with the status and title`, () => {
      const el = render(hue);
      expect(el.classList.contains(`hue${hue}`)).toBe(true);
      expect(el.classList.contains(`hue${3 - hue}`)).toBe(false);
      const top = el.querySelector(`:scope.hue${hue} > .hm-pc-top`);
      expect(top).not.toBeNull();
      expect(el.firstElementChild).toBe(top);
      expect(top!.textContent).toContain("With the review desk");
      expect(top!.querySelector("h3")!.textContent).toBe("Synthetic: message codes confuse investors");
    });

    it(`hue ${hue}: home.css paints .hm-pcard.hue${hue} .hm-pc-top with the board's stops`, () => {
      expect(rule(css("home/home.css"), `.hm-pcard.hue${hue} .hm-pc-top`)).toBe(`background: ${STOPS[hue]}`);
    });
  }

  it("the top block runs edge to edge with its own padding and border; the rest keeps the card's padding", () => {
    const home = css("home/home.css");
    expect(rule(home, ".hm-pc-top")).toContain("margin: 0 -22px; padding: 22px 22px 20px;");
    expect(rule(home, ".hm-pc-top")).toContain("border-bottom: 1px solid rgba(17, 17, 17, 0.06);");
    expect(rule(home, ".hm-pcard")).toContain("padding: 0 22px 20px;");
    expect(rule(home, ".hm-pcard")).toContain("overflow: hidden;");
  });

  it("lane F's S-H2 card (.crew-top.hue1/.hue2) carries the same stops", () => {
    const crew = css("crew/crew.css");
    for (const hue of [1, 2] as const)
      expect(rule(crew, `.crew-top.hue${hue}`)).toBe(`background: ${STOPS[hue]}`);
  });
});
