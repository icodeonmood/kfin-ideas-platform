// @vitest-environment jsdom
/**
 * S-WALL.ember, C-PILL (BLD-D016, WCAG 2.1 AA 1.4.3): the Ember's newest issue carries the board's warm "Latest" pill
 * (Wall.dc.html: #FFF4EE wash, #B54708 words, spark dot), not the gradient-band pill, which drew white words on
 * #b4b4b4 (2.07:1) on the white card. CI's data has no Ember issue, so this renders one. Synthetic content only.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
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
type Ember = Extract<Props["data"]["ember"], { ok: true }>["data"];

const EMBER = [
  {
    number: 1,
    month: "November 2026",
    state: "latest",
    headline: "Payout checks that stop a wrong bank detail.",
    items: ["One fix shipped", "Two crews formed"],
    to: "/ember/1",
  },
  { number: 2, month: "December 2026", state: "coming_soon", headline: null, items: [], to: null },
] as unknown as Ember;

function wall(): HTMLElement {
  const html = renderToStaticMarkup(
    createElement(WallScreen, {
      state: { kind: "all", sort: "newest", more: 0, ones: "wall", at: null, dy: null },
      data: {
        kindling: { ok: false, paused: null },
        justIn: { ok: false, paused: null },
        ones: { ok: false, paused: null },
        impact: { ok: false, paused: null },
        ember: { ok: true, data: EMBER },
      },
    }),
  );
  const host = document.createElement("div");
  host.innerHTML = html;
  return host;
}

const CSS = readFileSync(resolve(__dirname, "../../src/app/components.css"), "utf8");
const TOKENS = readFileSync(resolve(__dirname, "../../src/app/tokens.css"), "utf8");

function rule(selector: string): string {
  const at = CSS.indexOf(`${selector} {`);
  expect(at, selector).toBeGreaterThanOrEqual(0);
  return CSS.slice(at, CSS.indexOf("}", at));
}

function hex(value: string): string {
  const v = value.trim();
  const token = /^var\((--[\w-]+)\)$/.exec(v);
  if (!token) return v.toLowerCase();
  const m = new RegExp(`${token[1]}:\\s*(#[0-9a-fA-F]{6})`).exec(TOKENS);
  expect(m, token[1]).not.toBeNull();
  return m![1]!.toLowerCase();
}

function prop(block: string, name: string): string {
  const m = new RegExp(`(?:^|[\\s;{])${name}:\\s*([^;]+);`).exec(block);
  expect(m, name).not.toBeNull();
  return hex(m![1]!);
}

function luminance(h: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r!) + 0.7152 * lin(g!) + 0.0722 * lin(b!);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi! + 0.05) / (lo! + 0.05);
}

describe("S-WALL.ember, C-PILL (BLD-D016): the newest Ember issue's Latest pill", () => {
  it("draws the warm Latest pill with its dot on the issue card, never the band pill", () => {
    const card = wall().querySelector("article.wl-issue");
    expect(card).not.toBeNull();
    const pill = card!.querySelector(".pill");
    expect(pill?.textContent).toBe("Latest");
    expect(pill?.classList.contains("latest")).toBe(true);
    expect(pill?.classList.contains("band")).toBe(false);
    expect(pill?.querySelector('i[aria-hidden="true"]')).not.toBeNull();
  });

  it("keeps the board's colours, and its words pass AA (4.5:1) on its wash", () => {
    const pill = rule(".pill.latest");
    const bg = prop(pill, "background");
    const fg = prop(pill, "color");
    expect(bg).toBe("#fff4ee");
    expect(fg).toBe("#b54708");
    expect(prop(rule(".pill.latest > i"), "background")).toBe("#f46835");
    expect(contrast(fg, bg)).toBeGreaterThanOrEqual(4.5);
  });
});
