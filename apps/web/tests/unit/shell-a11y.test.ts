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

import { PhoneBar } from "@/components/shell/phone";
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

describe("C-PHONE-TABS.nav: Back and the title never touch", () => {
  const phone = (a: string) => a === "@media (max-width: 640px)";
  // Measured at 500 16px Inter: "Your idea" 71.2px, "The idea" 65.5px; Back adds 4 + 22 (chevron) + 2 + 8 = 36px
  const BACK_NEEDS = 36 + 71.2;

  it("BLD-D041, C-PHONE-TABS.nav: at every phone width each side keeps its own content and shares the rest equally, so the title stays centred; Back fits 'Your idea' under its 128px cap and a longer label ends in an ellipsis", () => {
    const cols = style("shell.css", ".pnav", phone).get("grid-template-columns");
    expect(cols).toBe("minmax(max-content, 1fr) auto minmax(max-content, 1fr)");
    // No narrower query sets the bar apart any more: one rule from 0 to 640px
    const apart = rules(read("shell.css")).filter(
      (r) => (r.selectors.includes(".pnav") || r.selectors.includes(".pback")) && r.at !== "" && !phone(r.at),
    );
    expect(apart).toEqual([]);
    const cap = Number.parseFloat(style("shell.css", ".pback", phone).get("max-width") ?? "");
    expect(cap).toBe(128);
    expect(cap).toBeGreaterThanOrEqual(BACK_NEEDS);
    expect(style("shell.css", ".pback span", phone).get("text-overflow")).toBe("ellipsis");
  });

  it("a longer Back label ends in an ellipsis inside its own column; targets stay 44px; the title caps at 180px", () => {
    const label = style("shell.css", ".pback span", phone);
    expect(label.get("min-width")).toBe("0");
    expect(label.get("overflow")).toBe("hidden");
    expect(label.get("text-overflow")).toBe("ellipsis");
    const back = style("shell.css", ".pback", phone);
    expect(back.get("min-width")).toBe("44px");
    expect(back.get("min-height")).toBe("44px");
    expect(back.get("overflow")).toBe("hidden");
    const title = style("shell.css", ".pnav-t", phone);
    expect(title.get("max-width")).toBe("180px");
    expect(title.get("text-overflow")).toBe("ellipsis");
    expect(
      renderToStaticMarkup(
        createElement(PhoneBar, {
          back: { href: "/ideas/IDEA-2026-000301", label: "The idea" },
          title: "Rejection SMS codes confuse distributors",
        }),
      ),
    ).toMatch(
      /<a href="\/ideas\/IDEA-2026-000301" class="pback"><svg[^>]*>.*<\/svg><span>The idea<\/span><\/a>/,
    );
  });

  it("BLD-D041, C-PHONE-TABS.nav (BLD-D034's case, now at every phone width): at 320 a short title shows in full, and at 360 on /crew so does 'Find your crew'; Back keeps its longest label and its 8px from the title", () => {
    // Inter's advance widths at the bar's weights: "Home" at 500 16px; "Answer", "Conversation" and "Find your crew"
    // at 600 15px
    const HOME = 45.2;
    const ANSWER = 56;
    const CONVERSATION = 97.7;
    const FIND_YOUR_CREW = 108;
    const bar = style("shell.css", ".pnav", phone);
    expect(bar.get("grid-template-columns")).toBe("minmax(max-content, 1fr) auto minmax(max-content, 1fr)");
    // The gaps and padding are the phone bar's own: Back and the title stay 8px apart
    expect(bar.get("gap")).toBe("8px");
    expect(bar.get("padding")).toBe("max(8px, env(safe-area-inset-top)) 8px 6px");
    // Back stops at a cap over its longest label, so "Your idea" never ends in an ellipsis and a longer one still does
    const cap = Number.parseFloat(style("shell.css", ".pback", phone).get("max-width") ?? "");
    expect(cap).toBeGreaterThanOrEqual(BACK_NEEDS);
    expect(style("shell.css", ".pback span", phone).get("text-overflow")).toBe("ellipsis");
    // The title gives way and ends in an ellipsis when even what the sides leave is too little
    const title = style("shell.css", ".pnav-t", phone);
    expect(title.get("overflow")).toBe("hidden");
    expect(title.get("text-overflow")).toBe("ellipsis");
    expect(title.get("white-space")).toBe("nowrap");
    // At 320 beside a 15px classic scrollbar (CI's desktop Chrome): 305 - 16 padding - 16 gaps = 273px inside
    const inside = 320 - 15 - 32;
    // Before: two 110px sides left 53px, under "Answer"
    expect(inside - 2 * 110).toBeLessThan(ANSWER);
    // S-R3: Back "Home", no actions: "Answer" fits, and the sides then share the rest equally, so it stays centred
    expect(inside - (36 + HOME)).toBeGreaterThanOrEqual(ANSWER);
    expect((inside - ANSWER) / 2).toBeGreaterThanOrEqual(36 + HOME);
    // S-08: Back at its cap and the 44px info button: "Conversation" still fits
    expect(inside - cap - 44).toBeGreaterThanOrEqual(CONVERSATION);
    // /crew at 360, inside lane F's 16px phone padding a side (crew.css): 360 - 32 - 16 padding - 16 gaps = 296px
    const crew = 360 - 32 - 16 - 16;
    expect(crew).toBe(296);
    // Before: two 110px sides left the title 76px on a real phone and 61px beside CI's scrollbar: "Find y…"
    expect(crew - 2 * 110).toBe(76);
    expect(crew - 15 - 2 * 110).toBeLessThan(FIND_YOUR_CREW);
    // Back "Home", no actions: "Find your crew" fits whole and centred, on a real phone and beside CI's scrollbar
    for (const room of [crew, crew - 15]) {
      expect(room - (36 + HOME)).toBeGreaterThanOrEqual(FIND_YOUR_CREW);
      expect((room - FIND_YOUR_CREW) / 2).toBeGreaterThanOrEqual(36 + HOME);
    }
  });
});

