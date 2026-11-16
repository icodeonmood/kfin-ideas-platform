/**
 * The foundation (lane D; F-COLOR, F-SPACE, F-MOTION; DEC-102, BLD-D010). The pack's tokens.css is imported unchanged so
 * a TOKEN delta changes one value; later sheets only alias it; the colour pairs the pack relies on meet WCAG; and the
 * FLIP helper's maths is right.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { FLIP_LIMIT, invert, isStill } from "@/lib/motion/flip";

const APP = fileURLToPath(new URL("../../src/app/", import.meta.url));
const PACK = fileURLToPath(new URL("../../../../1pc-handoff/01-foundations/", import.meta.url));
const read = (path: string) => readFileSync(path, "utf8");

/** Every custom property tokens.css declares, with its value. */
function packTokens(): Map<string, string> {
  const out = new Map<string, string>();
  for (const m of read(`${APP}tokens.css`).matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g))
    out.set(m[1]!, m[2]!.trim());
  return out;
}

/** Each custom property a sheet declares, with the selector of the rule it sits in. */
function declarations(css: string): Array<{ name: string; selector: string }> {
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const out: Array<{ name: string; selector: string }> = [];
  const stack: string[] = [];
  let buf = "";
  for (const ch of clean) {
    if (ch === "{") {
      stack.push(buf.trim());
      buf = "";
    } else if (ch === "}") {
      stack.pop();
      buf = "";
    } else if (ch === ";") {
      const m = buf.trim().match(/^(--[\w-]+)\s*:/);
      if (m) out.push({ name: m[1]!, selector: stack.join(" ") });
      buf = "";
    } else buf += ch;
  }
  return out;
}

function luminance(hex: string): number {
  const v = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(v.slice(i, i + 2), 16) / 255);
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r!) + 0.7152 * lin(g!) + 0.0722 * lin(b!);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi! + 0.05) / (lo! + 0.05);
}

describe("F-COLOR tokens", () => {
  it("F-COLOR: apps/web/src/app/tokens.css is the pack's tokens.css, unchanged", () => {
    expect(read(`${APP}tokens.css`)).toBe(read(`${PACK}tokens.css`));
  });

  it("F-COLOR: no later sheet redefines a pack token at the root (a scoped override, like the dark slab's, is fine)", () => {
    const names = new Set(packTokens().keys());
    const rootLike = /(^|[\s,])(:root|html|body|\[data-theme="white"\])(?=[\s,]|$)/;
    const offenders = ["foundation.css", "globals.css", "offer.css", "motion.css", "ds-app.css"].flatMap(
      (sheet) =>
        declarations(read(`${APP}${sheet}`))
          .filter((d) => names.has(d.name) && rootLike.test(d.selector.replace(/@media[^{]*?\)\s*/g, "")))
          .filter((d) => !(sheet === "foundation.css" && (d.name === "--fd" || d.name === "--ft")))
          .map((d) => `${sheet}: ${d.name} in ${d.selector}`),
    );
    expect(offenders).toEqual([]);
  });

  it("F-TYPE.faces: --fd and --ft lead with the self-hosted variable families (BLD-D010)", () => {
    const decl = read(`${APP}foundation.css`);
    expect(decl).toMatch(/--fd:\s*"Inter Tight Variable"/);
    expect(decl).toMatch(/--ft:\s*"Inter Variable"/);
  });
});

describe("F-COLOR.contrast and F-A11Y.rules/1", () => {
  const t = packTokens();
  const hex = (name: string) => {
    const v = t.get(name);
    if (!v || !/^#[0-9a-f]{6}$/i.test(v)) throw new Error(`${name} is not a hex token: ${v}`);
    return v;
  };

  it.each([
    ["--ink", "--paper"],
    ["--mute", "--paper"],
    ["--mute", "--card"],
    ["--mute2", "--paper"],
    ["--blueT", "--card"],
    ["--blueT", "--wash"],
    ["--okT", "--okW"],
    ["--warnT", "--warnW"],
    ["--badT", "--badW"],
    ["--placeholder", "--card"],
    ["--noteBlueText", "--wash"],
  ])("text %s on %s reaches 4.5:1", (fg, bg) => {
    expect(contrast(hex(fg), hex(bg))).toBeGreaterThanOrEqual(4.5);
  });

  it("F-COLOR.contrast/2: a field border reaches 3:1 on white", () => {
    expect(contrast(hex("--fieldBorder"), hex("--card"))).toBeGreaterThanOrEqual(3);
  });

  it("F-COLOR.contrast/2: every field uses the 3:1 border, not the old --line-control", () => {
    const offer = read(`${APP}offer.css`);
    const rule = offer.slice(offer.indexOf(".input,\n.textarea,\n.select {"));
    expect(rule.slice(0, rule.indexOf("}"))).toContain("var(--fieldBorder)");
  });
});

describe("F-MOTION FLIP helper (BLD-E005)", () => {
  it("F-MOTION.inside: invert gives the move and scale back to the first box", () => {
    const t = invert(
      { left: 10, top: 100, width: 200, height: 40 },
      { left: 30, top: 40, width: 100, height: 40 },
    );
    expect(t).toEqual({ dx: -20, dy: 60, sx: 2, sy: 1 });
    expect(isStill(t)).toBe(false);
  });

  it("F-MOTION.inside: an element that did not move is left alone, and a zero size never divides by zero", () => {
    expect(
      isStill(invert({ left: 5, top: 5, width: 0, height: 0 }, { left: 5.2, top: 5, width: 0, height: 0 })),
    ).toBe(true);
  });

  it("F-MOTION.rules/7: a morph measures at most 180 elements", () => {
    expect(FLIP_LIMIT).toBe(180);
  });
});
