/**
 * The foundation (lane D; F-COLOR, F-SPACE, F-MOTION; DEC-102, BLD-D010). The pack's tokens.css is imported unchanged so
 * a TOKEN delta changes one value; later sheets only alias it; the colour pairs the pack relies on meet WCAG, including
 * the tab counts' and countdown pills' words on their fills (C-TABS/1, C-PILL.rules/3); and the FLIP helper's maths is
 * right.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Pill, type PillVariant } from "@/components/ui/pill";
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

/** The declarations of the rule whose selector is exactly `selector` in a sheet (components.css by default). */
function componentRule(selector: string, sheet = "components.css"): Record<string, string> {
  const css = read(`${APP}${sheet}`).replace(/\/\*[\s\S]*?\*\//g, "");
  const esc = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const body = css.match(new RegExp(`(?:^|\\})\\s*${esc}\\s*\\{([^}]*)\\}`))?.[1];
  if (body === undefined) throw new Error(`${sheet} has no rule ${selector}`);
  return Object.fromEntries(
    body
      .split(";")
      .map((d) => d.trim())
      .filter(Boolean)
      .map((d) => [d.slice(0, d.indexOf(":")).trim(), d.slice(d.indexOf(":") + 1).trim()]),
  );
}

/** A CSS colour as painted over `under` (a hex): a token, a hex, white, transparent or an rgba() fill. */
function paint(value: string, under: string, tokens: Map<string, string>): string {
  const token = value.trim().match(/^var\((--[\w-]+)\)$/);
  if (token) return paint(tokens.get(token[1]!) ?? "", under, tokens);
  const v = value.trim().toLowerCase();
  if (v === "transparent") return under;
  if (v === "white" || v === "#fff") return "#ffffff";
  if (/^#[0-9a-f]{6}$/.test(v)) return v;
  const fill = v.match(/^rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)$/);
  if (!fill) throw new Error(`cannot paint ${value}`);
  const [r, g, b, a] = fill.slice(1).map(Number) as [number, number, number, number];
  const u = under.replace("#", "");
  return `#${[r, g, b]
    .map((c, i) => Math.round(c * a + parseInt(u.slice(i * 2, i * 2 + 2), 16) * (1 - a)))
    .map((c) => c.toString(16).padStart(2, "0"))
    .join("")}`;
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

  it("C-PILL.variants, F-COLOR.contrast: white words on the band pill reach 4.5:1 over both band ends and the slab (BLD-D012)", () => {
    const css = read(`${APP}components.css`).replace(/\/\*[\s\S]*?\*\//g, "");
    const rule = css.match(/(?:^|\})\s*\.pill\.band\s*\{([^}]*)\}/)?.[1] ?? "";
    expect(
      rule
        .match(/(?:^|;)\s*color:\s*([^;]+);/)?.[1]
        ?.trim()
        .toLowerCase(),
    ).toMatch(/^(#fff|#ffffff|white)$/);
    const fill = rule.match(/background:\s*rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)/);
    if (!fill) throw new Error(`.pill.band background is not an rgba() fill: ${rule.trim()}`);
    const [r, g, b, a] = fill.slice(1).map(Number) as [number, number, number, number];
    const over = (bg: string) => {
      const v = bg.replace("#", "");
      return `#${[r, g, b]
        .map((c, i) => Math.round(c * a + parseInt(v.slice(i * 2, i * 2 + 2), 16) * (1 - a)))
        .map((c) => c.toString(16).padStart(2, "0"))
        .join("")}`;
    };
    // The pack's gradient band runs #3455ec to #f58256; the Shipped pill on a One's post sits on --slab.
    for (const bg of ["#3455ec", "#f58256", hex("--slab")])
      expect(contrast("#ffffff", over(bg)), `white on .pill.band over ${bg}`).toBeGreaterThanOrEqual(4.5);
  });

  it("C-TABS/1: every count is a 22px pill in tabular figures, as the board draws it (Desk .mtab .n)", () => {
    const n = componentRule(".tab-n");
    expect(n).toMatchObject({
      "min-width": "22px",
      height: "22px",
      padding: "0 7px",
      "border-radius": "var(--r-pill)",
      background: "rgba(17, 17, 17, 0.06)",
      color: "var(--mute2)",
      font: "600 12px/22px var(--ft)",
      "font-variant-numeric": "tabular-nums",
    });
    expect(componentRule('[aria-selected="true"] > .tab-n')).toMatchObject({
      background: "var(--ink)",
      color: "#ffffff",
    });
  });

  it("C-TABS/1, F-COLOR.contrast: a count reaches 4.5:1 on its disc over --paper, selected or not", () => {
    for (const sel of [".tab-n", '[aria-selected="true"] > .tab-n']) {
      const r = componentRule(sel);
      const disc = paint(r.background!, hex("--paper"), t);
      expect(contrast(paint(r.color!, disc, t), disc), `${sel} on ${disc}`).toBeGreaterThanOrEqual(4.5);
    }
  });
});

