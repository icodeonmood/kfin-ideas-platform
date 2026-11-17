/**
 * The admin page's route handlers (lane A; J-ONE steps 1, 2, 3 and 6; L-DECIDE.after, L-IMPACT, L-AUDIT; BLD-A210).
 * The worker is replaced by a recorder, so these tests check who each handler lets through, what it forwards
 * (always the signed-in person's own id, never one from the request, and only the fields the worker reads), and
 * that a malformed reference never reaches the worker. The worker checks the grants again and audits (pytest).
 */
import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  me: null as null | Record<string, unknown>,
  calls: [] as { path: string; method: string; body: unknown }[],
}));

vi.mock("@/server/auth/current", () => ({ currentUser: async () => state.me }));
vi.mock("@/server/worker", () => ({
  workerFetch: async (path: string, init: RequestInit = {}) => {
    state.calls.push({
      path,
      method: init.method ?? "GET",
      body: typeof init.body === "string" ? JSON.parse(init.body) : undefined,
    });
    return Response.json({ ok: true });
  },
}));

const { GET: programmeGET } = await import("@/app/api/admin/programme/route");
const { POST: teamPOST } = await import("@/app/api/admin/ideas/[id]/build-team/route");
const { POST: shippedPOST } = await import("@/app/api/admin/ideas/[id]/shipped/route");
const { PUT: measurePUT } = await import("@/app/api/admin/ideas/[id]/measurements/[mark]/route");
const { POST: financePOST } = await import("@/app/api/admin/ideas/[id]/measurements/[mark]/finance/route");
const wallRoute = await import("@/app/api/admin/ideas/[id]/wall-removal/route");
const { POST: foundingPOST } = await import("@/app/api/admin/ones/founding/route");
const { DELETE: oneDELETE } = await import("@/app/api/admin/ones/[id]/route");
const { bucket, FlagError, setFlag } = await import("@/server/flags");
const { PUT: flagPUT } = await import("@/app/api/admin/flags/[key]/route");

const ME = "0b6c1f0e-1d2a-4c3b-9e8f-7a6b5c4d3e21";
const REF = "IDEA-2026-000123";

