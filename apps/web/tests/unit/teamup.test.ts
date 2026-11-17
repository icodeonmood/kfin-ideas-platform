import { beforeEach, describe, expect, it, vi } from "vitest";

const ME = "0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10";
const REQ = "5c2e1a70-6a4b-4f0e-9d1c-7e3b2a1f0c99";
const calls: { path: string; init?: RequestInit }[] = [];
let signedIn: { id: string } | Response = { id: ME };
let reply: { status: number; body: unknown; raw?: string } = { status: 200, body: { ok: true } };

vi.mock("@/server/auth/authorize", () => ({ signedIn: async () => signedIn }));
vi.mock("@/server/worker", () => ({
  workerFetch: async (path: string, init?: RequestInit) => {
    calls.push({ path, init });
    return new Response(reply.raw ?? JSON.stringify(reply.body), { status: reply.status });
  },
}));

const { NextResponse, NextRequest } = await import("next/server");
const teamup = await import("@/server/teamup");
const ideaTeamUp = await import("@/app/api/ideas/[id]/team-up/route");
const draftNote = await import("@/app/api/ideas/[id]/team-up/draft-note/route");
const request = await import("@/app/api/team-up/[id]/route");
const answer = await import("@/app/api/team-up/[id]/answer/route");
const mergeRequest = await import("@/app/api/drafts/[id]/merge-request/route");
const leave = await import("@/app/api/ideas/[id]/crew/leave/route");
const member = await import("@/app/api/ideas/[id]/crew/[member]/route");

