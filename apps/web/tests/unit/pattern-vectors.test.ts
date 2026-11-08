/**
 * AT-B3-03 (TypeScript half): the browser/server engine must find exactly what the Python engine finds on the
 * shared vectors, span for span. Vectors are generated at run time by `python -m pii.vectors` (never stored).
 */
import { execFileSync } from "node:child_process";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { scan } from "@/lib/pii/patterns";

type Found = { pattern: string; action: string; start: number; end: number };
type Vector = { id: string; text: string; python: Found[]; expect: { blocks: boolean; warns: boolean } };

const worker = path.resolve(__dirname, "../../../../services/worker");
const data = JSON.parse(
  execFileSync("uv", ["run", "--frozen", "python", "-m", "pii.vectors", "--n", "20"], {
    cwd: worker,
    encoding: "utf8",
    env: { ...process.env, APP_ENV: "test" },
    maxBuffer: 32 * 1024 * 1024,
  }),
) as { kfin_domains: string[]; count: number; vectors: Vector[] };

const sorted = (xs: Found[]) =>
  [...xs].sort((a, b) => a.start - b.start || a.pattern.localeCompare(b.pattern) || a.end - b.end);

describe("shared pattern vectors (AT-B3-03)", () => {
  it("has a full set", () => {
    expect(data.count).toBeGreaterThanOrEqual(300);
  });

  it("TypeScript finds exactly what Python finds on every vector", () => {
    const mismatches: string[] = [];
    for (const v of data.vectors) {
      const ts = scan(v.text, data.kfin_domains).map((m) => ({
        pattern: m.patternId,
        action: m.action,
        start: m.start,
        end: m.end,
      }));
      if (JSON.stringify(sorted(ts)) !== JSON.stringify(sorted(v.python))) mismatches.push(v.id);
    }
    expect(mismatches).toEqual([]);
  });

  it("blocks and warns as each vector expects", () => {
    for (const v of data.vectors) {
      const found = scan(v.text, data.kfin_domains);
      const blocks = found.some((m) => m.action === "block");
      expect(blocks, v.id).toBe(v.expect.blocks);
      if (v.expect.warns)
        expect(
          found.some((m) => m.action === "warn"),
          v.id,
        ).toBe(true);
    }
  });
});
