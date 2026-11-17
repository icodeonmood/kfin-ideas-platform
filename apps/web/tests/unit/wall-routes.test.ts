/**
 * The Wall's, the Ones' and Profile's route handlers (lane E; A-API.wall, A-API.ones, A-API.ones-posts, A-API.me).
 * The worker is replaced by a recorder, so these tests check what each handler lets through, what it forwards
 * (always the signed-in person's own id, never one from the request) and what it answers on failure.
 */
import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  me: null as null | Record<string, unknown>,
  calls: [] as { path: string; method: string; body: unknown }[],
  reply: (() => Response.json({ ok: true })) as (path: string) => Response | Promise<Response>,
}));

vi.mock("@/server/auth/current", () => ({ currentUser: async () => state.me }));
vi.mock("@/server/worker", () => ({
  workerFetch: async (path: string, init: RequestInit = {}) => {
    state.calls.push({
      path,
      method: init.method ?? "GET",
      body: typeof init.body === "string" ? JSON.parse(init.body) : undefined,
    });
    return state.reply(path);
  },
}));

const { GET: kindlingGET } = await import("@/app/api/wall/kindling/route");
const { GET: justInGET } = await import("@/app/api/wall/just-in/route");
const { GET: wallOnesGET } = await import("@/app/api/wall/ones/route");
const { GET: impactGET } = await import("@/app/api/wall/impact/route");
const { GET: emberGET } = await import("@/app/api/wall/ember/route");
const { GET: postsGET } = await import("@/app/api/ones/posts/route");
const { PUT: likePUT } = await import("@/app/api/ones/posts/[id]/like/route");
const { GET: oneGET } = await import("@/app/api/one/route");
const { PUT: numberPUT } = await import("@/app/api/one/number/route");
const { POST: briefPOST } = await import("@/app/api/one/brief/route");
const { POST: seenPOST } = await import("@/app/api/one/glow-up/[id]/seen/route");
const { GET: profileGET } = await import("@/app/api/me/profile/route");
const { PATCH: settingsPATCH } = await import("@/app/api/me/settings/route");

const TANVI = "0b6c1f0e-1d2a-4c3b-9e8f-7a6b5c4d3e21";
const OTHER = "9f8e7d6c-5b4a-4321-8fed-cba987654321";

function person(roles: string[] = ["contributor"], privacyAccepted = true) {
  return {
    id: TANVI,
    name: "Tanvi Joshi",
    email: "tanvi.joshi@kfintech.example",
    lobId: null,
    roleFamily: null,
    contributorCode: "CTR-0a1b2c",
    grants: [],
    roles: new Set(roles),
    nav: [],
    privacyAccepted,
  };
}

const req = (url: string, init: { method?: string; body?: unknown } = {}) =>
  new NextRequest(new URL(url, "http://localhost:3000"), {
    method: init.method ?? "GET",
    ...(init.body !== undefined
      ? { body: JSON.stringify(init.body), headers: { "Content-Type": "application/json" } }
      : {}),
  });
const params = (id: string) => ({ params: Promise.resolve({ id }) });

beforeEach(() => {
  state.me = person();
  state.calls = [];
  state.reply = () => Response.json({ ok: true });
});

