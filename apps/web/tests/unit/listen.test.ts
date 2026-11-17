import { describe, expect, it } from "vitest";

import { BANNERS, switchesFor } from "@/lib/killswitch-routes";
import policy from "@/lib/rbac.json";
import { isIdeaRef } from "@/server/listen";

const id = "11111111-2222-4333-8444-555555555555";

describe("BLD-C114 Listen in Sarvam's voice (DEC-108 (4), L-LISTEN, C-LISTEN)", () => {
  it("audio and chapters need lane B's desk.listen and speech.hosted", () => {
    for (const path of [
      `/api/ideas/${id}/listen`,
      `/api/ideas/${id}/listen/chapters`,
      "/api/ideas/IDEA-2026-000123/listen",
    ])
      expect(switchesFor("GET", path).sort()).toEqual(["desk.listen", "speech.hosted"]);
    expect(switchesFor("HEAD", `/api/ideas/${id}/listen`).sort()).toEqual(["desk.listen", "speech.hosted"]);
    expect(BANNERS["desk.listen"]).toBe(
      "Listening to an idea is paused for now. You can still read it on the page.",
    );
  });

  it("desk and committee only (view_review_queue)", () => {
    const endpoints = (policy as { endpoints: string[] }).endpoints.map((l) =>
      l.split(/\s+/).slice(0, 3).join(" "),
    );
    expect(endpoints).toContain("GET /api/ideas/{id}/listen view_review_queue");
    expect(endpoints).toContain("GET /api/ideas/{id}/listen/chapters view_review_queue");
  });

  it("takes an IDEA- reference or a uuid, nothing else", () => {
    expect(isIdeaRef("IDEA-2026-000123")).toBe(true);
    expect(isIdeaRef(id)).toBe(true);
    for (const bad of ["", "../x", "IDEA-26-1", `${id}/x`]) expect(isIdeaRef(bad)).toBe(false);
  });
});
