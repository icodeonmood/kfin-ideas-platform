/**
 * Accessibility and type checks on lane D's shell and shared components, read from the sheets as written (F-TYPE,
 * F-A11Y; C-FILE, C-SIDEBAR, C-TASKBAR, C-PHONE-TABS, C-SEARCH's question box, C-ONES-FAN). Each is a review note
 * that a screenshot would not catch until a person printed, zoomed or tabbed.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { OnesPost } from "@/components/ui/ones-fan";

vi.mock("next/link", async () => {
  const { createElement: h } = await import("react");
  return {
    default: (p: { href: string; className?: string; children?: unknown }) =>
      h("a", { href: p.href, className: p.className }, p.children as never),
  };
});

const APP = fileURLToPath(new URL("../../src/app/", import.meta.url));
const read = (sheet: string) => readFileSync(`${APP}${sheet}`, "utf8");

type Rule = { at: string; selectors: string[]; decls: Map<string, string> };

/** Every style rule in a sheet: its enclosing at-rules (joined), its selectors and its declarations. */
function rules(css: string): Rule[] {
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const out: Rule[] = [];
  const stack: string[] = [];
  let buf = "";
  let current: Rule | null = null;
  for (const ch of clean) {
    if (ch === "{") {
      const head = buf.trim();
      buf = "";
      if (head.startsWith("@")) {
        stack.push(head.replace(/\s+/g, " "));
      } else {
        current = {
          at: stack.join(" "),
          selectors: head.split(",").map((s) => s.trim().replace(/\s+/g, " ")),
          decls: new Map(),
        };
        stack.push("");
        out.push(current);
      }
    } else if (ch === "}") {
      const top = stack.pop();
      if (top === "" && current) {
        const last = buf.trim();
        const m = last.match(/^([\w-]+)\s*:\s*([\s\S]+)$/);
        if (m) current.decls.set(m[1]!, m[2]!.trim());
        current = null;
      }
      buf = "";
    } else if (ch === ";" && current) {
      const m = buf.trim().match(/^([\w-]+)\s*:\s*([\s\S]+)$/);
      if (m) current.decls.set(m[1]!, m[2]!.trim());
      buf = "";
    } else buf += ch;
  }
  return out;
}

/** The declarations for a selector, later rules winning, optionally only inside a given at-rule. */
function style(sheet: string, selector: string, at?: (a: string) => boolean): Map<string, string> {
  const merged = new Map<string, string>();
  for (const r of rules(read(sheet)))
    if (r.selectors.includes(selector) && (at ? at(r.at) : r.at === ""))
      for (const [k, v] of r.decls) merged.set(k, v);
  return merged;
}

/** A token's hex value from the pack's tokens.css. */
function token(name: string): string {
  const v = read("tokens.css").match(new RegExp(`${name}\\s*:\\s*(#[0-9a-fA-F]{6})`))?.[1];
  if (!v) throw new Error(`${name} is not a hex token`);
  return v;
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r!) + 0.7152 * lin(g!) + 0.0722 * lin(b!);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi! + 0.05) / (lo! + 0.05);
}

/** The px size a declaration block sets, from `font-size` or the `font` shorthand. */
function fontPx(decls: Map<string, string>): number {
  const size = decls.get("font-size") ?? decls.get("font")?.match(/(\d+(?:\.\d+)?)px/)?.[1];
  return Number.parseFloat(String(size));
}

describe("F-TYPE.rules/5: no text under 12px in lane D's badges", () => {
  it("C-FILE: the type tile (PNG, JPG, PDF, XLSX, DOC, PPT, Link) is 12px, one fixed width for every type", () => {
    const tile = style("components.css", ".fbadge");
    expect(fontPx(tile)).toBeGreaterThanOrEqual(12);
    // A fixed width (not min-width), so names line up row to row whatever the type
    expect(tile.get("width")).toBe("44px");
    expect(tile.has("min-width")).toBe(false);
    expect(tile.get("white-space")).toBe("nowrap");
  });

  it("C-SIDEBAR.fold/2: the folded bar's Inbox count is 12px, like the open bar's (600 12px)", () => {
    const folded = style("shell.css", ".sb-n", (a) => a.startsWith("@container sbar"));
    expect(fontPx(folded)).toBeGreaterThanOrEqual(12);
    expect(fontPx(style("shell.css", ".sb-n"))).toBe(12);
  });
});