function person(roles: string[]) {
  return {
    id: ME,
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

const req = (url: string, init: { method?: string; body?: unknown } = {}) =>
  new NextRequest(new URL(url, "http://localhost:3000"), {
    method: init.method ?? "GET",
    ...(init.body !== undefined
      ? { body: JSON.stringify(init.body), headers: { "Content-Type": "application/json" } }
      : {}),
  });
const idParams = (id: string) => ({ params: Promise.resolve({ id }) });
const markParams = (id: string, mark: string) => ({ params: Promise.resolve({ id, mark }) });

beforeEach(() => {
  state.me = person(["admin"]);
  state.calls = [];
});

describe("L-AUDIT.permissions: the admin page's routes", () => {
  it("J-ONE/1: an admin's team choice and shipping forward the admin's own id and only the form's fields", async () => {
    const team = await teamPOST(
      req(`/api/admin/ideas/${REF}/build-team`, {
        method: "POST",
        body: {
          name: "Mandates crew",
          lead_email: "kabir@kfintech.example",
          member_emails: "",
          user_id: "x",
        },
      }),
      idParams(REF),
    );
    expect(team.status).toBe(200);
    expect(state.calls[0]).toEqual({
      path: `/internal/admin/ideas/${REF}/build-team`,
      method: "POST",
      body: { name: "Mandates crew", lead_email: "kabir@kfintech.example", member_emails: "", user_id: ME },
    });
    state.calls = [];
    expect((await shippedPOST(req(`/api/admin/ideas/${REF}/shipped`), idParams(REF))).status).toBe(200);
    expect(state.calls[0]).toMatchObject({
      path: `/internal/admin/ideas/${REF}/shipped`,
      body: { user_id: ME },
    });
  });

  it("J-ONE/2: measurements and Finance's confirmation take a 30- or 90-day mark only", async () => {
    const body = { time: { amount: 120 }, money: { amount: 1800000 }, sentence: "120 hours a month saved." };
    const ok = await measurePUT(
      req(`/api/admin/ideas/${REF}/measurements/day_30`, { method: "PUT", body: { ...body, user_id: "x" } }),
      markParams(REF, "day_30"),
    );
    expect(ok.status).toBe(200);
    expect(state.calls[0]!.body).toEqual({ ...body, effort: undefined, scale: undefined, user_id: ME });
    state.calls = [];
    const bad = await measurePUT(
      req(`/api/admin/ideas/${REF}/measurements/day_60`, { method: "PUT", body }),
      markParams(REF, "day_60"),
    );
    expect(bad.status).toBe(404);
    expect(
      (await financePOST(req(`/api/admin/ideas/${REF}/measurements/day_7/finance`), markParams(REF, "day_7")))
        .status,
    ).toBe(404);
    expect(state.calls).toEqual([]);
    expect(
      (
        await financePOST(
          req(`/api/admin/ideas/${REF}/measurements/day_90/finance`),
          markParams(REF, "day_90"),
        )
      ).status,
    ).toBe(200);
    expect(state.calls[0]!.path).toBe(`/internal/admin/ideas/${REF}/measurements/day_90/finance`);
  });

  it("J-ONE/3: Founding Ones and removal go to the worker with no reason field; a bad One id never does", async () => {
    await foundingPOST(
      req("/api/admin/ones/founding", {
        method: "POST",
        body: { email: "rhea@kfintech.example", reason: "x" },
      }),
    );
    expect(state.calls[0]).toEqual({
      path: "/internal/admin/ones/founding",
      method: "POST",
      body: { email: "rhea@kfintech.example", user_id: ME },
    });
    state.calls = [];
    expect((await oneDELETE(req("/api/admin/ones/17", { method: "DELETE" }), idParams("17"))).status).toBe(
      200,
    );
    expect(state.calls[0]).toEqual({
      path: "/internal/admin/ones/17/remove",
      method: "POST",
      body: { user_id: ME },
    });
    state.calls = [];
    expect(
      (await oneDELETE(req("/api/admin/ones/x", { method: "DELETE" }), idParams("0; drop"))).status,
    ).toBe(404);
    expect(state.calls).toEqual([]);
  });

  it("DEC-106: the review desk takes an idea off the Wall and puts it back, but runs nothing else", async () => {
    state.me = person(["reviewer"]);
    const off = await wallRoute.POST(
      req(`/api/admin/ideas/${REF}/wall-removal`, {
        method: "POST",
        body: { reason: "Holds a rude remark" },
      }),
      idParams(REF),
    );
    expect(off.status).toBe(200);
    const back = await wallRoute.DELETE(
      req(`/api/admin/ideas/${REF}/wall-removal`, {
        method: "DELETE",
        body: { reason: "Checked, it is fine" },
      }),
      idParams(REF),
    );
    expect(back.status).toBe(200);
    expect(state.calls.map((c) => [c.path, c.body])).toEqual([
      [`/internal/admin/ideas/${REF}/wall-removal`, { reason: "Holds a rude remark", user_id: ME }],
      [`/internal/admin/ideas/${REF}/wall-restore`, { reason: "Checked, it is fine", user_id: ME }],
    ]);
    expect((await programmeGET()).status).toBe(200); // the desk sees its own part of the page
    state.calls = [];
    expect((await shippedPOST(req(`/api/admin/ideas/${REF}/shipped`), idParams(REF))).status).toBe(403);
    expect(
      (await foundingPOST(req("/api/admin/ones/founding", { method: "POST", body: { email: "a@b.c" } })))
        .status,
    ).toBe(403);
    expect(state.calls).toEqual([]);
  });

  it("a colleague without a role, or someone signed out, reaches none of it", async () => {
    state.me = person(["contributor"]);
    expect((await programmeGET()).status).toBe(403);
    expect(
      (await teamPOST(req(`/api/admin/ideas/${REF}/build-team`, { method: "POST", body: {} }), idParams(REF)))
        .status,
    ).toBe(403);
    expect(
      (
        await wallRoute.POST(
          req(`/api/admin/ideas/${REF}/wall-removal`, { method: "POST", body: {} }),
          idParams(REF),
        )
      ).status,
    ).toBe(403);
    state.me = null;
    expect((await programmeGET()).status).toBe(401);
    expect(state.calls).toEqual([]);
  });

  it("a reference that is not IDEA-YYYY-NNNNNN never reaches the worker", async () => {
    const res = await shippedPOST(req("/api/admin/ideas/IDEA-1/shipped"), idParams("../../ones/1"));
    expect(res.status).toBe(404);
    expect(state.calls).toEqual([]);
  });
});

describe("L-AUDIT.flags: one bucket rule on both sides", () => {
  it("places a person exactly as the worker does (services/worker/tests/test_1pc_admin_programme.py)", () => {
    expect(bucket("s1", "00000000-0000-0000-0000-000000000001")).toBe(62);
    expect(bucket("s2", "00000000-0000-0000-0000-000000000002")).toBe(62);
    expect(bucket("s3", "11111111-2222-3333-4444-555555555555")).toBe(86);
  });
});

describe("L-AUDIT.flags: an empty share is not 0 per cent (BLD-A216)", () => {
  const change = (alternativePercent: unknown) =>
    setFlag({
      key: "s1",
      state: "on",
      alternativePercent,
      reason: "Trying the new check screen",
      actorUserId: ME,
    });

  it("setFlag refuses an empty, blank, missing or non-number share before it reaches the database", async () => {
    for (const bad of ["", "   ", null, undefined, true, [], "12.5", "-1", "101", 101, 2.5]) {
      const err = await change(bad).then(
        () => null,
        (e: unknown) => e,
      );
      expect(err).toBeInstanceOf(FlagError);
      expect(err).toMatchObject({ code: "percent_not_valid", status: 422, field: "alternative_percent" });
    }
  });

  it("the route answers 422 on the share field for an empty share", async () => {
    const res = await flagPUT(
      req("/api/admin/flags/s1", {
        method: "PUT",
        body: { state: "on", alternative_percent: "", reason: "Trying the new check screen" },
      }),
      { params: Promise.resolve({ key: "s1" }) },
    );
    expect(res.status).toBe(422);
    expect(await res.json()).toEqual({
      error: {
        code: "percent_not_valid",
        message: "Enter a whole number from 0 to 100.",
        field: "alternative_percent",
      },
    });
  });
});
