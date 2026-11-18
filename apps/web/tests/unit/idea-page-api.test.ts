/**
 * Lane E's route handlers for the idea pages (A-API.ideas, A-API.my-ideas; S-06, S-09, S-07): who may call them,
 * what reaches the worker, and what may leave the web app. The worker is a stubbed fetch; the session is mocked.
 */
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser } from "@/server/auth/current";

const session = vi.hoisted(() => ({ user: null as CurrentUser | null }));
vi.mock("@/server/auth/current", () => ({ currentUser: async () => session.user }));

const { GET: getIdea } = await import("@/app/api/ideas/[id]/route");
const { GET: getMine, POST: postMine } = await import("@/app/api/me/ideas/route");
const { POST: postWithdraw } = await import("@/app/api/ideas/[id]/withdraw/route");
const { POST: postRestore } = await import("@/app/api/ideas/[id]/restore/route");

const REF = "IDEA-2026-000123";
const ME = "6f1c2a8e-1111-4222-8333-944455556666";

function person(roles: string[] = ["contributor"]): CurrentUser {
  return {
    id: ME,
    name: "Synthetic Person",
    email: "syn.person@example.test",
    lobId: null,
    roleFamily: null,
    contributorCode: "CTR-a1b2c3",
    grants: [],
    roles: new Set(roles),
    nav: [],
    privacyAccepted: true,
  };
}

let calls: { url: URL; init: RequestInit }[] = [];
function worker(status: number, body: unknown) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL, init: RequestInit = {}) => {
      calls.push({ url: new URL(String(input)), init });
      return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
    }),
  );
}

function first(): { url: URL; init: RequestInit } {
  const call = calls[0];
  if (!call) throw new Error("the worker was not called");
  return call;
}

const ctx = (id: string) => ({ params: Promise.resolve({ id }) });
const sharerRef = (id: string) => ({ id, name: "Synthetic Person", first_name: "Synthetic", initials: "SP" });
/** The worker's S-06, naming `sharerId` as its sharer. */
const sharerPage = (sharerId: string, state = "just_shared") => ({
  view: "sharer",
  screen: "S-06",
  idea: {
    id: REF,
    sharer: sharerRef(sharerId),
    own_words: [{ id: "m1", text: "RAW OWN WORDS" }],
    files: [{ id: "f1", name: "call-log.pdf" }],
    has_open_questions: false,
  },
  page: { state, card: { lead: "The review desk will look at it by Friday 20 November.", rest: "" } },
});
const get = (path: string, headers: Record<string, string> = {}) =>
  new NextRequest(`http://localhost${path}`, { headers });
const post = (path: string, body: unknown) =>
  new NextRequest(`http://localhost${path}`, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });

const COLLEAGUE = {
  view: "colleague",
  screen: "S-09",
  idea: {
    id: REF,
    ref: REF,
    status: "with_review_desk",
    title: "Rejection SMS codes confuse investors",
    summary: "The short summary everyone sees.",
    sharer: null,
    stages: [],
    // Nothing below may ever leave for a colleague (S-09.rules/1, DEC-104).
    own_words: [{ id: "m1", text: "RAW WORDS with Folio 1234567890" }],
    hidden: [{ masked: "Folio ••••90" }],
    files: [{ id: "f1", name: "call-log.pdf" }],
    answers_by_part: { often: [{ text: "RAW ANSWER" }] },
    decision: { reason: "RAW REASON" },
    edit_window: { open: true },
    review: { decide_by: "2026-11-20T12:30:00Z" },
  },
  page: {
    back: { from: "wall", label: "Back to the Wall", to: "/wall" },
    pill: { status: "with_review_desk", label: "With the review desk", variant: "blue" },
    team_up: { state: "not_asked", line: "Send a note.", can_team_up: true },
    shared: { rows: [{ value: "RAW WORDS" }] },
    actions: { withdraw: { path: "/api/ideas/x/withdraw" } },
  },
};

