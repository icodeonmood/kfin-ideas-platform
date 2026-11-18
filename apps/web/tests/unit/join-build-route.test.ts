/**
 * L-DECIDE/6, A-API POST /ideas/:id/join-build (DEC-111, BLD-B256): the web route asks the worker as the signed-in
 * person only, with no body, and passes the worker's answer back as it is: `{ asked_at }`, or a refusal in the
 * pack's error shape. A `user_id` the caller adds never reaches the worker. Synthetic people only.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { JoinBuildResponse } from "@/lib/contracts";
import rbac from "@/lib/rbac.json";

const KAVYA = "0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10";
const NIKHIL = "7a1f3c22-9e4b-4d10-b6a5-3f8e2c1d0b99";
const IDEA = "IDEA-2026-001481";

const calls: { path: string; init?: RequestInit }[] = [];
let reply: { status: number; body: unknown } = { status: 200, body: {} };
let signedIn: unknown = { id: KAVYA };

vi.mock("@/server/auth/authorize", () => ({ signedIn: async () => signedIn, authorize: vi.fn() }));
vi.mock("@/server/worker", () => ({
  workerFetch: async (path: string, init?: RequestInit) => {
    calls.push({ path, init });
    return new Response(JSON.stringify(reply.body), { status: reply.status });
  },
}));

const { NextRequest, NextResponse } = await import("next/server");
const route = await import("@/app/api/ideas/[id]/join-build/route");

const ctx = { params: Promise.resolve({ id: IDEA }) };
const post = (body: unknown = undefined) =>
  new NextRequest(`http://localhost/api/ideas/${IDEA}/join-build?user_id=${NIKHIL}`, {
    method: "POST",
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });

beforeEach(() => {
  calls.length = 0;
  reply = { status: 200, body: {} };
  signedIn = { id: KAVYA };
});

describe("L-DECIDE/6: POST /api/ideas/{id}/join-build", () => {
  it("L-DECIDE/6: asks the worker as the signed-in person, with no body, and returns { asked_at }", async () => {
    const asked: JoinBuildResponse = { asked_at: "2026-11-17T03:30:00+00:00" };
    reply = { status: 200, body: asked };
    const res = await route.POST(post({ user_id: NIKHIL, asked_at: "2026-01-01" }), ctx);
    expect(calls).toHaveLength(1);
    expect(calls[0]!.path).toBe(`/internal/ideas/${IDEA}/join-build?user_id=${KAVYA}`);
    expect(calls[0]!.init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0]!.init?.body))).toEqual({});
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual(asked);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
  });

  it("L-DECIDE/6: passes the worker's refusals back with their status and code", async () => {
    for (const [status, code] of [
      [409, "not_picked"],
      [409, "team_chosen"],
      [403, "forbidden"],
      [404, "not_found"],
    ] as const) {
      reply = { status, body: { error: { code, message: "" } } };
      const res = await route.POST(post(), ctx);
      expect(res.status).toBe(status);
      expect(((await res.json()) as { error: { code: string } }).error.code).toBe(code);
    }
  });

  it("L-DECIDE/6: someone not signed in never reaches the worker", async () => {
    signedIn = NextResponse.json({ error: "sign_in_required" }, { status: 401 });
    const res = await route.POST(post(), ctx);
    expect(res.status).toBe(401);
    expect(calls).toHaveLength(0);
  });

  it("L-DECIDE/6: the route is in the RBAC policy for anyone signed in (DEC-111)", () => {
    const routes = JSON.stringify(rbac);
    expect(routes).toMatch(/POST \/api\/ideas\/\{id\}\/join-build\s+signed_in/);
  });
});
