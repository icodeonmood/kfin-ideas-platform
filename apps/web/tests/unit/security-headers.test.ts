/** DEC-096: the microphone is allowed on the share pages only; everything else keeps it off. */
import { describe, expect, it } from "vitest";

import nextConfig, { headerRules, PERMISSIONS_POLICY, PERMISSIONS_POLICY_SHARE } from "../../next.config";

/** The Permissions-Policy a path ends up with: Next.js applies matching rules in order, the last value wins. */
function policyFor(path: string): string | undefined {
  let value: string | undefined;
  for (const rule of headerRules()) {
    const prefix = rule.source.replace("/:path*", "");
    if (path === prefix || path.startsWith(`${prefix}/`) || prefix === "") {
      for (const h of rule.headers) if (h.key === "Permissions-Policy") value = h.value;
    }
  }
  return value;
}

describe("Permissions-Policy (DEC-096)", () => {
  it("allows the microphone for this site on /share pages only", () => {
    expect(policyFor("/share/0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10")).toBe(PERMISSIONS_POLICY_SHARE);
    expect(policyFor("/share")).toBe(PERMISSIONS_POLICY_SHARE);
    for (const path of ["/", "/my-ideas", "/wall", "/review/x", "/admin", "/launch", "/shared-thing"]) {
      expect(policyFor(path), path).toBe(PERMISSIONS_POLICY);
    }
  });

  it("never allows the microphone to other origins, and keeps the camera and location off everywhere", () => {
    for (const value of [PERMISSIONS_POLICY, PERMISSIONS_POLICY_SHARE]) {
      expect(value).toContain("camera=()");
      expect(value).toContain("geolocation=()");
      expect(value).not.toMatch(/microphone=\*|microphone=\(\s*\*|microphone=\(self [^)]/);
    }
    expect(PERMISSIONS_POLICY).toContain("microphone=()");
  });

  it("is what next.config.ts serves, with the other security headers on every page", async () => {
    const rules = await nextConfig.headers!();
    expect(rules).toEqual(headerRules());
    const keys = rules[0]!.headers.map((h) => h.key);
    expect(keys).toEqual(
      expect.arrayContaining([
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
      ]),
    );
  });
});
