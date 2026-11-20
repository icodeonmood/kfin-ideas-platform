// @vitest-environment jsdom
/**
 * C-ONES-FAN rebuilt to Home.dc.html's static look (BLD-D020): the card (C-ONES-FAN.card), the three states and the
 * stack's side panel (C-ONES-FAN.states), the tier colours from the tokens (F-COLOR.tiers, so BLD-D023's swap of
 * tiers 6 and 7 follows), the board's greys measured on the slab (F-COLOR.contrast), 44px targets named by their
 * visible words (F-A11Y), and a still pose with a flat offset under reduced motion (F-MOTION.reduced). The moving
 * parts (Previous and Next, ← →, the wheel) keep their own tests in vacc-teamup.test.ts and s03-home.test.ts.
 * Synthetic people only.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { act, createElement as h, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { applied, cssRules, SRC } from "./helpers/css-rules";

vi.mock("next/link", async () => {
  const { createElement } = await import("react");
  return {
    default: ({ href, children, ...rest }: { href: string; children?: ReactNode }) =>
      createElement("a", { href, ...rest }, children),
  };
});

const { OnesEmpty, OnesFan, OnesNext, OnesPost, ONES_FAN_COPY } = await import("@/components/ui/ones-fan");

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

  it("F-A11Y: names start with the visible words; only the icon buttons carry a label", () => {
    fan(3);
    const named = [...host.querySelectorAll("a, button")].filter((el) => el.hasAttribute("aria-label"));
    expect(named.map((el) => el.getAttribute("aria-label"))).toEqual(["Previous post", "Next post"]);
    expect(words(host.querySelector(".fan-side button"))).toBe("See details");
    expect(words(host.querySelector(".opost-t"))).toMatch(/^Read the thread \d+$/);
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
