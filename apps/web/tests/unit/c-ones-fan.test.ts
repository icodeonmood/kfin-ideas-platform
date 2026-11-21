// @vitest-environment jsdom
/**
 * C-ONES-FAN rebuilt to Home.dc.html's static look (BLD-D020): the card (C-ONES-FAN.card), the three states and the
 * stack's side panel (C-ONES-FAN.states), the tier colours from the tokens (F-COLOR.tiers, so BLD-D023's swap of
 * tiers 6 and 7 follows), the board's greys measured on the slab (F-COLOR.contrast), 44px targets named by their
 * visible words (F-A11Y), and a still pose with a flat offset under reduced motion (F-MOTION.reduced). The moving
 * parts (Previous and Next, ← →, the wheel) keep their own tests in vacc-teamup.test.ts and s03-home.test.ts.
 * BLD-D026 adds the motion between those poses (motion.css: the fly-out, the edge straightening, the hover, the side
 * panel's exit, cheerPop) and the phone row's native snap; components.css keeps the look at rest and no animation.
 * Synthetic people only.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { act, createElement as h, useState, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { applied, cssRules, keyframes, SRC, type CssRule } from "./helpers/css-rules";

vi.mock("next/link", async () => {
  const { createElement } = await import("react");
  return {
    default: ({ href, children, ...rest }: { href: string; children?: ReactNode }) =>
      createElement("a", { href, ...rest }, children),
  };
});

const { FAN_FINE, FAN_FLY, FAN_MOTION, FAN_PHONE, OnesEmpty, OnesFan, OnesNext, OnesPost, ONES_FAN_COPY } =
  await import("@/components/ui/ones-fan");

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLElement;
let root: Root;

beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

function show(node: ReactNode) {
  act(() => root.render(node));
}

const words = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();

type PostSeed = { n: number; t: number; tn: string; who: string | null; i: string; adopted?: string };
const POSTS: PostSeed[] = [
  { n: 1, t: 4, tn: "Blaze", who: "Asha Shetty", i: "AS", adopted: "Adopted by 3 teams" },
  { n: 17, t: 2, tn: "Glow", who: null, i: "" },
  { n: 5, t: 6, tn: "Blue flame", who: "Imran Qureshi", i: "IQ" },
  { n: 9, t: 5, tn: "White heat", who: "Neha Kapoor", i: "NK" },
  { n: 12, t: 7, tn: "Star", who: "Kiran Das", i: "KD" },
];

function post(p: PostSeed, extra: { cheered?: boolean; onCheer?: () => void } = {}) {
  return h(OnesPost, {
    key: p.n,
    name: p.who,
    initials: p.i,
    number: p.n,
    tier: p.t,
    tierName: p.tn,
    ago: "2d",
    sentence:
      "Synthetic: wrong bank details are now caught before the first SIP debit, not after it bounces.",
    adopted: p.adopted,
    figure: "1,240",
    unit: "failed debits avoided last quarter",
    cheers: 214,
    cheered: extra.cheered ?? false,
    onCheer: extra.onCheer ?? (() => undefined),
    replies: 18,
    threadHref: "/ideas/IDEA-2026-001400/conversation",
  });
}

const NEXT = h(OnesNext, {
  title: "The next One could be you",
  body: "Every fix here started with one person saying what kept going wrong.",
  action: "Share a problem",
  href: "/share",
});

function fan(count: number, people?: number) {
  show(
    h(OnesFan, {
      label: "The Ones",
      cards: POSTS.slice(0, count).map((p) => post(p)),
      empty: h(OnesEmpty, {
        title: "No Ones yet",
        body: "When a shared fix ships and its result is measured, the people behind it are posted here first.",
      }),
      companion: NEXT,
      people,
    }),
  );
  return host.querySelector<HTMLElement>('[role="region"]');
}

const cards = () => [...host.querySelectorAll<HTMLElement>(".fan-card")];
const position = () => words(host.querySelector(".fan-pos"));

// =================================================================================================================
describe("C-ONES-FAN.card: a One's post on the slab, as Home.dc.html draws .ocard (BLD-D020)", () => {
  it("C-ONES-FAN.card: header with the tier-ringed avatar, the name, 'One No. 1, Tier 4, Blaze' and when", () => {
    show(post(POSTS[0]!));
    const card = host.querySelector("article.opost")!;
    expect(card.getAttribute("data-tier")).toBe("4");
    const av = card.querySelector(".opost-h .av")!;
    expect(av.className).toContain("opost-av");
    expect(av.className).toContain("av-ring av-t4"); // C-AVATAR.ring/2: the tier ring, F-COLOR.tiers/1 allows it here
    expect(av.getAttribute("aria-hidden")).toBe("true"); // the name is beside it
    expect(words(card.querySelector(".opost-who b"))).toBe("Asha Shetty");
    expect(words(card.querySelector(".opost-who > span"))).toBe("One No. 1, Tier 4, Blaze");
    expect(words(card.querySelector(".opost-ago"))).toBe("2d");
  });

  it("C-ONES-FAN.card: a One who keeps their name off shows as 'One No. 17', the number in the disc", () => {
    show(post(POSTS[1]!));
    expect(words(host.querySelector(".opost-who b"))).toBe("One No. 17");
    expect(words(host.querySelector(".opost-who > span"))).toBe("Tier 2, Glow");
    expect(words(host.querySelector(".opost-av"))).toBe("17");
  });

  it("C-ONES-FAN.card: the sentence, then the media block: Shipped, Adopted by, the big figure, its unit line", () => {
    show(post(POSTS[0]!));
    expect(words(host.querySelector(".opost-s"))).toMatch(/^Synthetic: wrong bank details/);
    const media = host.querySelector(".opost-m")!;
    const tags = [...media.querySelectorAll(".opost-tags .opost-tag")];
    expect(tags.map(words)).toEqual(["Shipped", "Adopted by 3 teams"]);
    expect(tags[0]!.classList.contains("ok")).toBe(true);
    expect(media.querySelector(".opost-big")!.classList.contains("num")).toBe(true); // tabular figures
    expect(words(media.querySelector(".opost-big"))).toBe("1,240");
    expect(words(media.querySelector(".opost-unit"))).toBe("failed debits avoided last quarter");
    // No adoption: Shipped alone
    show(post(POSTS[2]!));
    expect([...host.querySelectorAll(".opost-tag")].map(words)).toEqual(["Shipped"]);
  });

  it("C-ONES-FAN.card: footer, Cheer on the left (a toggle with the count), Read the thread with replies on the right", () => {
    const onCheer = vi.fn();
    show(post(POSTS[0]!, { cheered: true, onCheer }));
    const foot = host.querySelector(".opost-f")!;
    const [cheer, thread] = [...foot.children];
    expect(cheer!.tagName).toBe("BUTTON");
    expect(cheer!.className).toBe("opost-cheer"); // the existing cheer, wired to Home's onCheer
    expect(cheer!.getAttribute("aria-pressed")).toBe("true");
    expect(words(cheer)).toBe("Cheer Asha Shetty’s fix, 214 cheers"); // reference/copy/Home.md
    // The board's heart, filled when pressed (by CSS, below)
    expect(cheer!.querySelector("svg path")!.getAttribute("d")).toBe(
      "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z",
    );
    act(() => (cheer as HTMLButtonElement).click());
    expect(onCheer).toHaveBeenCalledOnce();
    expect(thread!.tagName).toBe("A");
    expect(thread!.getAttribute("href")).toBe("/ideas/IDEA-2026-001400/conversation");
    expect(words(thread)).toBe("Read the thread 18");
    expect(words(thread!.querySelector(".opost-n"))).toBe("18");
  });
});

// =================================================================================================================
describe("C-ONES-FAN.states: none, one with the companion card, several stacked with the side panel (BLD-D020)", () => {
  it("C-ONES-FAN.states none: 'No Ones yet' and its line, no fan and no controls", () => {
    expect(fan(0)).toBeNull();
    expect(words(host.querySelector(".fan-empty .opost-et"))).toBe("No Ones yet");
    expect(words(host.querySelector(".fan-empty .opost-ep"))).toBe(
      "When a shared fix ships and its result is measured, the people behind it are posted here first.",
    );
    expect(host.querySelector("button")).toBeNull();
  });

  it("C-ONES-FAN.states one: the post and 'The next One could be you' side by side, both readable; 'Post 1 of 1'", () => {
    const region = fan(1)!;
    expect(region.className).toBe("fan one");
    expect(cards()).toHaveLength(2);
    for (const c of cards()) {
      expect(c.hasAttribute("inert")).toBe(false);
      expect(c.hasAttribute("aria-hidden")).toBe(false);
    }
    const next = cards()[1]!.querySelector("article.opost.opost-next")!;
    expect(words(next.querySelector(".opost-nt"))).toBe("The next One could be you");
    expect(words(next.querySelector(".opost-np"))).toBe(
      "Every fix here started with one person saying what kept going wrong.",
    );
    const share = next.querySelector("a")!;
    expect(words(share)).toBe("Share a problem");
    expect(share.getAttribute("href")).toBe("/share");
    expect(position()).toBe("Post 1 of 1");
    // Nothing to move through: no Previous or Next, no side panel, and an arrow key changes nothing
    expect(region.querySelectorAll("button.round-btn")).toHaveLength(0);
    expect(region.querySelector(".fan-side")).toBeNull();
    act(() => {
      region.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    });
    expect(region.className).toBe("fan one");
    expect(position()).toBe("Post 1 of 1");
  });

  it("C-ONES-FAN.states several: stacked at rest, the front card alone in the reading order, the side panel beside it", () => {
    const region = fan(3, 2)!;
    expect(region.className).toBe("fan several");
    expect(cards().map((c) => c.hasAttribute("inert"))).toEqual([false, true, true]);
    const side = region.querySelector(".fan-side")!;
    expect(words(side.querySelector(".fan-side-t"))).toBe("3 fixes, 2 people");
    expect(words(side.querySelector(".fan-side-p"))).toBe(
      "Each one started with someone saying what kept going wrong. See them side by side.",
    );
    expect(words(side.querySelector("button"))).toBe("See details");
    expect(position()).toBe("Post 1 of 3");
  });

  it("C-ONES-FAN.states: 'N fixes, N people' counts each One once; one each when the caller gives no count", () => {
    expect(ONES_FAN_COPY.side(6, 6)).toBe("6 fixes, 6 people");
    expect(ONES_FAN_COPY.side(2, 1)).toBe("2 fixes, 1 person");
    fan(4);
    expect(words(host.querySelector(".fan-side-t"))).toBe("4 fixes, 4 people");
  });

  it("C-ONES-FAN.behaviour/2: See details spreads the fan, the side panel goes and focus moves on to Next", () => {
    const region = fan(5)!;
    const see = region.querySelector<HTMLButtonElement>(".fan-side button")!;
    act(() => see.click());
    expect(region.className).toBe("fan several spread");
    expect(region.querySelector(".fan-side")).toBeNull();
    expect(document.activeElement?.getAttribute("aria-label")).toBe("Next post");
    expect(position()).toBe("Post 1 of 5");
    // The row's static pose: the card two along sits at the edge, the ones after it further back
    expect(cards().map((c) => c.className)).toEqual([
      "fan-card cur",
      "fan-card",
      "fan-card edge",
      "fan-card far",
      "fan-card far",
    ]);
  });

  it("C-ONES-FAN.behaviour/3, WCAG 2.4.3: with focus on See details, → spreads the fan and focus moves on to Next, not to the page", () => {
    const region = fan(4)!;
    const see = region.querySelector<HTMLButtonElement>(".fan-side button")!;
    act(() => see.focus());
    expect(document.activeElement).toBe(see);
    act(() => {
      see.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true, cancelable: true }));
    });
    expect(region.className).toBe("fan several spread");
    expect(region.querySelector(".fan-side")).toBeNull();
    expect(document.activeElement?.getAttribute("aria-label")).toBe("Next post");
    expect(position()).toBe("Post 2 of 4");
  });

  it("C-ONES-FAN.behaviour/4, WCAG 2.4.3: with focus on See details, a wheel step over the cards spreads the fan and focus moves on to Next", () => {
    const region = fan(4)!;
    const see = region.querySelector<HTMLButtonElement>(".fan-side button")!;
    act(() => see.focus());
    const step = new WheelEvent("wheel", { deltaY: 100, bubbles: true, cancelable: true });
    act(() => {
      region.querySelector("article")!.dispatchEvent(step);
    });
    expect(step.defaultPrevented).toBe(true); // the first step spreads the fan and keeps the page still
    expect(region.className).toBe("fan several spread");
    expect(document.activeElement?.getAttribute("aria-label")).toBe("Next post");
    expect(position()).toBe("Post 1 of 4");
  });

  it("C-ONES-FAN.behaviour/3: a spread that starts outside the side panel leaves focus where it is", () => {
    const region = fan(4)!;
    const prev = region.querySelector<HTMLButtonElement>('button[aria-label="Previous post"]')!;
    act(() => prev.focus());
    act(() => {
      prev.dispatchEvent(
        new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true, cancelable: true }),
      );
    });
    expect(region.className).toBe("fan several spread");
    expect(document.activeElement).toBe(prev);
    expect(position()).toBe("Post 2 of 4");
  });
});

// =================================================================================================================
const components = cssRules("app/components.css");
const home = cssRules("app/home/home.css");
const offer = cssRules("app/offer.css");
const block = (() => {
  const css = readFileSync(resolve(SRC, "app/components.css"), "utf8");
  const from = css.indexOf("/* ---------- C-ONES-FAN");
  return css.slice(from, css.indexOf("/* ---------- ", from + 10));
})();
const tokens = readFileSync(resolve(SRC, "app/tokens.css"), "utf8");
const decl = (rules: typeof components, selector: string, prop: string, at = "") =>
  rules
    .filter((r) => r.at === at && r.selectors.includes(selector))
    .at(-1)
    ?.decls.get(prop);

describe("F-COLOR.tiers: the fan's tier colours come from the tokens, never the board's literals (BLD-D023 follows)", () => {
  it("F-COLOR.tiers/3: each tier's ring and key colour reach the card through data-tier and the tokens", () => {
    for (let n = 1; n <= 7; n++) {
      expect(decl(components, `.opost[data-tier="${n}"]`, "--opost-ring")).toBe(`var(--tier-${n}-ring)`);
      expect(decl(offer, `[data-tier="${n}"]`, "--heat")).toBe(`var(--tier-${n})`);
    }
    expect(decl(components, ".opost-m::before", "background")).toBe("var(--opost-ring, var(--heat))");
    expect(decl(components, ".opost-m::after", "background")).toBe("var(--heat)");
  });

  it("F-COLOR.tiers: no tier hex (key colour or ring stop) is written anywhere in C-ONES-FAN's CSS", () => {
    const tierHexes = new Set(
      [...tokens.matchAll(/--tier-\d(?:-ring)?:([^;]+);/g)].flatMap((m) =>
        [...m[1]!.matchAll(/#[0-9a-f]{6}/gi)].map((x) => x[0].toLowerCase()),
      ),
    );
    expect(tierHexes.size).toBeGreaterThanOrEqual(28);
    const written = [...block.matchAll(/#[0-9a-f]{6}\b/gi)].map((x) => x[0].toLowerCase());
    expect(written.filter((x) => tierHexes.has(x))).toEqual([]);
    expect(block).not.toMatch(/\.t[1-7]\b/); // no board class per tier either
  });
});

// =================================================================================================================
function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r!) + 0.7152 * lin(g!) + 0.0722 * lin(b!);
}
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi! + 0.05) / (lo! + 0.05);
}
/** `top` at `alpha` over `base`, as a hex colour. */
function over(top: string, alpha: number, base: string): string {
  const ch = (hex: string, i: number) => parseInt(hex.slice(i, i + 2), 16);
  return `#${[1, 3, 5]
    .map((i) => Math.round(ch(top, i) * alpha + ch(base, i) * (1 - alpha)))
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("")}`;
}
const SLAB = tokens.match(/--slab:(#[0-9A-Fa-f]{6})/)![1]!;

describe("F-COLOR.contrast/1: the board's greys and the cheer's colours, measured on the card #18191D and the slab", () => {
  it("F-COLOR.contrast/1: #A9A9B2 (the card's lines, the side panel, the position line) is 4.5:1 or more", () => {
    expect(SLAB.toLowerCase()).toBe("#18191d");
    for (const sel of [
      ".fan-side-p",
      ".opost-who > span",
      ".opost-ago",
      ".opost-np",
      ".opost-ep",
      ".fan-pos",
    ])
      expect(decl(components, sel, "color"), sel).toBe("#a9a9b2");
    expect(contrast("#a9a9b2", "#18191d")).toBeGreaterThanOrEqual(4.5);
    expect(contrast("#a9a9b2", SLAB)).toBeGreaterThanOrEqual(4.5);
    // The companion card's light: the blue at 22% at its brightest, still over 4.5:1
    expect(contrast("#a9a9b2", over("#395ded", 0.22, SLAB))).toBeGreaterThanOrEqual(4.5);
  });

  it("F-COLOR.contrast/1: S-03's heading, its second line #9C9CA6 at the heading's size, is 4.5:1 or more", () => {
    expect(decl(home, ".hm-o-title span", "color")).toBe("#9c9ca6");
    expect(decl(home, ".hm-o-title span", "font")).toBeUndefined(); // the heading's 500 30px/1.18
    expect(decl(home, ".hm-o-title", "font")).toBe("500 30px/1.18 var(--fd)");
    expect(contrast("#9c9ca6", "#18191d")).toBeGreaterThanOrEqual(4.5);
    expect(contrast("#9c9ca6", SLAB)).toBeGreaterThanOrEqual(4.5);
  });

  it("F-COLOR.contrast/1: Cheer reads at rest, on hover and pressed; Shipped reads on its green", () => {
    const spark = tokens.match(/--spark:(#[0-9A-Fa-f]{6})/)![1]!;
    const rest = over("#ffffff", 0.08, SLAB);
    expect(contrast("#e4e4ea", rest)).toBeGreaterThanOrEqual(4.5);
    expect(decl(components, "button.opost-cheer:hover", "color")).toBe("#ffc2a6");
    expect(contrast("#ffc2a6", over(spark, 0.16, SLAB))).toBeGreaterThanOrEqual(4.5);
    expect(decl(components, 'button.opost-cheer[aria-pressed="true"]', "color")).toBe("#ff9a6e");
    expect(contrast("#ff9a6e", over(spark, 0.2, SLAB))).toBeGreaterThanOrEqual(4.5);
    expect(contrast("#8df3c1", over("#4dd187", 0.18, SLAB))).toBeGreaterThanOrEqual(4.5);
  });

  it("F-COLOR.contrast/1, WCAG 1.4.3: over every tier's ring glow at its brightest stop, the unit line holds 4.5:1 on the scrim and the 44px figure 3:1 without it", () => {
    // Everything read from the sheet and the tokens: the glow's opacity, the block's brighter white stop over the
    // slab, the scrim's floor and how far up it reaches, the unit line's white and the figure's
    const glow = Number(decl(components, ".opost-m::before", "opacity"));
    const lift = Math.max(
      ...[...decl(components, ".opost-m", "background")!.matchAll(/rgba\(255, 255, 255, ([\d.]+)\)/g)].map(
        (m) => Number(m[1]),
      ),
    );
    const base = over("#ffffff", lift, SLAB);
    const scrim = decl(components, ".opost-fig", "background")!;
    const floor = Number(/rgba\(0, 0, 0, ([\d.]+)\)/.exec(scrim)![1]);
    const unitWhite = Number(
      /rgba\(255, 255, 255, ([\d.]+)\)/.exec(decl(components, ".opost-unit", "color")!)![1],
    );
    expect(decl(components, ".opost-big", "color")).toBe("#ffffff");
    expect([glow, lift, floor, unitWhite].every((v) => v > 0 && v < 1)).toBe(true);
    // The floor runs from the block's foot to the top of the unit line, at the laptop's figure and the phone's
    const fade = Number(/calc\(100% - (\d+)px\)/.exec(scrim)![1]);
    const top = parseFloat(decl(components, ".opost-fig", "padding")!);
    const gap = parseFloat(decl(components, ".opost-unit", "margin")!);
    const [, laptop, lineHeight] = /(\d+)px\/([\d.]+)/.exec(decl(components, ".opost-big", "font")!)!;
    const phone = parseFloat(decl(components, ".opost-big", "font-size", "@media (max-width: 640px)")!);
    expect(fade).toBeLessThanOrEqual(top + Math.min(Number(laptop), phone) * Number(lineHeight) + gap);
    for (let n = 1; n <= 7; n++) {
      const stops = [
        ...new RegExp(`--tier-${n}-ring:([^;]+);`).exec(tokens)![1]!.matchAll(/#[0-9A-Fa-f]{6}/g),
      ].map((m) => m[0]);
      const brightest = stops.reduce((a, b) => (luminance(b) > luminance(a) ? b : a));
      const lit = over(brightest, glow, base);
      expect(contrast("#ffffff", lit), `tier ${n}: the figure`).toBeGreaterThanOrEqual(3);
      const under = over("#000000", floor, lit);
      expect(
        contrast(over("#ffffff", unitWhite, under), under),
        `tier ${n}: the unit line`,
      ).toBeGreaterThanOrEqual(4.5);
    }
    // No text-shadow stands in for contrast
    expect(decl(components, ".opost-unit", "text-shadow")).toBeUndefined();
    expect(decl(components, ".opost-big", "text-shadow")).toBeUndefined();
  });
});

// =================================================================================================================
describe("F-A11Y: every target is 44px or more and is named by its visible words", () => {
  it("F-A11Y: Cheer, Read the thread, Share a problem and See details reach 44px; Previous and Next are 44×44", () => {
    expect(decl(components, ".opost-cheer", "min-height")).toBe("44px");
    expect(decl(components, ".opost-cheer", "min-width")).toBe("44px");
    expect(decl(components, ".opost-pill", "min-height")).toBe("44px");
    expect(decl(offer, ".round-btn", "width")).toBe("44px");
    expect(decl(offer, ".round-btn", "height")).toBe("44px");
    // Read the thread, Share a problem and See details are all the one pill
    fan(1);
    expect(host.querySelector(".opost-t")!.classList.contains("opost-pill")).toBe(true);
    expect(host.querySelector(".opost-next a")!.classList.contains("opost-pill")).toBe(true);
    fan(3);
    expect(host.querySelector(".fan-side button")!.classList.contains("opost-pill")).toBe(true);
  });

  it("F-A11Y, WCAG 2.5.3: every control's name starts with its visible words; Cheer, whose visible text is its count, is named as Home.md has it", () => {
    const visible = (el: Element) => {
      const shown = el.cloneNode(true) as Element;
      shown.querySelectorAll(".vh, svg").forEach((n) => n.remove());
      return words(shown);
    };
    const names: string[] = [];
    for (const count of [1, 3]) {
      fan(count);
      for (const el of host.querySelectorAll("a, button")) {
        const seen = visible(el);
        const name = el.getAttribute("aria-label") ?? words(el);
        names.push(name);
        if (el.classList.contains("opost-cheer"))
          expect(name).toMatch(new RegExp(`^Cheer .+\u2019s fix, ${seen} cheers?$`)); // "Cheer Rohit Menon’s fix, 214 cheers"
        else if (seen === "")
          expect(el.getAttribute("aria-label"), el.outerHTML).toBeTruthy(); // an icon alone
        else expect(name.startsWith(seen), `"${name}" starts with "${seen}"`).toBe(true);
      }
    }
    expect(names).toEqual(
      expect.arrayContaining([
        "See details",
        "Previous post",
        "Next post",
        "Share a problem",
        "Read the thread 18",
      ]),
    );
    // Only the two icon buttons carry a label
    fan(3);
    const labelled = [...host.querySelectorAll("a, button")].filter((el) => el.hasAttribute("aria-label"));
    expect(labelled.map((el) => el.getAttribute("aria-label"))).toEqual(["Previous post", "Next post"]);
  });

  it("F-A11Y.rules/4: pressed is more than colour, the heart fills in; on the slab focus is the light blue", () => {
    expect(decl(components, 'button.opost-cheer[aria-pressed="true"] svg', "fill")).toBe("currentColor");
    expect(decl(components, ".fan", "--focus")).toBe("#8fa8ff");
  });
});

// =================================================================================================================
describe("F-MOTION.reduced: a still pose in this slot, the flat offset under reduced motion", () => {
  it("C-ONES-FAN.behaviour/1: stacked, the cards behind are angled into the page with motion allowed, flat under reduced motion, and in a row on a phone", () => {
    fan(4);
    const behind = cards()[1]!;
    const front = cards()[0]!;
    const motion = applied(components, behind, "transform", 1280, false)!;
    expect(motion).toContain("perspective(1400px)");
    expect(motion).toContain("rotateY(-24deg)");
    const still = applied(components, behind, "transform", 1280, true)!;
    expect(still).not.toMatch(/perspective|rotate/);
    expect(still).toContain("var(--i) * 28px");
    expect(applied(components, behind, "filter", 1280, true)).toBe("brightness(calc(1 - var(--i) * 0.15))");
    // The front card faces you; up to four show
    expect(applied(components, front, "transform", 1280, false)).toBeUndefined();
    expect(block).toMatch(
      /\.fan\.several:not\(\.spread\) \.fan-card:nth-child\(n \+ 5\) \{\s*visibility: hidden;/,
    );
    // A phone shows the row: no stacked pose under 641px
    expect(applied(components, behind, "filter", 390, false)).toBeUndefined();
  });

  it("F-MOTION.reduced: no animation and no new transition in C-ONES-FAN's CSS; the glide and tilt stop under reduced motion", () => {
    expect(block.replace(/\/\*[\s\S]*?\*\//g, "")).not.toMatch(/\banimation\b|@keyframes/);
    const moving = components.filter(
      (r) => r.decls.has("transition") && r.selectors.some((s) => /\b(fan|opost)/.test(s)) && r.at === "",
    );
    expect(moving.flatMap((r) => r.selectors).sort()).toEqual([".fan-card > *", ".fan-track"]);
    for (const sel of [".fan-track", ".fan-card > *"])
      expect(decl(components, sel, "transition", "@media (prefers-reduced-motion: reduce)")).toBe("none");
  });
});

// =================================================================================================================
// BLD-D026: the motion between the poses (motion.css) and the phone row's native snap
// =================================================================================================================
const motion = cssRules("app/motion.css");
/** Both sheets in the order layout.tsx loads them, so the last matching rule is the one a browser applies. */
const sheets = [...components, ...motion];
const NO_PREF = "prefers-reduced-motion: no-preference";
const REDUCE = "(prefers-reduced-motion: reduce)";
const MOVES = "@media (min-width: 641px) and (prefers-reduced-motion: no-preference)";
const onFan = (selector: string) => /\.(fan|opost)\b/.test(selector);
const moves = (r: CssRule) => [...r.decls.keys()].some((k) => /^(transition|animation)(-|$)/.test(k));
/** The transform functions in a pose, in order (calc and var are values, not moves). */
const functions = (pose: string) =>
  [...pose.matchAll(/([a-zA-Z]+)\(/g)].map((m) => m[1]).filter((f) => f !== "calc" && f !== "var");

/** jsdom has no matchMedia: answer true for the queries given and false for any other. */
function mediaHolds(...queries: string[]) {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (media: string) => ({
      matches: queries.includes(media),
      media,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    }),
  });
}

/** jsdom has no IntersectionObserver: this one records what it watches and lets a test say where the row snapped. */
class FakeObserver {
  static made: FakeObserver[] = [];
  cb: IntersectionObserverCallback;
  opts: IntersectionObserverInit;
  targets: Element[] = [];
  constructor(cb: IntersectionObserverCallback, opts: IntersectionObserverInit = {}) {
    this.cb = cb;
    this.opts = opts;
    FakeObserver.made.push(this);
  }
  observe(el: Element) {
    this.targets.push(el);
  }
  unobserve() {}
  disconnect() {
    this.targets = [];
  }
  takeRecords() {
    return [];
  }
  /** The row came to rest with card `i` showing at `ratio` of its width. */
  snap(i: number, ratio = 1) {
    const entry = { target: this.targets[i]!, isIntersecting: ratio > 0, intersectionRatio: ratio };
    act(() =>
      this.cb([entry as unknown as IntersectionObserverEntry], this as unknown as IntersectionObserver),
    );
  }
}

const box = (left: number) =>
  ({
    left,
    top: 0,
    width: 300,
    height: 450,
    right: left + 300,
    bottom: 450,
    x: left,
    y: 0,
    toJSON: () => ({}),
  }) as DOMRect;

/** A post whose Cheer the person can press on and off, as Home keeps it. */
function Cheerable({ start }: { start: boolean }) {
  const [on, setOn] = useState(start);
  return post(POSTS[0]!, { cheered: on, onCheer: () => setOn((v) => !v) });
}

const button = (name: string) => host.querySelector<HTMLButtonElement>(`button[aria-label="${name}"]`)!;
const seeDetails = () => host.querySelector<HTMLButtonElement>(".fan-side button")!;

afterEach(() => {
  delete (window as { matchMedia?: unknown }).matchMedia;
  FakeObserver.made = [];
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("C-ONES-FAN.behaviour/2, BLD-D026: the stack flies out into the row, 0.8s a card on the board's curve, 45ms apart", () => {
  it("C-ONES-FAN.behaviour/2: each card carries its place as --i; the fly-out staggers by it and arcs on the way (oFly)", () => {
    fan(5);
    expect(cards().map((c) => c.style.getPropertyValue("--i"))).toEqual(["0", "1", "2", "3", "4"]);
    expect(decl(motion, ".fan.several", "--fan-fly", MOVES)).toBe("0.8s");
    expect(decl(motion, ".fan.several", "--fan-ease", MOVES)).toBe("cubic-bezier(0.2, 0.85, 0.25, 1)");
    expect(decl(motion, ".fan.several", "--fan-stagger", MOVES)).toBe("45ms");
    expect(FAN_MOTION).toEqual({ flyMs: 800, staggerMs: 45, sideMs: 400 });
    // Every card glides between its poses: transform on the board's curve, filter and opacity as the board has them
    expect(decl(motion, ".fan.several .fan-card", "transition", MOVES)).toMatch(
      /^transform var\(--fan-fly\) var\(--fan-ease\),\s*filter 0\.5s ease,\s*opacity 0\.45s ease$/,
    );
    const flying = '.fan.several[data-fly="open"] .fan-card';
    expect(decl(motion, flying, "transition-delay", MOVES)).toBe("calc(var(--i) * var(--fan-stagger))");
    expect(decl(motion, flying, "animation", MOVES)).toBe(
      "oFly var(--fan-fly) var(--fan-ease) calc(var(--i) * var(--fan-stagger)) both",
    );
    // will-change only while the cards fly, nowhere else on the fan
    const promoted = sheets.filter((r) => r.decls.has("will-change") && r.selectors.some(onFan));
    expect(promoted.flatMap((r) => r.selectors)).toEqual([flying]);
    expect(decl(motion, flying, "will-change", MOVES)).toBe("transform, filter");
    // The arc: up 26px and turned 1.5deg at 40% of the way, from the individual properties so it adds to the glide
    const arc = keyframes(motion, "oFly");
    expect(arc.map((k) => [k.at, k.decls.get("translate"), k.decls.get("rotate")])).toEqual([
      [40, "0 -26px", "-1.5deg"],
    ]);
    // The cards the stack hides (the fifth on) fade in as they fly
    expect(decl(motion, `${flying}:nth-child(n + 5)`, "animation", MOVES)).toMatch(
      /oFly .*,\s*oShow 0\.45s ease /,
    );
    expect(keyframes(motion, "oShow").map((k) => [k.at, k.decls.get("opacity")])).toEqual([[0, "0"]]);
  });

  it("C-ONES-FAN.behaviour/2: spread, the card coming up sits angled in (.edge), the ones after it further back (.far), in the stack's own list of functions", () => {
    const region = fan(5)!;
    act(() => seeDetails().click());
    const [front, , edge, far] = cards();
    expect(applied(components, edge!, "transform", 1280)).toBe(
      "translateX(0) perspective(1400px) translateX(0) translateZ(-60px) rotateY(-16deg)",
    );
    expect(applied(components, edge!, "filter", 1280)).toBe("brightness(0.8)");
    expect(applied(components, far!, "transform", 1280)).toBe(
      "translateX(0) perspective(1400px) translateX(0) translateZ(-90px) rotateY(-24deg)",
    );
    expect(applied(components, far!, "filter", 1280)).toBe("brightness(0.66)");
    expect(applied(components, front!, "transform", 1280)).toBeUndefined(); // the current card faces you
    expect(region.className).toBe("fan several spread");
    // The stack, its hover and the row's two angled poses share one list of functions, so a card glides from one
    // to the next function by function (the edge straightening as it comes up), never through a matrix
    const stacked = decl(
      components,
      ".fan.several:not(.spread) .fan-card:not(:first-child)",
      "transform",
      MOVES,
    )!;
    const hover = motion.find((r) => r.selectors[0]!.endsWith(":hover .fan-card:not(:first-child)"))!;
    const poses = [
      stacked,
      hover.decls.get("transform")!,
      ...[edge!, far!].map((c) => applied(components, c, "transform", 1280)!),
    ];
    for (const pose of poses)
      expect(functions(pose)).toEqual(["translateX", "perspective", "translateX", "translateZ", "rotateY"]);
  });

  it("C-ONES-FAN.behaviour/2, WCAG 2.4.3: with motion allowed, See details flies the cards out; the side panel leaves the reading order at once and the page after its exit", () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    mediaHolds(FAN_FLY);
    const region = fan(5)!;
    expect(region.hasAttribute("data-fly")).toBe(false);
    act(() => seeDetails().click());
    expect(region.className).toBe("fan several spread");
    expect(region.getAttribute("data-fly")).toBe("open");
    const side = region.querySelector(".fan-side")!;
    expect(side.hasAttribute("data-leaving")).toBe(true);
    expect(side.getAttribute("aria-hidden")).toBe("true");
    expect(side.hasAttribute("inert")).toBe(true);
    expect(document.activeElement?.getAttribute("aria-label")).toBe("Next post");
    expect(position()).toBe("Post 1 of 5");
    act(() => vi.advanceTimersByTime(FAN_MOTION.sideMs));
    expect(region.querySelector(".fan-side")).toBeNull();
    expect(region.getAttribute("data-fly")).toBe("open"); // the last card is still on its way
    act(() => vi.advanceTimersByTime(FAN_MOTION.flyMs + 4 * FAN_MOTION.staggerMs + 50 - FAN_MOTION.sideMs));
    expect(region.hasAttribute("data-fly")).toBe(false);
    // The row then moves card by card; nothing flies again
    act(() => button("Next post").click());
    expect(region.hasAttribute("data-fly")).toBe(false);
    expect(position()).toBe("Post 2 of 5");
  });

  it("C-ONES-FAN.behaviour/2: the panel's exit takes the board's values; it keeps its column over the cards, and stays in place where it sat under the stack", () => {
    const leaving = (prop: string) => decl(motion, ".fan-side[data-leaving]", prop, MOVES);
    expect(leaving("opacity")).toBe("0");
    expect(leaving("visibility")).toBe("hidden");
    expect(leaving("translate")).toBe("32px 0");
    expect(leaving("pointer-events")).toBe("none");
    expect(leaving("transition")).toMatch(
      /^opacity 0\.25s ease,\s*translate 0\.4s ease,\s*visibility 0s linear 0\.4s$/,
    );
    expect(leaving("width")).toBe("min(28%, 280px)"); // the stack's column, as the grid gave it
    expect(decl(components, ".fan.several:not(.spread) .fan-stage", "grid-template-columns")).toBe(
      "minmax(0, 1fr) min(28%, 280px)",
    );
    expect(
      decl(motion, ".fan-side[data-leaving]", "position", `${MOVES} @container fan (max-width: 860px)`),
    ).toBe("static");
  });
});

describe("F-MOTION.reduced, BLD-D026: under reduced motion the fan has no transition and no animation at all", () => {
  it("F-MOTION.reduced/1: every fan rule that moves sits under no-preference, or a reduced-motion rule sets it to none", () => {
    const moving = sheets.filter(
      (r) =>
        !r.at.startsWith("@keyframes") && !r.at.includes("reduce") && r.selectors.some(onFan) && moves(r),
    );
    expect(moving.length).toBeGreaterThanOrEqual(6);
    const reduce = sheets.filter((r) => r.at.includes(REDUCE));
    for (const r of moving) {
      if (r.at.includes(NO_PREF)) continue;
      for (const selector of r.selectors.filter(onFan)) {
        const off = reduce.find((x) => x.selectors.includes(selector));
        expect(off, `${selector}: a reduced-motion rule`).toBeDefined();
        for (const k of r.decls.keys())
          if (/^(transition|animation)/.test(k)) expect(off!.decls.get(k), `${selector} ${k}`).toBe("none");
      }
    }
  });

  it("F-MOTION.reduced/1: on the rendered fan, stacked, flying or cheered, no element takes a transition, animation or will-change", () => {
    const still = (root: Element, what: string) => {
      for (const width of [1280, 390])
        for (const el of [root, ...root.querySelectorAll("*")])
          for (const prop of ["transition", "transition-delay", "animation", "will-change"]) {
            const v = applied(sheets, el, prop, width, true);
            expect(
              v === undefined || v === "none",
              `${what}, ${el.tagName}.${String(el.getAttribute("class"))} ${prop} at ${width}: ${v}`,
            ).toBe(true);
          }
    };
    const stacked = fan(5)!;
    // With motion allowed the same cards do glide, so the check below is not empty by accident
    expect(applied(sheets, cards()[1]!, "transition", 1280, false)).toMatch(/^transform /);
    still(stacked, "stacked");
    const region = fan(5)!;
    act(() => button("Next post").click());
    region.setAttribute("data-fly", "open");
    still(region, "flying");
    show(h(Cheerable, { start: false }));
    act(() => host.querySelector<HTMLButtonElement>("button.opost-cheer")!.click());
    expect(host.querySelector("button.opost-cheer.on")).not.toBeNull();
    still(host, "cheered");
  });

  it("F-MOTION.reduced/1: under reduced motion nothing flies; the panel goes at once and focus still moves on to Next", () => {
    mediaHolds(REDUCE);
    const region = fan(4)!;
    act(() => seeDetails().click());
    expect(region.className).toBe("fan several spread");
    expect(region.hasAttribute("data-fly")).toBe(false);
    expect(region.querySelector(".fan-side")).toBeNull();
    expect(document.activeElement?.getAttribute("aria-label")).toBe("Next post");
  });
});

describe("C-ONES-FAN.behaviour/6, BLD-D026: the hover lean and the tilt, only with a pointer that hovers and is fine", () => {
  it("C-ONES-FAN.behaviour/6: every fan hover that moves a card sits under (hover: hover) and (pointer: fine), with motion allowed, and takes the board's values", () => {
    const lean = sheets.filter(
      (r) => r.decls.has("transform") && r.selectors.some((s) => onFan(s) && s.includes(":hover")),
    );
    expect(lean).toHaveLength(2);
    for (const r of lean) {
      expect(r.at).toContain("(hover: hover) and (pointer: fine)");
      expect(r.at).toContain(NO_PREF);
      expect(r.at).toContain("(min-width: 641px)");
      expect(r.selectors.every((s) => s.startsWith(".fan.several:not(.spread) .fan-stage:hover "))).toBe(
        true,
      );
    }
    // The fan opens a little: 52px to 68px a card, -24deg to -16deg
    const behind = lean.find((r) => r.selectors[0]!.endsWith(":not(:first-child)"))!.decls.get("transform")!;
    expect(behind).toContain("68px * (var(--i) - 1)");
    expect(behind).toContain("rotateY(-16deg)");
    expect(
      decl(components, ".fan.several:not(.spread) .fan-card:not(:first-child)", "transform", MOVES),
    ).toContain("52px * (var(--i) - 1)");
    // The top card leans out toward the pointer
    const top = lean.find((r) => r.selectors[0]!.endsWith(".fan-card:first-child"))!.decls.get("transform");
    expect(top).toBe("perspective(1400px) translateZ(24px) rotateY(4deg)");
    // Where no fine pointer hovers (touch), nothing applies: the front card faces you at rest
    fan(4);
    expect(applied(sheets, cards()[0]!, "transform", 1280)).toBeUndefined();
  });

  it("C-ONES-FAN.behaviour/6: the pointer tilt follows a mouse only where the pointer hovers and is fine; never a finger, never under reduced motion", () => {
    fan(4);
    const front = cards()[0]!;
    front.getBoundingClientRect = () =>
      ({ ...box(0), width: 200, right: 200, height: 300, bottom: 300 }) as DOMRect;
    const point = (pointerType: string) =>
      act(() => {
        front.style.removeProperty("--tx");
        front.style.removeProperty("--ty");
        front.dispatchEvent(new PointerEvent("pointerover", { bubbles: true, pointerType }));
        front.dispatchEvent(
          new PointerEvent("pointermove", { bubbles: true, pointerType, clientX: 150, clientY: 75 }),
        );
      });
    point("mouse"); // no fine pointer known
    expect(front.style.getPropertyValue("--ty")).toBe("");
    mediaHolds(FAN_FINE);
    point("touch");
    expect(front.style.getPropertyValue("--ty")).toBe("");
    point("mouse");
    expect(front.style.getPropertyValue("--ty")).toBe("1.25deg");
    expect(front.style.getPropertyValue("--tx")).toBe("1.00deg");
    mediaHolds(FAN_FINE, REDUCE);
    point("mouse");
    expect(front.style.getPropertyValue("--ty")).toBe("");
  });
});

describe("C-ONES-FAN.card, BLD-D026: Cheer's heart fills and pops once, on the person's own press only", () => {
  it("C-ONES-FAN.card: cheerPop runs only on .on, with motion allowed, 0.42s on the board's spring", () => {
    const users = sheets.filter((r) => [...r.decls.values()].some((v) => /\bcheerPop\b/.test(v)));
    expect(users.map((r) => [r.at, r.selectors])).toEqual([
      ["@media (prefers-reduced-motion: no-preference)", ["button.opost-cheer.on svg"]],
    ]);
    expect(users[0]!.decls.get("animation")).toBe("cheerPop 0.42s cubic-bezier(0.34, 1.56, 0.64, 1)");
    expect(keyframes(motion, "cheerPop").map((k) => [k.at, k.decls.get("transform")])).toEqual([
      [40, "scale(1.35)"],
    ]);
    // The fill stays the pressed state's own, with or without motion
    expect(decl(components, 'button.opost-cheer[aria-pressed="true"] svg', "fill")).toBe("currentColor");
  });

  it("C-ONES-FAN.card: a cheer already there on load never pops; the person's press that turns it on adds .on, turning it off takes .on away", () => {
    show(h(Cheerable, { start: true }));
    const cheer = () => host.querySelector<HTMLButtonElement>("button.opost-cheer")!;
    expect(cheer().getAttribute("aria-pressed")).toBe("true");
    expect(cheer().classList.contains("on")).toBe(false);
    act(() => cheer().click());
    expect(cheer().getAttribute("aria-pressed")).toBe("false");
    expect(cheer().classList.contains("on")).toBe(false);
    act(() => cheer().click());
    expect(cheer().getAttribute("aria-pressed")).toBe("true");
    expect(cheer().classList.contains("on")).toBe(true);
    expect(words(cheer())).toBe("Cheer Asha Shetty’s fix, 214 cheers"); // the name is unchanged
  });
});

describe("C-ONES-FAN.behaviour/7, BLD-D026: on a phone several posts scroll by swipe with native snap, and the position line follows", () => {
  it("C-ONES-FAN.behaviour/7: at phone width the row is the view's own scroll, x mandatory, a card a snap; the track no longer moves", () => {
    const region = fan(4)!;
    const view = region.querySelector(".fan-view")!;
    const track = region.querySelector(".fan-track")!;
    expect(applied(components, view, "overflow-x", 390)).toBe("auto");
    expect(applied(components, view, "scroll-snap-type", 390)).toBe("x mandatory");
    expect(applied(components, view, "overscroll-behavior-x", 390)).toBe("contain");
    expect(applied(components, view, "touch-action", 390)).toBe("auto");
    expect(applied(components, cards()[2]!, "scroll-snap-align", 390)).toBe("start");
    // Wider than a phone it stays the track the controls move
    expect(applied(components, view, "overflow-x", 1280)).toBe("clip");
    expect(applied(components, view, "scroll-snap-type", 1280)).toBeUndefined();
    act(() => button("Next post").click());
    expect(applied(components, track, "transform", 1280)).toContain("var(--at)");
    expect(applied(components, track, "transform", 390)).toBeUndefined();
    // Under reduced motion it still snaps, and moves without a glide
    expect(applied(components, view, "scroll-snap-type", 390, true)).toBe("x mandatory");
    expect(applied(components, view, "scroll-behavior", 390, true)).toBe("auto");
  });

  it("C-ONES-FAN.behaviour/5, /7: the position line, the reading order and Previous and Next follow the card the row snaps to; Next scrolls to the next snap", () => {
    mediaHolds(FAN_PHONE);
    vi.stubGlobal("IntersectionObserver", FakeObserver);
    const region = fan(4)!;
    const view = region.querySelector<HTMLElement>(".fan-view")!;
    const io = FakeObserver.made.at(-1)!;
    expect(io.opts.root).toBe(view);
    expect(io.opts.threshold).toBe(0.6);
    expect(io.targets).toEqual(cards());
    expect(position()).toBe("Post 1 of 4");
    // A swipe lands on the third card
    io.snap(2);
    expect(position()).toBe("Post 3 of 4");
    expect(cards().map((c) => c.hasAttribute("inert"))).toEqual([true, true, false, true]);
    expect(button("Previous post").hasAttribute("aria-disabled")).toBe(false);
    // A card only partly in view while the row moves changes nothing
    io.snap(1, 0.4);
    expect(position()).toBe("Post 3 of 4");
    // Next scrolls the row so the fourth card sits at its snap point, with a glide
    const scrollTo = vi.fn();
    view.scrollTo = scrollTo as unknown as typeof view.scrollTo;
    view.getBoundingClientRect = () => box(10);
    cards()[3]!.getBoundingClientRect = () => box(310);
    act(() => button("Next post").click());
    expect(scrollTo).toHaveBeenCalledWith({ left: 300, behavior: "smooth" });
    expect(position()).toBe("Post 4 of 4");
    expect(button("Next post").getAttribute("aria-disabled")).toBe("true");
    io.snap(3);
    expect(position()).toBe("Post 4 of 4");
    // Never a fly-out on a phone: there is no stack
    expect(region.hasAttribute("data-fly")).toBe(false);
  });

  it("C-ONES-FAN.behaviour/4, F-MOTION.reduced/5: on a phone the first wheel step already moves a card (no stack to open), and under reduced motion it jumps", () => {
    mediaHolds(FAN_PHONE, REDUCE);
    vi.stubGlobal("IntersectionObserver", FakeObserver);
    const region = fan(3)!;
    const view = region.querySelector<HTMLElement>(".fan-view")!;
    const scrollTo = vi.fn();
    view.scrollTo = scrollTo as unknown as typeof view.scrollTo;
    const step = new WheelEvent("wheel", { deltaY: 100, bubbles: true, cancelable: true });
    act(() => {
      region.querySelector("article")!.dispatchEvent(step);
    });
    expect(step.defaultPrevented).toBe(true);
    expect(position()).toBe("Post 2 of 3");
    expect(scrollTo).toHaveBeenCalledWith({ left: expect.any(Number), behavior: "auto" });
  });
});
