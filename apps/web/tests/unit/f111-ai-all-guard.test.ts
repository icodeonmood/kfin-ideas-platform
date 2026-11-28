/**
 * DEC-143 (h), BLD-F111: the Admin page switches `ai.all` on only where the worker has a real model route. The web
 * container never gets the route's credentials (BLD-A246), so the route handler asks the worker
 * (`/internal/model-route`). No route: 409 `no_model_route`. The worker unreachable: 503 `route_unchecked`. Either way
 * nothing is written. Switching `ai.all` off, and every other switch, never asks. The worker side is
 * test_1pc_f_ai_all_guard.py.
 */
import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  me: null as null | Record<string, unknown>,
  asked: [] as string[],
  route: { ready: true } as unknown,
  workerDown: false,
  set: [] as { name: string; state: string }[],
}));

vi.mock("@/server/auth/current", () => ({ currentUser: async () => state.me }));
vi.mock("@/server/worker", () => ({
  WorkerError: class extends Error {},
  workerJson: async (path: string) => {
    state.asked.push(path);
    if (state.workerDown) throw new Error("worker answered 502");
    return state.route;
  },
}));
vi.mock("@/server/killswitch", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/server/killswitch")>()),
  setKillSwitch: async (input: { name: string; state: string }) => {
    state.set.push({ name: input.name, state: input.state });
  },
}));

const { PUT } = await import("@/app/api/admin/kill-switches/route");
const { KILL_SWITCH_COPY, refusedLine } = await import("@/app/admin/kill-switches");

function person(roles: string[]) {
  return {
    id: "0b6c1f0e-1d2a-4c3b-9e8f-7a6b5c4d3e21",
    name: "Ishaan Varma",
    email: "ishaan.varma@kfintech.example",
    lobId: null,
    roleFamily: null,
    contributorCode: "CTR-0a1b2c",
    grants: [],
    roles: new Set(roles),
    nav: [],
    privacyAccepted: true,
  };
}

const put = (name: string, to: "on" | "off") =>
  PUT(
    new NextRequest(new URL("/api/admin/kill-switches", "http://localhost:3000"), {
      method: "PUT",
      body: JSON.stringify({ name, state: to, reason: "The product lead's go for full mode" }),
      headers: { "Content-Type": "application/json" },
    }),
  );

beforeEach(() => {
  state.me = person(["admin"]);
  state.asked = [];
  state.route = { ready: true };
  state.workerDown = false;
  state.set = [];
});

describe("DEC-143 (h), BLD-F111: ai.all goes on only where the worker has a model route", () => {
  it("BLD-F111: with no model route, switching ai.all on is refused (409 no_model_route) and nothing is written", async () => {
    state.route = { ready: false };
    const res = await put("ai.all", "on");
    expect(res.status).toBe(409);
    expect(await res.json()).toEqual({ error: "no_model_route" });
    expect(state.asked).toEqual(["/internal/model-route"]);
    expect(state.set).toEqual([]);
  });

  it("BLD-F111: when the worker cannot be asked, ai.all stays off (503 route_unchecked) and nothing is written", async () => {
    state.workerDown = true;
    const res = await put("ai.all", "on");
    expect(res.status).toBe(503);
    expect(await res.json()).toEqual({ error: "route_unchecked" });
    expect(state.set).toEqual([]);
  });

  it("BLD-F111: an answer that is not a plain yes counts as no route", async () => {
    for (const answer of [{}, { ready: "true" }, { ready: 1 }, null]) {
      state.route = answer;
      state.set = [];
      const res = await put("ai.all", "on");
      expect(res.status).toBe(answer === null ? 503 : 409);
      expect(state.set).toEqual([]);
    }
  });

  it("BLD-F111: with the route set, ai.all goes on as before", async () => {
    const res = await put("ai.all", "on");
    expect(res.status).toBe(200);
    expect(state.asked).toEqual(["/internal/model-route"]);
    expect(state.set).toEqual([{ name: "ai.all", state: "on" }]);
  });

  it("BLD-F111: switching ai.all off, and any other switch either way, never asks the worker", async () => {
    state.route = { ready: false };
    state.me = person(["admin", "infosec"]);
    for (const [name, to] of [
      ["ai.all", "off"],
      ["agent.gatekeeper", "on"],
      ["comms.email", "on"],
      ["comms.email", "off"],
    ] as const) {
      expect((await put(name, to)).status).toBe(200);
    }
    expect(state.asked).toEqual([]);
    expect(state.set.map((s) => `${s.name} ${s.state}`)).toEqual([
      "ai.all off",
      "agent.gatekeeper on",
      "comms.email on",
      "comms.email off",
    ]);
  });

  it("BLD-F111: someone who may not flip ai.all is refused before the worker is asked", async () => {
    state.me = person(["reviewer"]);
    const res = await put("ai.all", "on");
    expect(res.status).toBe(403);
    expect(state.asked).toEqual([]);
  });

  it("BLD-F111: the Admin page says why, in plain words, for each refusal", () => {
    expect(refusedLine("no_model_route")).toBe(KILL_SWITCH_COPY.noModelRoute);
    expect(KILL_SWITCH_COPY.noModelRoute).toBe(
      "ai.all can't be switched on: this server has no model route yet. Set the route first (docs/UAT.md, Switching to full mode), then try again.",
    );
    expect(refusedLine("route_unchecked")).toBe(KILL_SWITCH_COPY.routeUnchecked);
    expect(KILL_SWITCH_COPY.routeUnchecked).toBe(
      "We couldn't check this server's model route, so ai.all stays off. Please try again in a few minutes.",
    );
    for (const other of ["forbidden", "switch_not_changed", undefined, 42]) {
      expect(refusedLine(other)).toBe("That didn't work. You may not have permission to change this switch.");
    }
  });
});
