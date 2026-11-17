/**
 * Find your crew's route handlers (A-API.team-up, L-CREW/5–6): the session is checked, the signed-in person goes to
 * the worker as `user_id`, only the deck's filters pass through (repeated keys kept), and the pass body carries the
 * idea's reference alone. The worker's answer, errors included, comes back as it is.
 */
import { NextRequest, NextResponse } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const calls: { path: string; init: RequestInit }[] = [];
let signedInAs: { id: string } | NextResponse = { id: "0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10" };

vi.mock("@/server/auth/authorize", () => ({ signedIn: async () => signedInAs }));
vi.mock("@/server/worker", () => ({
  workerFetch: async (path: string, init: RequestInit = {}) => {
    calls.push({ path, init });
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  },
}));

const { passBody, workerPath } = await import("@/server/crew");
const deck = await import("@/app/api/crew/route");
const pass = await import("@/app/api/crew/pass/route");
const undo = await import("@/app/api/crew/pass/undo/route");
const reset = await import("@/app/api/crew/pass/reset/route");

const ME = "0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10";

beforeEach(() => {
  calls.length = 0;
  signedInAs = { id: ME };
});

describe("crew worker paths (L-CREW/5)", () => {
  it("keeps repeated filters in order, drops empty and unknown keys, and never takes user_id from the caller", () => {
    const params = new URLSearchParams(
      "location=Hyderabad&location=Pune&location=&colour=red&user_id=someone-else&limit=3&team_size=four_plus",
    );
    const path = workerPath(
      "/internal/crew",
      ME,
      params,
      ["location", "category", "status", "team_size", "looking_for"],
      ["limit"],
    );
    const qs = new URL(path, "http://worker").searchParams;
    expect(qs.getAll("user_id")).toEqual([ME]);
    expect(qs.getAll("location")).toEqual(["Hyderabad", "Pune"]);
    expect(qs.get("team_size")).toBe("four_plus");
    expect(qs.get("limit")).toBe("3");
    expect(qs.has("colour")).toBe(false);
  });

  it("passes only the idea's reference", () => {
    expect(passBody({ idea_id: "IDEA-2026-001481", user_id: "x", note: "y" })).toBe(
      JSON.stringify({ idea_id: "IDEA-2026-001481" }),
    );
    expect(passBody({ idea_id: 42 })).toBe("{}");
  });
});

describe("crew route handlers (A-API.team-up)", () => {
  it("GET /api/crew forwards the filters for the signed-in person", async () => {
    const res = await deck.GET(new NextRequest("http://app/api/crew?location=Mumbai&category=Operations"));
    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
    expect(calls[0].path).toBe(`/internal/crew?user_id=${ME}&location=Mumbai&category=Operations`);
  });

  it("POST /api/crew/pass, /undo and /reset reach the worker as POSTs", async () => {
    const body = JSON.stringify({ idea_id: "IDEA-2026-001481" });
    await pass.POST(new NextRequest("http://app/api/crew/pass", { method: "POST", body }));
    await undo.POST(new NextRequest("http://app/api/crew/pass/undo", { method: "POST" }));
    await reset.POST(new NextRequest("http://app/api/crew/pass/reset", { method: "POST" }));
    expect(calls.map((c) => [c.path, c.init.method, c.init.body])).toEqual([
      [`/internal/crew/pass?user_id=${ME}`, "POST", body],
      [`/internal/crew/pass/undo?user_id=${ME}`, "POST", "{}"],
      [`/internal/crew/pass/reset?user_id=${ME}`, "POST", "{}"],
    ]);
  });

  it("answers for itself when nobody is signed in, and never calls the worker", async () => {
    signedInAs = NextResponse.json({ error: "sign_in_required" }, { status: 401 });
    const res = await deck.GET(new NextRequest("http://app/api/crew"));
    expect(res.status).toBe(401);
    expect(calls).toEqual([]);
  });
});