describe("A-API.wall: anyone signed in reads the Wall", () => {
  it("serves every Wall read to a plain colleague and forwards only the Wall's own query values", async () => {
    const res = await justInGET(
      req("/api/wall/just-in?kind=problem&sort=popular&limit=5&offset=10&user_id=x"),
    );
    expect(res.status).toBe(200);
    expect(state.calls[0]!.path).toBe("/internal/wall/just-in?kind=problem&sort=popular&limit=5&offset=10");
    for (const [handler, path] of [
      [() => kindlingGET(req("/api/wall/kindling?kind=fix")), "/internal/wall/kindling?kind=fix"],
      [() => wallOnesGET(req("/api/wall/ones?order=leaderboard")), "/internal/wall/ones?order=leaderboard"],
      [() => impactGET(), "/internal/wall/impact"],
      [() => emberGET(), "/internal/wall/ember"],
    ] as const) {
      state.calls = [];
      expect((await handler()).status).toBe(200);
      expect(state.calls.map((c) => c.path)).toEqual([path]);
    }
  });

  it("asks nobody's name: the Wall's reads carry no person to the worker", async () => {
    await kindlingGET(req("/api/wall/kindling"));
    await justInGET(req("/api/wall/just-in"));
    expect(state.calls.map((c) => c.path)).toEqual(["/internal/wall/kindling", "/internal/wall/just-in"]);
  });

  it("refuses someone not signed in, or not past the privacy notice, before the worker hears of it", async () => {
    state.me = null;
    expect((await justInGET(req("/api/wall/just-in"))).status).toBe(401);
    state.me = person(["contributor"], false);
    expect((await impactGET()).status).toBe(403);
    expect(state.calls).toEqual([]);
  });

  it("answers an unknown sort, kind or page in the pack's error shape (A-API.conventions/2)", async () => {
    for (const [query, code, field] of [
      ["sort=loudest", "bad_sort", "sort"],
      ["kind=rumour", "bad_kind", "kind"],
      ["limit=five", "bad_page", "limit"],
      ["offset=-1", "bad_page", "offset"],
    ] as const) {
      const res = await justInGET(req(`/api/wall/just-in?${query}`));
      expect(res.status).toBe(400);
      expect(await res.json()).toEqual({ error: { code, message: "", field } });
    }
    expect(state.calls).toEqual([]);
  });

  it("passes a paused Wall through with its plain-words notice (§7.6)", async () => {
    state.reply = () =>
      Response.json({ error: { code: "paused", message: "", switch: "wall.public" } }, { status: 503 });
    const res = await kindlingGET(req("/api/wall/kindling"));
    const body = (await res.json()) as { error: { code: string; message: string } };
    expect(res.status).toBe(503);
    expect(body.error.code).toBe("paused");
    expect(body.error.message.length).toBeGreaterThan(0);
  });

  it("turns a worker that cannot answer into a clean 503 the screen can show", async () => {
    state.reply = () => {
      throw new Error("connection refused");
    };
    const res = await impactGET();
    expect(res.status).toBe(503);
    expect(await res.json()).toEqual({ error: { code: "try_again", message: "" } });
  });
});

describe("A-API.ones-posts: anyone signed in reads and likes the Ones' posts", () => {
  it("reads as the signed-in person, so 'liked' is theirs", async () => {
    expect((await postsGET()).status).toBe(200);
    expect(state.calls[0]!.path).toBe(`/internal/ones/posts?user_id=${TANVI}`);
  });

  it("likes as the signed-in person and forwards only `liked`", async () => {
    await likePUT(
      req("/api/ones/posts/p1/like", { method: "PUT", body: { liked: true, user_id: OTHER } }),
      params("p1"),
    );
    expect(state.calls).toEqual([
      { path: `/internal/ones/posts/p1/like?user_id=${TANVI}`, method: "PUT", body: { liked: true } },
    ]);
  });
});

