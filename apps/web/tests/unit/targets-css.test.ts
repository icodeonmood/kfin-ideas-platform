/**
 * F-SPACE.targets with WCAG 2.5.8 (BLD-D018): every target keeps a 24×24 px area that no other target covers, and the
 * 44 px hit areas the pack asks for never sit on top of a neighbouring target. axe's `target-size` rule found four
 * targets partly covered on main (docs/WCAG22_POST_LAUNCH.md, CI run 44398344925); the causes in lane D's shared
 * sheets are pinned here, read from the sheets as written (jsdom cannot lay out; the layout itself is proven by the
 * e2e axe checks in CI).
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

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

/** The declarations for a selector, later rules winning, only inside the at-rules `at` accepts ("" = none). */
function style(
  sheet: string,
  selector: string,
  at: (a: string) => boolean = (a) => a === "",
): Map<string, string> {
  const merged = new Map<string, string>();
  for (const r of rules(read(sheet)))
    if (r.selectors.includes(selector) && at(r.at)) for (const [k, v] of r.decls) merged.set(k, v);
  return merged;
}

const FOLDED = (a: string) => a === "@container sbar (max-width: 120px)";

/** The app's global sheets in the order the root layout imports them, so a later sheet wins as in the browser. */
const SHEETS = [...read("layout.tsx").matchAll(/^import "\.\/([\w-]+\.css)";$/gm)].map((m) => m[1]!);

/** The declarations every global sheet gives a selector outside any at-rule, in import order (later wins). */
function cascade(selector: string): Map<string, string> {
  const merged = new Map<string, string>();
  for (const sheet of SHEETS) for (const [k, v] of style(sheet, selector)) merged.set(k, v);
  return merged;
}

describe("F-SPACE.targets, C-SIDEBAR.anatomy/4–5: a section's rows never slide under the account row", () => {
  it("open, the sections keep their full height, so the bar scrolls instead of stacking rows under Account", () => {
    const sec = style("shell.css", ".sb-sec");
    expect(sec.get("flex-shrink")).toBe("0");
    expect(sec.get("min-height") ?? "auto").not.toBe("0");
  });

  it("the open bar is the one that scrolls (.sb-in), with the account row pushed to its foot", () => {
    expect(style("shell.css", ".sb-in").get("overflow-y")).toBe("auto");
    expect(style("shell.css", ".acct-up").get("margin-top")).toBe("auto");
  });

  it("folded, the hidden sections shrink to nothing, so the account row stays at the foot", () => {
    const sec = style("shell.css", ".sb-sec", FOLDED);
    expect(sec.get("visibility")).toBe("hidden");
    expect(sec.get("min-height")).toBe("0");
    expect(sec.get("flex-shrink")).toBe("1");
  });
});

describe("F-SPACE.targets, F-A11Y.rules/2: the skip link, with focus, covers no other target", () => {
  it("reads the global sheets in the root layout's order, ds-app.css last", () => {
    expect(SHEETS.at(-1)).toBe("ds-app.css");
    expect(SHEETS).toEqual(expect.arrayContaining(["globals.css", "shell.css", "ds-app.css"]));
  });

  it("rests off the page, laid over it", () => {
    const rest = cascade(".skip-link");
    expect(rest.get("position")).toBe("absolute");
    expect(rest.get("top")).toBe("-4rem");
  });

  it("with focus takes its own row in the flow, so the page moves down under it (S-02's mark was left 8 px clear)", () => {
    const focus = cascade(".skip-link:focus");
    expect(focus.get("position")).toBe("relative");
    expect(focus.get("top")).toBe("auto");
    expect(focus.get("left")).toBe("auto");
    expect(focus.get("display")).toBe("block");
    expect(focus.get("width")).toBe("fit-content");
    expect(focus.get("z-index")).toBe("var(--z-skip)");
  });

  it("in the signed-in shell, starts after the fixed sidebar rather than over its brand", () => {
    const signedIn = cascade(".skip-link:focus:has(~ .shell:not(.shell-public))");
    expect(signedIn.get("margin-inline-start")).toBe("calc(var(--sbw) + var(--space-4))");
  });
});

const COARSE = (a: string) => a === "@media (pointer: coarse)";
const px = (v: string | undefined) => parseFloat(v ?? "NaN");

