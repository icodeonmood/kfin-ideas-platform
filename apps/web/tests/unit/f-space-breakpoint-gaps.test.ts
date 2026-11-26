/**
 * F-SPACE breakpoints (BLD-D027): no gap between a phone rule and the wide rule beside it. At fractional zoom or
 * device-pixel widths a viewport can be 640.5px wide. There neither `(max-width: 640px)` nor `(min-width: 641px)`
 * holds, so both sets of rules drop. The range form `(width > 640px)` closes the gap. The same pair sits at 1100/1101
 * (S-03 Home, lane C's file) and 759/760 (the Inbox, lane A's file), changed the same way.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

import { holdsAt, SRC } from "./helpers/css-rules";

/** A wide rule written one pixel above its phone rule: the form BLD-D027 replaced. */
const ONE_PIXEL_ABOVE = /min-width:\s*(641|1101|760)px/;

function sources(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) out.push(...sources(path));
    else if (/\.(css|ts|tsx)$/.test(name)) out.push(path);
  }
  return out;
}

describe("F-SPACE breakpoints (BLD-D027): no gap at fractional widths", () => {
  it("no CSS or TS file under apps/web/src opens a wide rule at min-width 641px, 1101px or 760px", () => {
    const hits: string[] = [];
    for (const file of sources(SRC)) {
      readFileSync(file, "utf8")
        .split("\n")
        .forEach((line, i) => {
          if (ONE_PIXEL_ABOVE.test(line)) hits.push(`${relative(SRC, file)}:${i + 1}`);
        });
    }
    expect(hits).toEqual([]);
  });

  it("at 640.5px the wide rule holds and the phone rule does not; at 640px it is the other way round", () => {
    expect(holdsAt("@media (max-width: 640px)", 640.5)).toBe(false);
    expect(holdsAt("@media (width > 640px)", 640.5)).toBe(true);
    expect(holdsAt("@media (max-width: 640px)", 640)).toBe(true);
    expect(holdsAt("@media (width > 640px)", 640)).toBe(false);
    // The gap the old form left: neither side held.
    expect(holdsAt("@media (min-width: 641px)", 640.5)).toBe(false);
  });

  it("the range form keeps every other condition in a compound query", () => {
    const fly = "@media (width > 640px) and (prefers-reduced-motion: no-preference)";
    expect(holdsAt(fly, 1440)).toBe(true);
    expect(holdsAt(fly, 1440, true)).toBe(false);
    expect(holdsAt(fly, 360)).toBe(false);
  });
});
