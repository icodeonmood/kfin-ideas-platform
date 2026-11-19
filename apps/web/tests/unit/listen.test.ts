import { describe, expect, it, vi } from "vitest";

import { BANNERS, switchesFor } from "@/lib/killswitch-routes";
import policy from "@/lib/rbac.json";
import { isIdeaRef, listenAudio, listenChapters } from "@/server/listen";

const calls: string[] = [];
vi.mock("@/server/worker", () => ({
  workerFetch: async (path: string) => {
    calls.push(path);
    return Response.json({ error: "forbidden" }, { status: 403 });
  },
}));

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

  it("BLD-C198: the signed-in person goes to the worker, which refuses anyone not on the desk or committee", async () => {
    calls.length = 0;
    const who = "33333333-4444-4555-8666-777777777777";
    const audio = await listenAudio(id, who, null);
    const chapters = await listenChapters(id, who);
    expect(calls).toEqual([
      `/internal/listen/${id}?user_id=${who}`,
      `/internal/listen/${id}/chapters?user_id=${who}`,
    ]);
    // An admin with no desk or committee grant: the worker's 403 reaches the player, which plays nothing.
    expect(audio.status).toBe(403);
    expect(await audio.json()).toEqual({ error: "forbidden" });
    expect(chapters.status).toBe(403);
  });
});
