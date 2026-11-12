import { existsSync, readFileSync } from "node:fs";
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
    expect(covered("/brand/email-mark-ink@2x.png")).toBe(false);
  });

  it("still covers every page and API route", () => {
    for (const path of [
      "/",
      "/ember",
      "/my-ideas",
      "/api/ideas",
      "/brandnew",
      "/ember/brand/x",
      "/ds/opc.js",
      "/dsx",
      "/ember/ds/x",
    ]) {
      expect(covered(path)).toBe(true);
    }
  });

  // Excluded paths skip sign-in and the kill-switch check (non-negotiable 9). Only static files may live there:
  // a page or route handler under app/brand would be public without anyone noticing. /ds/ is no longer excluded
  // (DEC-101 dropped the design system's script), so it is covered like any other path.
  it("has no page or route under the public static paths", () => {
    for (const dir of ["brand"]) {
      expect(existsSync(fileURLToPath(new URL(`../../src/app/${dir}`, import.meta.url)))).toBe(false);
    }
  });
});
