/**
 * Accessibility and type checks on lane D's shell and shared components, read from the sheets as written (F-TYPE,
 * F-A11Y; C-FILE, C-SIDEBAR, C-TASKBAR, C-PHONE-TABS, C-SEARCH's question box, C-ONES-FAN). Each is a review note
 * that a screenshot would not catch until a person printed, zoomed or tabbed.
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

/** The declarations for a selector, later rules winning, optionally only inside a given at-rule. */
function style(sheet: string, selector: string, at?: (a: string) => boolean): Map<string, string> {
  const merged = new Map<string, string>();
  for (const r of rules(read(sheet)))
    if (r.selectors.includes(selector) && (at ? at(r.at) : r.at === ""))
      for (const [k, v] of r.decls) merged.set(k, v);
  return merged;
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
