/**
 * S-03 Home (BLD-D017): the question scales with its column up to 28px, as Home.dc.html:641-642 draws it, and can
 * still wrap (no nowrap), so a long first name never pushes the page sideways; the phone rule (640px and narrower)
 * keeps its 32px. Your ideas and Find your crew start level in two columns: globals.css's old `section + section`
 * margin is cancelled there only, so the stacked layout keeps its spacing. Layout itself was measured in a browser at
 * 641, 768, 1024, 1280 and 1440 px (no overflow; one line at every width for the longest seeded first name); jsdom cannot
 * lay out, so this pins the rules that measurement depends on.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const CSS = readFileSync(resolve(__dirname, "../../src/app/home/home.css"), "utf8").replace(
  /\/\*[\s\S]*?\*\//g,
  "",
);

/** Every top-level or nested block whose selector list is exactly `selector`, with the @media it sits in (or ""). */
function blocks(selector: string): Array<{ media: string; body: string }> {
  const out: Array<{ media: string; body: string }> = [];
  const stack: string[] = [];
  let head = "";
  for (let i = 0; i < CSS.length; i++) {
    const c = CSS[i]!;
    if (c === "{") {
      const sel = head.trim();
      if (sel.startsWith("@")) {
        stack.push(sel);
      } else {
        const end = CSS.indexOf("}", i);
        if (sel === selector) out.push({ media: stack.at(-1) ?? "", body: CSS.slice(i + 1, end) });
        i = end;
      }
      head = "";
    } else if (c === "}") {
      stack.pop();
      head = "";
    } else if (c === ";" && stack.length === 0) {
      head = "";
    } else {
      head += c;
    }
  }
  return out;
}

describe("S-03 Home hero question (BLD-D017; Home.dc.html:641-642)", () => {
  it("measures its column: .hm-hero-in is an inline-size container", () => {
    const [base] = blocks(".hm-hero-in").filter((b) => b.media === "");
    expect(base?.body).toMatch(/container-type:\s*inline-size/);
  });

  it("scales with the column up to 28px, without a width cap", () => {
    const [base] = blocks(".hm-hello").filter((b) => b.media === "");
    expect(base?.body).toMatch(/font:\s*500 clamp\(16px, 3\.75cqi, 28px\)\s*\/\s*1\.12 var\(--fd\)/);
    expect(base?.body).toMatch(/max-width:\s*none/);
  });

  it("never refuses to wrap, so a long name cannot push the page sideways", () => {
    for (const b of blocks(".hm-hello")) expect(b.body).not.toMatch(/white-space:\s*nowrap/);
  });

  it("keeps the phone's 32px question at 640px and narrower", () => {
    const phone = blocks(".hm-hello").filter((b) => /max-width:\s*640px/.test(b.media));
    expect(phone.map((b) => /font-size:\s*32px/.test(b.body))).toEqual([true]);
  });
});

describe("S-03 Home grid (BLD-D017): Your ideas and Find your crew start level", () => {
  it("cancels the old section + section margin in two columns only", () => {
    const rules = blocks(".hm-grid > section");
    const zeroed = rules.filter((b) => /margin-top:\s*0\b/.test(b.body));
    expect(zeroed.map((b) => b.media)).toEqual(["@media (width > 1100px)"]);
    expect(rules.filter((b) => b.media === "").every((b) => !/margin-top/.test(b.body))).toBe(true);
  });

  it("stacks into one column at the same width the margin rule stops (1100px)", () => {
    const stacked = blocks(".hm-grid,\n  .hm-needs").concat(blocks(".hm-grid"));
    expect(stacked.some((b) => /max-width:\s*1100px/.test(b.media))).toBe(true);
  });
});