describe("F-SPACE.targets/2, C-BUTTON.variants (DEC-126): the quiet link is padded to 44px on touch, 24px with a mouse", () => {
  it("with a mouse the target stays at least 24×24px and draws no extra layer", () => {
    const quiet = style("offer.css", ".link-quiet");
    expect(px(quiet.get("min-height"))).toBeGreaterThanOrEqual(24);
    expect(px(quiet.get("min-width"))).toBeGreaterThanOrEqual(24);
    for (const sheet of SHEETS)
      for (const sel of [".link-quiet::after", ".link-quiet::before"])
        expect(style(sheet, sel).size, `${sheet} ${sel} outside the touch rule`).toBe(0);
  });

  it("on touch an empty layer reaches 10px past each side and 20px below, never above, so the hit area is 44px both ways and stays off Requested (DEC-126)", () => {
    const quiet = style("offer.css", ".link-quiet");
    expect(style("offer.css", ".link-quiet", COARSE).get("position")).toBe("relative");
    const pad = style("offer.css", ".link-quiet::after", COARSE);
    expect(pad.get("content")).toBe('""');
    expect(pad.get("position")).toBe("absolute");
    // The inset shorthand, expanded as CSS does: 1 to 4 values for top, right, bottom, left.
    const v = (pad.get("inset") ?? "").trim().split(/\s+/).map(px);
    const top = v[0] ?? NaN;
    const right = v[1] ?? top;
    const bottom = v[2] ?? top;
    const left = v[3] ?? right;
    // "Withdraw" sits 4px under "Requested" (.tu-req gap --sp-4): the layer may not reach up into it.
    expect(top).toBeGreaterThanOrEqual(-2);
    expect(px(quiet.get("min-height")) - top - bottom).toBeGreaterThanOrEqual(44);
    expect(px(quiet.get("min-width")) - left - right).toBeGreaterThanOrEqual(44);
  });

  it("the look and the layout do not change on touch: the box keeps its size and the layer draws nothing", () => {
    expect([...style("offer.css", ".link-quiet", COARSE).keys()]).toEqual(["position"]);
    expect([...style("offer.css", ".link-quiet::after", COARSE).keys()].sort()).toEqual([
      "content",
      "inset",
      "position",
    ]);
  });
});

describe('F-SPACE.targets/2, C-PROMPT.attach (DEC-124, BLD-D025): the box\'s file rows and its "+"', () => {
  const SHEET = "share/compose.css";

  it("the remove button's 32px circle is padded to at least 44px on touch, never reaching the 4px gap to Try again or past the row's 8px padding", () => {
    const x = style(SHEET, ".cz .cfile-x");
    expect(px(x.get("width"))).toBe(32);
    expect(px(x.get("height"))).toBe(32);
    expect(style(SHEET, ".cz .cfile-x", COARSE).get("position")).toBe("relative");
    const pad = style(SHEET, ".cz .cfile-x::after", COARSE);
    expect(pad.get("content")).toBe('""');
    expect(pad.get("position")).toBe("absolute");
    const v = (pad.get("inset") ?? "").trim().split(/\s+/).map(px);
    const top = v[0] ?? NaN;
    const right = v[1] ?? top;
    const bottom = v[2] ?? top;
    const left = v[3] ?? right;
    expect(32 - top - bottom).toBeGreaterThanOrEqual(44);
    expect(32 - left - right).toBeGreaterThanOrEqual(44);
    // The row actions sit 4px apart (`.frow-a` gap) and the row pads 8px on the right: the layer stays inside both.
    expect(px(style(SHEET, ".cz .cfiles .frow-a").get("gap"))).toBeGreaterThanOrEqual(-left);
    expect(-right).toBeLessThanOrEqual(8);
    // With a mouse there is no layer.
    expect(style(SHEET, ".cz .cfile-x::after").size).toBe(0);
  });

  it("the \"+\" takes lane D's shared look (BLD-D019): the prompt box's sheet no longer restyles .attach-btn", () => {
    for (const r of rules(read(SHEET)))
      for (const s of r.selectors) expect(s, `${SHEET}: ${s}`).not.toMatch(/\.attach-btn/);
  });
});
