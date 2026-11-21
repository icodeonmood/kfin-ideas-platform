/**
 * DEC-128 (amends DEC-096; BLD-C221): the microphone is allowed for this site's own origin on every page, because a
 * Permissions-Policy is fixed when the document loads and the app's client-side routes keep the first page's policy.
 * No other origin and no wildcard; the camera and location stay off everywhere.
 */
import { describe, expect, it } from "vitest";

import nextConfig, { headerRules, PERMISSIONS_POLICY } from "../../next.config";

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

/** One feature's allow-list: "microphone=(self)" gives "(self)". */
function allowList(policy: string, feature: string): string | undefined {
  return policy
    .split(",")
    .map((p) => p.trim())
    .find((p) => p.startsWith(`${feature}=`))
    ?.slice(feature.length + 1);
}

const PATHS = [
  "/",
  "/home",
  "/share",
  "/share/0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10",
  "/my-ideas",
  "/crew",
  "/wall",
  "/ideas/IDEA-2026-001412",
  "/review/x",
  "/admin",
  "/launch",
  "/sign-in",
  "/shared-thing",
  "/api/drafts",
];

describe("Permissions-Policy (DEC-128, amends DEC-096)", () => {
  it("V-ACC C-PROMPT.voice: every path allows the microphone for this site only, so a client-side route to a box with a microphone keeps it", () => {
    for (const path of PATHS) {
      const value = policyFor(path);
      expect(value, path).toBe(PERMISSIONS_POLICY);
      expect(allowList(value!, "microphone"), path).toBe("(self)");
      expect(allowList(value!, "camera"), path).toBe("()");
      expect(allowList(value!, "geolocation"), path).toBe("()");
      expect(allowList(value!, "interest-cohort"), path).toBe("()");
    }
  });

  it("names each feature once, with no other origin and no wildcard anywhere", () => {
    expect(PERMISSIONS_POLICY.split(",").map((p) => p.trim())).toEqual([
      "camera=()",
      "microphone=(self)",
      "geolocation=()",
      "interest-cohort=()",
    ]);
    expect(PERMISSIONS_POLICY).not.toMatch(/\*|https?:|"|src/);
  });

  it("is one rule for every path, what next.config.ts serves, with the other security headers", async () => {
    const rules = await nextConfig.headers!();
    expect(rules).toEqual(headerRules());
    expect(rules.map((r) => r.source)).toEqual(["/:path*"]);
    expect(rules.flatMap((r) => r.headers).filter((h) => h.key === "Permissions-Policy")).toHaveLength(1);
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