describe("Print: the page only", () => {
  it.each([
    [".tbar", "C-TASKBAR"],
    [".dock", "C-PHONE-TABS.dock"],
  ])("%s (%s) is hidden in print, from lane D's own sheet", (selector) => {
    const printed = style("shell.css", selector, (a) => a === "@media print");
    expect(printed.get("display")).toMatch(/^none(\s*!important)?$/);
  });
});

describe("F-A11Y.rules/2: the question box shows the focus ring every field has", () => {
  it("C-SEARCH: the box draws a 2px --focus outline, 3px out, while its input has focus", () => {
    expect(style("components.css", ".qbox input").get("outline")).toBe("none");
    const ring = style("components.css", ".qbox:has(input:focus-visible)");
    expect(ring.get("outline")).toBe("2px solid var(--focus)");
    expect(ring.get("outline-offset")).toBe("3px");
    // The old ring was a 1px line at 55% plus a 12% halo; nothing else may stand in for the outline
    expect(style("components.css", ".qbox:focus-within").size).toBe(0);
  });

  it("C-SEARCH: --focus is --blue on light screens and reaches 3:1 on white and on paper", () => {
    expect(read("offer.css")).toMatch(/:root[^{]*\{[^}]*--focus:\s*var\(--blue\)/);
    expect(contrast(token("--blue"), "#ffffff")).toBeGreaterThanOrEqual(3);
    expect(contrast(token("--blue"), token("--paper"))).toBeGreaterThanOrEqual(3);
  });
});

describe("C-ONES-FAN.card: the cheer toggle is never colour alone (F-A11Y.rules/4)", () => {
  const post = (cheered: boolean) =>
    renderToStaticMarkup(
      createElement(OnesPost, {
        name: "Farhan Nair",
        initials: "FN",
        number: 17,
        tier: 3,
        tierName: "Flame",
        ago: "2d",
        sentence: "Courier tracking for physical redemption forms now updates on its own.",
        figure: "1,240",
        unit: "calls avoided last quarter",
        cheers: 156,
        cheered,
        onCheer: () => undefined,
        replies: 12,
        threadHref: "/ideas/IDEA-2026-000301/conversation",
      }),
    );

  it("pressed, the flame fills in; unpressed, it is an outline. No motion on it (DEC-109)", () => {
    const pressed = style("components.css", 'button.opost-cheer[aria-pressed="true"] svg');
    expect(pressed.get("fill")).toBe("currentColor");
    expect([...pressed.keys()].some((k) => k.startsWith("animation") || k.startsWith("transition"))).toBe(
      false,
    );
    expect(post(true)).toMatch(
      /<button[^>]*class="opost-cheer"[^>]*aria-pressed="true"[^>]*>.*?<svg[^>]*fill="none"/,
    );
    expect(post(false)).toMatch(/<button[^>]*class="opost-cheer"[^>]*aria-pressed="false"/);
  });

  it("keeps its 44px target", () => {
    const cheer = style("components.css", ".opost-cheer");
    expect(cheer.get("min-width")).toBe("44px");
    expect(cheer.get("min-height")).toBe("44px");
  });
});

describe("S-H6.rules/3: the account menu is not clipped", () => {
  it("C-SIDEBAR: in the open bar, which scrolls and so clips, the menu keeps to the account row; its anchor stays", () => {
    expect(style("shell.css", ".sb-in").get("overflow-y")).toBe("auto");
    const up = style("shell.css", ".acct-up .acct-menu");
    expect(up.get("left")).toBe("0");
    expect(up.get("bottom")).toBe("calc(100% - 4px)");
    expect(up.get("max-width")).toBe("100%");
  });

  it("C-SIDEBAR.fold: folded, the bar overflows visibly and the menu takes its full 248px", () => {
    const folded = (a: string) => a.startsWith("@container sbar");
    expect(style("shell.css", ".sb-in", folded).get("overflow")).toBe("visible");
    expect(style("shell.css", ".acct-up .acct-menu", folded).get("max-width")).toBe("none");
    expect(style("shell.css", ".acct-menu").get("width")).toBe("248px");
  });
});