beforeEach(() => {
  process.env.INTERNAL_API_TOKEN = "test-token";
  process.env.WORKER_URL = "http://worker.test";
  session.user = person();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("A-API.ideas GET /api/ideas/:id (S-06, S-09)", () => {
  it("P-ROUTES.screens: signed out gets 401 and the worker is never asked", async () => {
    session.user = null;
    worker(200, {});
    const res = await getIdea(get(`/api/ideas/${REF}`), ctx(REF));
    expect(res.status).toBe(401);
    expect(calls).toHaveLength(0);
  });

  it("P-ROUTES.state: asks for the signed-in person only, whatever the query says, with the way back", async () => {
    worker(200, sharerPage(ME));
    const res = await getIdea(
      get(`/api/ideas/${REF}?user_id=someone-else&from=my-ideas&back=%2Fmy-ideas%3Ffilter%3Dclosed`),
      ctx(REF),
    );
    expect(res.status).toBe(200);
    const url = first().url;
    expect(url.pathname).toBe(`/internal/ideas/${REF}/view`);
    expect(url.searchParams.getAll("user_id")).toEqual([ME]);
    expect(url.searchParams.get("came_from")).toBe("my-ideas");
    expect(url.searchParams.get("back")).toBe("/my-ideas?filter=closed");
    expect(new Headers(first().init.headers).get("X-Internal-Token")).toBe("test-token");
    expect(res.headers.get("Cache-Control")).toBe("no-store");
  });

  it("DEC-110: a search in the way back (an older link) is dropped before it reaches the worker", async () => {
    worker(200, sharerPage(ME));
    const back = encodeURIComponent("/my-ideas?sort=shared&q=Zebra7Kestrel&row=IDEA-2026-000123");
    await getIdea(get(`/api/ideas/${REF}?from=my-ideas&back=${back}`), ctx(REF));
    expect(first().url.searchParams.get("back")).toBe("/my-ideas?sort=shared&row=IDEA-2026-000123");
    expect(first().url.href).not.toMatch(/zebra7kestrel/i);
  });

  it("an id that is neither a reference nor a row id is not found, without asking the worker", async () => {
    worker(200, {});
    const res = await getIdea(get("/api/ideas/..%2Finternal"), ctx("../internal"));
    expect(res.status).toBe(404);
    expect(((await res.json()) as { error: { code: string } }).error.code).toBe("not_found");
    expect(calls).toHaveLength(0);
  });

  it("DEC-104, S-09.rules/1: a colleague's view never carries raw words, answers, files or a reason", async () => {
    worker(200, COLLEAGUE);
    const res = await getIdea(get(`/api/ideas/${REF}`), ctx(REF));
    const body = (await res.json()) as typeof COLLEAGUE;
    const dump = JSON.stringify(body);
    expect(body.view).toBe("colleague");
    for (const raw of ["RAW WORDS", "RAW ANSWER", "RAW REASON", "1234567890", "call-log.pdf", "Folio"]) {
      expect(dump).not.toContain(raw);
    }
    for (const key of [
      "own_words",
      "hidden",
      "files",
      "answers_by_part",
      "decision",
      "edit_window",
      "review",
    ]) {
      expect(body.idea).not.toHaveProperty(key);
    }
    expect(body.page).not.toHaveProperty("shared");
    expect(body.page).not.toHaveProperty("actions");
    expect(body.idea.summary).toBe("The short summary everyone sees.");
    expect(body.page.team_up.state).toBe("not_asked");
  });

  it("P-ROUTES.screens: a non-sharer never gets S-06 data; the worker's not found passes as 404", async () => {
    worker(404, { error: { code: "not_found", message: "We can’t find that idea." } });
    const res = await getIdea(get(`/api/ideas/${REF}`), ctx(REF));
    expect(res.status).toBe(404);
    expect(await res.json()).toEqual({ error: { code: "not_found", message: "We can’t find that idea." } });
  });

  it("S-06, non-negotiable 7: a sharer's page that names someone else, or nobody, never leaves the web app", async () => {
    for (const page of [
      sharerPage("0d9e8f7a-6b5c-4d3e-8f1a-2b3c4d5e6f70"),
      { ...sharerPage(ME), idea: { ...sharerPage(ME).idea, sharer: null } },
      { ...sharerPage(ME), idea: { id: REF, own_words: [{ text: "RAW OWN WORDS" }] } },
    ]) {
      worker(200, page);
      const res = await getIdea(get(`/api/ideas/${REF}`), ctx(REF));
      expect(res.status).toBe(404);
      const dump = JSON.stringify(await res.json());
      for (const raw of ["RAW OWN WORDS", "call-log.pdf", "Friday 20 November"])
        expect(dump).not.toContain(raw);
    }
  });

  it("L-DRAFT: a draft opens only for its owner, as a pointer and nothing else", async () => {
    const draft = "0b6d3c1e-2f4a-4b5c-8d9e-0f1a2b3c4d5e";
    worker(200, { view: "draft", to: `/share/${draft}`, idea: { own_words: ["RAW"] } });
    const res = await getIdea(get(`/api/ideas/${draft}`), ctx(draft));
    expect(await res.json()).toEqual({ view: "draft", to: `/share/${draft}` });
    worker(404, { error: { code: "not_found", message: "We can’t find that idea." } });
    expect((await getIdea(get(`/api/ideas/${draft}`), ctx(draft))).status).toBe(404);
  });

  it("BLD-E011, S-09.rules/2: a withdrawn idea leaves with its reference and one line, nothing of the idea", async () => {
    const line = "The person who shared it withdrew it, so nobody else can see it now.";
    worker(200, {
      view: "colleague",
      screen: "S-09",
      idea: { ...COLLEAGUE.idea, status: "withdrawn", crew: { count: 4 }, area: "Investor service" },
      page: {
        ...COLLEAGUE.page,
        state: "withdrawn",
        pill: { status: "withdrawn", label: "Withdrawn", variant: "neutral" },
        shared_line: "Shared Monday 9 November by Synthetic Person",
        about: [{ label: "Area", value: "Investor service" }],
        team_up: { state: "withdrawn", line, can_team_up: false, faces: [{ name: "Synthetic Person" }] },
      },
    });
    const res = await getIdea(get(`/api/ideas/${REF}?from=my-ideas`), ctx(REF));
    expect(res.status).toBe(200);
    const body = (await res.json()) as { idea: object; page: { team_up: object } };
    expect(body.idea).toEqual({ id: REF, ref: REF, status: "withdrawn" });
    expect(Object.keys(body.page).sort()).toEqual(["back", "pill", "state", "team_up"]);
    expect(body.page.team_up).toEqual({ state: "withdrawn", line, can_team_up: false });
    const dump = JSON.stringify(body);
    for (const gone of ["Rejection SMS", "short summary", "Synthetic Person", "Investor service", "RAW"]) {
      expect(dump).not.toContain(gone);
    }
    // Anyone who was not on its crew and did not ask to join gets the worker's "not found", as for a missing idea.
    worker(404, { error: { code: "not_found", message: "We can’t find that idea." } });
    expect((await getIdea(get(`/api/ideas/${REF}`), ctx(REF))).status).toBe(404);
  });

  it("S-09.rules/3: a reviewer is sent to the desk's page (S-R2)", async () => {
    worker(200, { view: "desk", to: `/desk/ideas/${REF}` });
    const res = await getIdea(get(`/api/ideas/${REF}`), ctx(REF));
    expect(await res.json()).toEqual({ view: "desk", to: `/desk/ideas/${REF}` });
  });

  it("S-06: the sharer's page passes through whole to its sharer, and an unknown view is not found", async () => {
    const page = sharerPage(ME);
    worker(200, page);
    expect(await (await getIdea(get(`/api/ideas/${REF}`), ctx(REF))).json()).toEqual(page);
    worker(200, { view: "something-else", idea: { own_words: ["RAW"] } });
    const res = await getIdea(get(`/api/ideas/${REF}`), ctx(REF));
    expect(res.status).toBe(404);
    expect(JSON.stringify(await res.json())).not.toContain("RAW");
  });

  it("an unreachable worker answers 503 in the pack's error shape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );
    const res = await getIdea(get(`/api/ideas/${REF}`), ctx(REF));
    expect(res.status).toBe(503);
    expect(((await res.json()) as { error: { code: string } }).error.code).toBe("unavailable");
  });
});

describe("A-API.my-ideas GET /api/me/ideas (S-07, P-ROUTES.state)", () => {
  it("P-ROUTES.state, J-BROWSE/1 and /3, DEC-110: tab, filter, sort and row go from the URL to the worker; a q never does", async () => {
    const state = { list: "teamed", filter: "closed", sort: "stage", q: "", row: "IDEA-2026-000001" };
    const body = {
      items: [],
      total: 0,
      counts: {},
      lists: {},
      state,
      query: "list=teamed&filter=closed&sort=stage&row=IDEA-2026-000001",
      url: "/my-ideas?list=teamed&filter=closed&sort=stage&row=IDEA-2026-000001",
      arrival: { line: "Back where you were: Teamed up.", row: "IDEA-2026-000001" },
    };
    worker(200, body);
    const res = await getMine(
      get("/api/me/ideas?list=teamed&filter=closed&sort=stage&q=sms&row=IDEA-2026-000001&user_id=x", {
        "x-device-id": "laptop-abcdef12",
      }),
    );
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual(body);
    const url = first().url;
    expect(url.pathname).toBe(`/internal/me/${ME}/my-ideas`);
    expect(Object.fromEntries(url.searchParams)).toEqual({
      user_id: ME,
      device: "laptop-abcdef12",
      list: "teamed",
      filter: "closed",
      sort: "stage",
      row: "IDEA-2026-000001",
    });
    expect(url.href).not.toContain("sms");
  });

  it("DEC-110, BLD-A219: POST carries the search in its body to the worker's POST, never in a URL, cut at 200", async () => {
    const state = { list: "yours", filter: "all", sort: "shared", q: "Zebra7Kestrel", row: null };
    worker(200, { items: [], state });
    const res = await postMine(
      post("/api/me/ideas?user_id=x", {
        list: "yours",
        sort: "shared",
        q: "Zebra7Kestrel",
        filter: 7,
        user_id: "someone-else",
      }),
    );
    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
    const call = first();
    expect(call.init.method).toBe("POST");
    expect(call.url.pathname).toBe(`/internal/me/${ME}/my-ideas`);
    expect(Object.fromEntries(call.url.searchParams)).toEqual({ user_id: ME });
    expect(JSON.parse(String(call.init.body))).toEqual({ list: "yours", sort: "shared", q: "Zebra7Kestrel" });
    expect(call.url.href).not.toMatch(/zebra7kestrel/i);

    calls = [];
    await postMine(post("/api/me/ideas", { q: "a".repeat(250) }));
    expect((JSON.parse(String(first().init.body)) as { q: string }).q).toHaveLength(200);
    session.user = null;
    calls = [];
    expect((await postMine(post("/api/me/ideas", { q: "x" }))).status).toBe(401);
    expect(calls).toHaveLength(0);
  });

  it("drops a device id that is not an opaque token, and refuses the signed out", async () => {
    worker(200, { items: [] });
    await getMine(get("/api/me/ideas", { "x-device-id": "<script>" }));
    expect(first().url.searchParams.has("device")).toBe(false);
    session.user = null;
    expect((await getMine(get("/api/me/ideas"))).status).toBe(401);
  });
});

describe("A-API.ideas withdraw and restore (L-SUBMIT.withdraw)", () => {
  it("withdraw sends the optional reason for the signed-in person and returns the sharer's page", async () => {
    worker(200, sharerPage(ME, "withdrawn"));
    const res = await postWithdraw(
      post(`/api/ideas/${REF}/withdraw`, { reason: "Being fixed", user_id: "x" }),
      ctx(REF),
    );
    expect(res.status).toBe(200);
    expect(first().init.method).toBe("POST");
    expect(first().url.pathname).toBe(`/internal/ideas/${REF}/withdraw`);
    expect(first().url.searchParams.getAll("user_id")).toEqual([ME]);
    expect(JSON.parse(String(first().init.body))).toEqual({ reason: "Being fixed" });
    expect(((await res.json()) as { page: { state: string } }).page.state).toBe("withdrawn");
  });

  it("S-06: withdraw and restore answer only with the signed-in sharer's own page", async () => {
    for (const handler of [postWithdraw, postRestore]) {
      worker(200, sharerPage("0d9e8f7a-6b5c-4d3e-8f1a-2b3c4d5e6f70", "withdrawn"));
      const res = await handler(post(`/api/ideas/${REF}/withdraw`, {}), ctx(REF));
      expect(res.status).toBe(404);
      expect(JSON.stringify(await res.json())).not.toContain("RAW OWN WORDS");
    }
  });

  it("the worker's refusal passes through with its words (edit_window_closed)", async () => {
    const refusal = {
      error: {
        code: "edit_window_closed",
        message: "The review desk has it now, so it can’t be withdrawn. Write to them in the conversation.",
        opened_by_desk_at: "2026-11-16T05:50:00+00:00",
      },
    };
    worker(409, refusal);
    const res = await postWithdraw(post(`/api/ideas/${REF}/withdraw`, {}), ctx(REF));
    expect(res.status).toBe(409);
    expect(await res.json()).toEqual(refusal);
  });

  it("restore sends no body fields; a person without the submit capability is refused before the worker", async () => {
    worker(200, sharerPage(ME));
    expect((await postRestore(post(`/api/ideas/${REF}/restore`, { anything: 1 }), ctx(REF))).status).toBe(
      200,
    );
    expect(first().url.pathname).toBe(`/internal/ideas/${REF}/restore`);
    expect(JSON.parse(String(first().init.body))).toEqual({});
    session.user = person([]);
    calls = [];
    expect((await postRestore(post(`/api/ideas/${REF}/restore`, {}), ctx(REF))).status).toBe(403);
    expect(calls).toHaveLength(0);
  });
});