describe("A-API.ones: only the One uses /one", () => {
  it("every /one call names the signed-in person; a body can never act for someone else", async () => {
    await oneGET();
    await numberPUT(req("/api/one/number", { method: "PUT", body: { number: 17, user_id: OTHER } }));
    await briefPOST(
      req("/api/one/brief", {
        method: "POST",
        body: { text: "Bounced first debits are down by a third.", user_id: OTHER },
      }),
    );
    await seenPOST(req("/api/one/glow-up/4/seen", { method: "POST" }), params("4"));
    expect(state.calls).toEqual([
      { path: `/internal/one?user_id=${TANVI}`, method: "GET", body: undefined },
      { path: `/internal/one/number?user_id=${TANVI}`, method: "PUT", body: { number: 17 } },
      {
        path: `/internal/one/brief?user_id=${TANVI}`,
        method: "POST",
        body: { text: "Bounced first debits are down by a third." },
      },
      { path: `/internal/one/glow-up/4/seen?user_id=${TANVI}`, method: "POST", body: {} },
    ]);
    expect(JSON.stringify(state.calls)).not.toContain(OTHER);
  });

  it("someone who is not a One is refused with 403 `not_a_one` (S-ONE.rules/1: the page sends them to Profile)", async () => {
    state.reply = () => Response.json({ error: { code: "not_a_one", message: "" } }, { status: 403 });
    for (const call of [
      () => oneGET(),
      () => numberPUT(req("/api/one/number", { method: "PUT", body: { number: 17 } })),
      () => briefPOST(req("/api/one/brief", { method: "POST", body: { text: "x" } })),
      () => seenPOST(req("/api/one/glow-up/4/seen", { method: "POST" }), params("4")),
    ]) {
      const res = await call();
      expect(res.status).toBe(403);
      expect(await res.json()).toEqual({ error: { code: "not_a_one", message: "" } });
    }
  });

  it("a taken number comes back as the worker wrote it: the message and the free numbers near it", async () => {
    const taken = {
      error: {
        code: "taken",
        message: "No. 7 is taken. Free numbers near it: 6, 8, 11.",
        field: "number",
        near: [6, 8, 11],
      },
    };
    state.reply = () => Response.json(taken, { status: 409 });
    const res = await numberPUT(req("/api/one/number", { method: "PUT", body: { number: 7 } }));
    expect(res.status).toBe(409);
    expect(await res.json()).toEqual(taken);
  });

  it("refuses someone not signed in before the worker hears of it", async () => {
    state.me = null;
    expect((await numberPUT(req("/api/one/number", { method: "PUT", body: { number: 7 } }))).status).toBe(
      401,
    );
    expect(state.calls).toEqual([]);
  });
});

describe("A-API.me: only the person reads their own profile and points", () => {
  it("the profile is always the signed-in person's own; the route takes no id", async () => {
    state.reply = () => Response.json({ person: { id: TANVI, points: 340 } });
    const res = await profileGET();
    expect(res.status).toBe(200);
    expect(state.calls).toEqual([
      { path: `/internal/me/profile?user_id=${TANVI}`, method: "GET", body: undefined },
    ]);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
  });

  it("refuses someone not signed in: no points without a session", async () => {
    state.me = null;
    expect((await profileGET()).status).toBe(401);
    expect(state.calls).toEqual([]);
  });

  it("a switch saves at once for the signed-in person and returns every switch's state (S-H6.rules/1)", async () => {
    const settings = {
      show_name_on_wall: false,
      teams: false,
      email: true,
      reminders: true,
      shortcut_p: true,
      sidebar_folded: false,
    };
    state.reply = () => Response.json({ settings });
    const res = await settingsPATCH(
      req("/api/me/settings", { method: "PATCH", body: { show_name_on_wall: false } }),
    );
    expect(await res.json()).toEqual({ settings });
    expect(state.calls).toEqual([
      { path: `/internal/me/settings?user_id=${TANVI}`, method: "PATCH", body: { show_name_on_wall: false } },
    ]);
  });

  it("a save that fails names the switch with the pack's message, so the switch flips back (V-FIELDS.one/5)", async () => {
    state.reply = () => {
      throw new Error("timeout");
    };
    const res = await settingsPATCH(req("/api/me/settings", { method: "PATCH", body: { email: false } }));
    expect(res.status).toBe(503);
    expect(await res.json()).toEqual({
      error: { code: "try_again", message: "Couldn't save that. Try again.", field: "email" },
    });
  });

  it("Teams stays switched off (DEC-105): the worker's refusal reaches the screen as it is", async () => {
    const off = { error: { code: "teams_off", message: "Couldn't save that. Try again.", field: "teams" } };
    state.reply = () => Response.json(off, { status: 409 });
    const res = await settingsPATCH(req("/api/me/settings", { method: "PATCH", body: { teams: true } }));
    expect(res.status).toBe(409);
    expect(await res.json()).toEqual(off);
  });

  it("a body that is not an object saves nothing in its name", async () => {
    await settingsPATCH(req("/api/me/settings", { method: "PATCH", body: ["show_name_on_wall"] }));
    expect(state.calls[0]!.body).toEqual({});
  });
});
