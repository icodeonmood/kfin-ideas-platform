import { beforeEach, describe, expect, it, vi } from "vitest";

// L-HIDE.rules/7 at the web edge (lane C, BLD-C066): S-R2 "Hide this" forwards the masked words the page selected
// (`selected`) for the worker's `stale` check, caps them, and refuses the reviewer's own idea. Synthetic ids and words.
const IDEA = "3f1c2b7a-5d4e-4c3b-9a2f-1e0d9c8b7a65";
const ME = "0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10";
const MY_CODE = "CTR-a1b2c3";
const calls: { path: string; body: Record<string, unknown> }[] = [];
let idea: { id: string; idea_id: string; status: string; contributor_code: string } | undefined;
let reply: { status: number; body: unknown } = { status: 200, body: {} };

vi.mock("@/server/auth/authorize", () => ({
  authorize: async () => ({ id: ME, contributorCode: MY_CODE, roles: new Set(["reviewer"]) }),
}));
vi.mock("@/server/db", () => {
  const chain: Record<string, unknown> = {};
  for (const step of ["selectFrom", "select", "where"]) chain[step] = () => chain;
  chain.executeTakeFirst = async () => idea;
  return { getDb: () => chain };
});
vi.mock("@/server/worker", () => ({
  workerFetch: async (path: string, init?: RequestInit) => {
    calls.push({ path, body: JSON.parse(String(init?.body)) as Record<string, unknown> });
    return new Response(JSON.stringify(reply.body), { status: reply.status });
  },
}));

const { NextRequest } = await import("next/server");
const route = await import("@/app/api/desk/ideas/[id]/hide/route");
const { OWN_IDEA, SELECTED_MAX } = await import("@/server/hide");

const DETAIL = {
  id: "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d",
  kind: "name",
  masked: "Name ••••ao",
  state: "hidden",
};
const post = (body: unknown) =>
  route.POST(
    new NextRequest(`http://localhost/api/desk/ideas/${IDEA}/hide`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
    { params: Promise.resolve({ id: IDEA }) },
  );
const base = { source: { kind: "message", id: "5c2e1a70-6a4b-4f0e-9d1c-7e3b2a1f0c99" }, start: 12, end: 21 };

beforeEach(() => {
  calls.length = 0;
  idea = {
    id: IDEA,
    idea_id: "IDEA-2026-001412",
    status: "with_review_desk",
    contributor_code: "CTR-0f0e0d",
  };
  reply = { status: 200, body: DETAIL };
});

describe("L-HIDE.rules/7 S-R2 Hide this: selected, stale and own idea", () => {
  it("forwards selected with the browser's offsets, and leaves it out when the page sends none", async () => {
    const res = await post({ ...base, selected: "Kiran Rao" });
    expect(res.status).toBe(200);
    expect(calls[0]!.path).toBe(`/internal/hide/desk/${IDEA}`);
    expect(calls[0]!.body).toEqual({ ...base, units: "utf16", selected: "Kiran Rao", by: ME });
    await post(base);
    expect(calls[1]!.body).toEqual({ ...base, units: "utf16", by: ME });
    await post({ ...base, selected: null });
    expect("selected" in calls[2]!.body).toBe(false);
  });

  it("answers the worker's stale with 409 and the A-API shape", async () => {
    reply = { status: 409, body: { error: { code: "stale", message: "" } } };
    const res = await post({ ...base, selected: "Kiran Rao" });
    expect(res.status).toBe(409);
    expect(await res.json()).toEqual({
      error: { code: "stale", message: "The page changed. Select again." },
    });
  });

  it("refuses a selected longer than the cap with 422 selection_too_long, and a selected that is not text", async () => {
    const long = await post({ ...base, selected: "x".repeat(SELECTED_MAX + 1) });
    expect(long.status).toBe(422);
    expect((await long.json()).error.code).toBe("selection_too_long");
    const atCap = await post({ ...base, selected: "x".repeat(SELECTED_MAX) });
    expect(atCap.status).toBe(200);
    const notText = await post({ ...base, selected: 42 });
    expect(notText.status).toBe(400);
    expect((await notText.json()).error.code).toBe("range_invalid");
    expect(calls).toHaveLength(1);
    reply = { status: 422, body: { error: { code: "selection_too_long", message: "" } } };
    expect((await post({ ...base, selected: "Kiran Rao" })).status).toBe(422);
  });

  it("answers the worker's own-idea refusal (own or merged in) with 403 forbidden and lane B's words", async () => {
    idea = { ...idea!, contributor_code: MY_CODE };
    reply = { status: 403, body: { error: { code: "forbidden", message: "" } } };
    for (const body of [{ ...base, selected: "Kiran Rao" }, base]) {
      const res = await post(body);
      expect(res.status).toBe(403);
      expect(await res.json()).toEqual({ error: { code: "forbidden", message: OWN_IDEA } });
    }
    expect(calls).toHaveLength(2); // the worker decides, and audits, every refusal
  });
});