const ctx = <T extends Record<string, string>>(params: T) => ({ params: Promise.resolve(params) });
const req = (method: string, body?: unknown, headers: Record<string, string> = {}) =>
  new NextRequest("http://localhost/api/x", {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
const call = (i = 0) => {
  const c = calls[i];
  if (!c) throw new Error(`no worker call ${i}`);
  return c;
};
const sentBody = (i = 0) => JSON.parse(String(call(i).init?.body)) as unknown;

beforeEach(() => {
  calls.length = 0;
  signedIn = { id: ME };
  reply = { status: 200, body: { ok: true } };
});

describe("L-TEAMUP and L-MERGE.request web handlers (A-API.team-up, A-API.drafts merge-request)", () => {
  it("GET /ideas/:id/team-up forwards the signed-in person as user_id, uncached", async () => {
    reply = {
      status: 200,
      body: { idea_id: "IDEA-2026-001412", can_request: false, why_not: "already_requested" },
    };
    const res = await ideaTeamUp.GET(req("GET"), ctx({ id: "IDEA-2026-001412" }));
    expect(call().path).toBe(`/internal/ideas/IDEA-2026-001412/team-up?user_id=${ME}`);
    expect(call().init?.method).toBeUndefined();
    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
    expect((await res.json()).why_not).toBe("already_requested");
  });

  it("refuses without a session and never calls the worker", async () => {
    signedIn = NextResponse.json({ error: "sign_in_required" }, { status: 401 });
    for (const res of [
      await ideaTeamUp.POST(req("POST", { note: "x".repeat(40) }), ctx({ id: "IDEA-2026-001412" })),
      await draftNote.GET(req("GET"), ctx({ id: "IDEA-2026-001412" })),
      await answer.POST(req("POST", { answer: "merge" }), ctx({ id: REQ })),
      await request.DELETE(req("DELETE"), ctx({ id: REQ })),
      await mergeRequest.POST(req("POST", { note: "x".repeat(40) }), ctx({ id: REQ })),
      await leave.POST(req("POST"), ctx({ id: "IDEA-2026-001412" })),
    ])
      expect(res.status).toBe(401);
    expect(calls).toHaveLength(0);
  });

  it("POST /ideas/:id/team-up sends only the contract's fields and the Idempotency-Key", async () => {
    reply = { status: 201, body: { id: REQ, state: "sent" } };
    const res = await ideaTeamUp.POST(
      req(
        "POST",
        {
          note: "I take these calls every day.",
          brought_idea_ids: ["IDEA-2026-001481"],
          draft_id: REQ,
          user_id: "x",
        },
        { "Idempotency-Key": "key-teamup-0001" },
      ),
      ctx({ id: "IDEA-2026-001412" }),
    );
    expect(call().path).toBe(`/internal/ideas/IDEA-2026-001412/team-up?user_id=${ME}`);
    expect(call().init?.method).toBe("POST");
    expect(sentBody()).toEqual({
      note: "I take these calls every day.",
      brought_idea_ids: ["IDEA-2026-001481"],
      draft_id: REQ,
    });
    expect(new Headers(call().init?.headers).get("Idempotency-Key")).toBe("key-teamup-0001");
    expect(res.status).toBe(201);
  });

  it("passes the worker's error shape through as it is, so the message shows under its field", async () => {
    reply = {
      status: 422,
      body: {
        error: {
          code: "note_too_short",
          message: "Add a little more: at least 30 characters.",
          field: "note",
        },
      },
    };
    const short = await ideaTeamUp.POST(req("POST", { note: "short" }), ctx({ id: "IDEA-2026-001412" }));
    expect(short.status).toBe(422);
    expect(await short.json()).toEqual(reply.body);

    reply = {
      status: 403,
      body: { error: { code: "not_lead", message: "Only the lead of this idea can answer." } },
    };
    const notLead = await answer.POST(
      req("POST", { answer: "merge", reason: "", as: "lead" }),
      ctx({ id: REQ }),
    );
    expect(call(1).path).toBe(`/internal/team-up/${REQ}/answer?user_id=${ME}`);
    expect(sentBody(1)).toEqual({ answer: "merge", reason: "" });
    expect(notLead.status).toBe(403);
    expect((await notLead.json()).error.code).toBe("not_lead");
  });

  it("a worker answer that is not JSON becomes one plain error, with the worker's status", async () => {
    reply = { status: 502, body: null, raw: "<html>Bad gateway</html>" };
    const res = await request.GET(req("GET"), ctx({ id: REQ }));
    expect(res.status).toBe(502);
    expect(await res.json()).toEqual({
      error: { code: "worker_error", message: "Something went wrong. Please try again." },
    });
  });

  it("withdraws a request and a draft's merge request with DELETE and no body", async () => {
    await request.DELETE(req("DELETE"), ctx({ id: REQ }));
    await mergeRequest.DELETE(req("DELETE"), ctx({ id: REQ }));
    expect(calls.map((c) => [c.init?.method, c.path, c.init?.body])).toEqual([
      ["DELETE", `/internal/team-up/${REQ}?user_id=${ME}`, undefined],
      ["DELETE", `/internal/drafts/${REQ}/merge-request?user_id=${ME}`, undefined],
    ]);
  });

  it("asks to merge a draft in with the other idea and the note only", async () => {
    reply = { status: 201, body: { state: "waiting" } };
    const res = await mergeRequest.POST(
      req("POST", {
        other_idea_id: "IDEA-2026-001412",
        note: "I take these calls every day.",
        state: "accepted",
      }),
      ctx({ id: REQ }),
    );
    expect(call().path).toBe(`/internal/drafts/${REQ}/merge-request?user_id=${ME}`);
    expect(sentBody()).toEqual({ other_idea_id: "IDEA-2026-001412", note: "I take these calls every day." });
    expect(res.status).toBe(201);
  });

  it("escapes path segments: the lead removes a member by id; a member leaves with an empty body", async () => {
    await member.DELETE(req("DELETE"), ctx({ id: "IDEA-2026-001412", member: "a/b?c" }));
    await leave.POST(req("POST", { anything: 1 }), ctx({ id: "IDEA-2026-001412" }));
    expect(call().path).toBe(`/internal/ideas/IDEA-2026-001412/crew/a%2Fb%3Fc?user_id=${ME}`);
    expect(call(1).path).toBe(`/internal/ideas/IDEA-2026-001412/crew/leave?user_id=${ME}`);
    expect(sentBody(1)).toEqual({});
  });

  it("pick keeps only the named fields that were sent", () => {
    expect(teamup.pick({ a: 1, b: undefined, c: 3 }, ["a", "b"])).toEqual({ a: 1 });
  });
});
