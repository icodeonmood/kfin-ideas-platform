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
function style(sheet: string, selector: string, at: (a: string) => boolean = (a) => a === ""): Map<string, string> {
  const merged = new Map<string, string>();
  for (const r of rules(read(sheet)))
    if (r.selectors.includes(selector) && at(r.at)) for (const [k, v] of r.decls) merged.set(k, v);
  return merged;
}

const FOLDED = (a: string) => a === "@container sbar (max-width: 120px)";

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
