import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// Read from the source, not imported: the proxy pulls in server-only modules. Next.js compiles the same pattern.
const source = readFileSync(fileURLToPath(new URL("../../src/proxy.ts", import.meta.url)), "utf8");
const pattern = /matcher:\s*\["([^"]+)"\]/.exec(source)?.[1] ?? "";
const covered = (path: string) => new RegExp(`^${pattern}$`).test(path);

describe("proxy matcher", () => {
  it("leaves the brand marks public, so emails can load them with no session", () => {
    expect(covered("/brand/email-mark-white@2x.png")).toBe(false);
    expect(covered("/brand/email-mark-white.png")).toBe(false);
  });

  it("still covers every page and API route", () => {
    for (const path of ["/", "/ember", "/my-ideas", "/api/ideas", "/brandnew", "/ember/brand/x"]) {
      expect(covered(path)).toBe(true);
    }
  });
});