describe("F-TYPE.rules/5: avatar initials are 12px or larger", () => {
  it.each([".av", ".av-36", ".av-32", ".av-28", ".crew-face"])("%s", (sel) => {
    const r = componentRule(sel, "shell.css");
    const size = (r["font-size"] ?? r.font ?? "").match(/(\d+(?:\.\d+)?)px/)?.[1];
    expect(Number(size), `${sel} font size`).toBeGreaterThanOrEqual(12);
  });
});

describe("C-PILL.rules/3, S-R1.layout/4: the countdown pill", () => {
  const t = packTokens();
  // Pill holds no state, so calling it gives the element to render
  const pill = (variant: PillVariant | undefined, countdown: boolean) =>
    renderToStaticMarkup(Pill({ variant, countdown, children: "3 days to answer" }));

  it.each([
    [undefined, "due"],
    ["neutral", "due"],
    ["warn", "due soon"],
    ["bad", "due over"],
    ["ok", "due done"],
  ] as const)("variant %s draws a clock and no dot, as class %s", (variant, cls) => {
    const html = pill(variant, true);
    expect(html).toMatch(new RegExp(`^<span class="${cls}"><svg[^>]*aria-hidden="true"`));
    expect(html).not.toContain("<i");
    expect(html).toContain("3 days to answer");
  });

  it("a Pill without countdown is unchanged: the dot, the pill class, no clock", () => {
    expect(pill("bad", false)).toBe(
      '<span class="pill bad"><i aria-hidden="true"></i>3 days to answer</span>',
    );
    expect(pill(undefined, false)).toBe(
      '<span class="pill"><i aria-hidden="true"></i>3 days to answer</span>',
    );
  });

  it("the board's look (Desk .due): 28px, 0 11px 0 9px, 6px gap, 500 13px/1, tabular figures", () => {
    expect(componentRule(".due")).toMatchObject({
      "min-height": "28px",
      padding: "0 11px 0 9px",
      gap: "6px",
      font: "500 13px/1 var(--ft)",
      "font-variant-numeric": "tabular-nums",
      background: "rgba(17, 17, 17, 0.05)",
      color: "var(--ink2)",
    });
  });

  it("overdue is solid: white words on --badT", () => {
    expect(componentRule(".due.over")).toMatchObject({ background: "var(--badT)", color: "#ffffff" });
  });

  it.each([".due", ".due.soon", ".due.over", ".due.done"])(
    "F-COLOR.contrast: %s words reach 4.5:1 on its fill over --paper and --card",
    (sel) => {
      const own = componentRule(sel);
      const base = componentRule(".due");
      for (const under of [t.get("--paper")!, t.get("--card")!]) {
        const fill = paint(own.background ?? base.background!, under, t);
        const words = paint(own.color ?? base.color!, fill, t);
        expect(contrast(words, fill), `${sel} over ${under}`).toBeGreaterThanOrEqual(4.5);
      }
    },
  );
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

describe("F-MOTION.inside: the 1% spark", () => {
  it("eighteen slashes spread round the circle, 46 to 116 px out, in the pack's six colours", async () => {
    const { sparkPaths } = await import("@/lib/motion/spark");
    let seed = 0.37;
    const random = () => (seed = ((seed * 9301 + 49297) % 233280) / 233280);
    const paths = sparkPaths(18, random);
    expect(paths).toHaveLength(18);
    for (const p of paths) {
      const d = Math.hypot(p.dx, p.dy);
      expect(d).toBeGreaterThanOrEqual(46);
      expect(d).toBeLessThanOrEqual(116);
      expect(p.duration).toBeGreaterThanOrEqual(760);
      expect(p.duration).toBeLessThanOrEqual(1120);
    }
    expect(new Set(paths.map((p) => p.colour)).size).toBe(6);
  });
});