describe("S-08.rules/4: the conversation is a task screen on a phone only", () => {
  it('F-SPACE.shell: every rule keyed on data-mode="task" sits in the phone query, so desktop looks the same', () => {
    const sheets = [
      "foundation.css",
      "globals.css",
      "offer.css",
      "shell.css",
      "components.css",
      "motion.css",
      "ds-app.css",
    ];
    const task = sheets.flatMap((sheet) =>
      rules(read(sheet))
        .filter((r) => r.selectors.some((s) => s.includes('data-mode="task"')))
        .map((r) => `${sheet}: ${r.at}`),
    );
    expect(task.length).toBeGreaterThan(0);
    expect(task.every((t) => t.endsWith("@media (max-width: 640px)"))).toBe(true);
  });
});

describe("F-MOTION.arrive/4: a block holding a pinned bar fades in, so the bar never rides up with it", () => {
  const all = rules(read("motion.css"));
  const text = (r: Rule) => r.selectors.join(",");
  const pinned = all.findIndex((r) => /\):has\(\.mo-pin,\s*\.cv-box\)/.test(text(r)));

  it("S-08.rules/4: the pinned block takes moFade, only where motion is allowed", () => {
    expect(pinned).toBeGreaterThan(-1);
    const rule = all[pinned]!;
    expect(rule.at).toBe("@media (prefers-reduced-motion: no-preference)");
    expect(rule.decls.get("animation-name")).toBe("moFade");
  });

  it("moFade moves nothing: no translate, scale, transform or filter", () => {
    const body = read("motion.css").match(/@keyframes moFade\s*\{([\s\S]*?)\n\}/)?.[1] ?? "";
    expect(body).toMatch(/opacity:\s*0/);
    expect(body).not.toMatch(/translate|scale|transform|filter/);
  });

  it("it comes after every arrival and hand-over rule of the same weight, so it wins after a hand-over too", () => {
    const arrivals = all
      .map((r, i) => ({ i, t: text(r) }))
      .filter(({ t }) => t.includes("main#main:not(:has(.launch"))
      .map(({ i }) => i)
      .filter((i) => i !== pinned);
    expect(arrivals.length).toBeGreaterThan(3);
    expect(Math.max(...arrivals)).toBeLessThan(pinned);
  });

  it("its two arms are the base arrival rule's own, so the two cannot drift apart", () => {
    const squash = (r: Rule) => text(r).replace(/\s+/g, "");
    const base = all.find((r) => text(r).startsWith("main#main:not(:has(.launch"));
    expect(base).toBeDefined();
    expect(squash(all[pinned]!)).toBe(`:is(${squash(base!)}):has(.mo-pin,.cv-box)`);
  });

  it("the conversation's box is the fixed bar it names: .cv-box is position fixed on a phone", () => {
    const convo = readFileSync(
      fileURLToPath(new URL("../../src/components/convo/conversation.css", import.meta.url)),
      "utf8",
    );
    const box = rules(convo).filter((r) => r.selectors.includes(".cv-box") && r.at.includes("max-width"));
    expect(box.some((r) => r.decls.get("position") === "fixed")).toBe(true);
  });
});
