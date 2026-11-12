import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/*
 * DEC-098: a tier colour is light and fill, never text. Tiers 6 and 7 fail as text on the dark panel (3.6:1 and 2.8:1),
 * so a One's number is solid white (DEC-101) and the tier shows as a dash, a dot and a soft light. This fails on any
 * `color:` set from a tier colour in the app's own code: a style object fed `tier_colour`, or CSS
 * `color: var(--tier-N)`. Fills, glows, borders and SVG paint are fine.
 */
const SRC = fileURLToPath(new URL("../../src", import.meta.url));

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : [path];
  });
}

const TSX_TEXT_COLOUR = /(?<![-\w])color\s*:\s*[^,}\n]*tier_colou?r/;
const CSS_TEXT_COLOUR = /(?<![-\w])color\s*:\s*var\(--tier(-[1-7])?\b/;

describe("tier colours are never text (DEC-098)", () => {
  it("no component sets a text colour from tier_colour", () => {
    const offenders = files(SRC)
      .filter((f) => /\.(tsx|ts)$/.test(f))
      .flatMap((f) =>
        readFileSync(f, "utf8")
          .split("\n")
          .map((line, i) => (TSX_TEXT_COLOUR.test(line) ? `${relative(SRC, f)}:${i + 1}` : null))
          .filter((x): x is string => x !== null),
      );
    expect(offenders).toEqual([]);
  });

  it("no app stylesheet sets a text colour from a tier token", () => {
    const offenders = files(SRC)
      .filter((f) => f.endsWith(".css"))
      .flatMap((f) =>
        readFileSync(f, "utf8")
          .split("\n")
          .map((line, i) => (CSS_TEXT_COLOUR.test(line) ? `${relative(SRC, f)}:${i + 1}` : null))
          .filter((x): x is string => x !== null),
      );
    expect(offenders).toEqual([]);
  });
});
