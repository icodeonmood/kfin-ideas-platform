/** BLD-C090, BLD-C092 (L-SIMILAR, A-API.idea-preview): which ideas the routes accept, and who reaches them. */
import { describe, expect, it } from "vitest";

import { decide, effectiveRoles } from "@/lib/rbac";
import { isIdeaKey } from "@/server/similar";

describe("BLD-C090 idea keys", () => {
  it("takes an IDEA- reference or a row ID, and nothing else", () => {
    expect(isIdeaKey("IDEA-2026-001412")).toBe(true);
    expect(isIdeaKey("0b4c6f6e-8d1a-4c3e-9a51-2f0f6f1f6a10")).toBe(true);
    expect(isIdeaKey("IDEA-2026-1412")).toBe(false);
    expect(isIdeaKey("SUB-2026-001412")).toBe(false);
    expect(isIdeaKey("../internal/wall")).toBe(false);
    expect(isIdeaKey("")).toBe(false);
  });
});

describe("BLD-C090 BLD-C092 routes in the policy", () => {
  const everyone = effectiveRoles([]);
  for (const path of ["/api/ideas/IDEA-2026-001412/preview"]) {
    it(`${path}: any signed-in person reaches the handler, which decides what they see`, () => {
      expect(decide(everyone, "GET", path).kind).toBe("allow");
      expect(decide(everyone, "POST", path).kind).toBe("unknown");
    });
  }
});
