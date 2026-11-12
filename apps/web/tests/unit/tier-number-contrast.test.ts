import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/*
 * DEC-098 and WCAG 1.4.3: a One's number is large text, so its solid lower part needs 3:1 on every ground it sits
 * on. The design system ends the number's gradient on the tier colour; ds-app.css gives each tier its own end
 * (`--num-end`), lightening Blue flame and Star. This computes each end from the tokens, the way the browser does
 * (`color-mix(in srgb, …)` mixes the gamma-encoded channels), and checks it on Zed, Graphite and the glow-up sheet.
 */
const APP = fileURLToPath(new URL("../../src/app/", import.meta.url));
const tokensCss = readFileSync(APP + "ds-tokens.css", "utf8");
const appCss = readFileSync(APP + "ds-app.css", "utf8");

type Rgb = [number, number, number];

const hex = (h: string): Rgb => {
  const m = /^#([0-9a-f]{6})$/i.exec(h.trim());
  if (!m) throw new Error(`not a 6-digit hex colour: ${h}`);
  const n = parseInt(m[1]!, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};

const token = (name: string): Rgb => {
  const m = new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})\\s*;`).exec(tokensCss);
  if (!m) throw new Error(`token --${name} not found in ds-tokens.css`);
  return hex(m[1]!);
};

const linear = (c: number) => {
  const s = c / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
};
const luminance = ([r, g, b]: Rgb) => 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
const contrast = (a: Rgb, b: Rgb) => {
  const hi = Math.max(luminance(a), luminance(b));
  const lo = Math.min(luminance(a), luminance(b));
  return (hi + 0.05) / (lo + 0.05);
};

/** The colour a `--num-end` value resolves to: a token, or a token mixed with white in sRGB. */
function resolve(value: string): Rgb {
  const plain = /^var\(--([a-z0-9-]+)\)$/.exec(value);
  if (plain) return token(plain[1]!);
  const mix = /^color-mix\(in srgb, var\(--([a-z0-9-]+)\) (\d+(?:\.\d+)?)%, #fff\)$/.exec(value);
  if (mix) {
    const p = Number(mix[2]) / 100;
    return token(mix[1]!).map((c) => c * p + 255 * (1 - p)) as Rgb;
  }
  throw new Error(`--num-end value the test cannot compute: ${value}`);
}

const ends = new Map<number, string>();
for (const m of appCss.matchAll(/\[data-tier="(\d)"\]\s*\{\s*--num-end:\s*([^;]+);\s*\}/g))
  ends.set(Number(m[1]), m[2]!.trim());

const GROUNDS: Record<string, Rgb> = {
  zed: token("zed"),
  graphite: token("graphite"),
  "glow-up sheet": hex("#202229"),
};

describe("a One's number keeps 3:1 at every tier (DEC-098)", () => {
  it("every tier, 0 to 7, sets its own number end", () => {
    expect([...ends.keys()].sort()).toEqual([0, 1, 2, 3, 4, 5, 6, 7]);
  });

  for (let tier = 0; tier <= 7; tier++) {
    it(`Tier ${tier}'s number end is at least 3:1 on Zed, Graphite and the glow-up sheet`, () => {
      const end = resolve(ends.get(tier) ?? "missing");
      for (const [name, ground] of Object.entries(GROUNDS)) {
        expect(contrast(end, ground), `Tier ${tier} on ${name}`).toBeGreaterThanOrEqual(3);
      }
    });
  }

  it("the jersey number and the glow-up number end on --num-end", () => {
    expect(appCss).toMatch(/\.jersey-num\s*\{[^}]*var\(--num-end,[^}]*\}/);
    expect(appCss).toMatch(/\.glow-up\s*\{\s*--heat-anim:\s*var\(--num-end,/);
    expect(appCss).toMatch(/\.glow-num\s*\{[^}]*var\(--heat-anim\)[^}]*\}/);
  });

  it("without the lighter end, Tier 7's own colour would fail (keeps this test honest)", () => {
    expect(contrast(token("tier-7"), token("graphite"))).toBeLessThan(3);
  });
});
