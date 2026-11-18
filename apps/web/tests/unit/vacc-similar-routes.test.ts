/**
 * V-ACC.similar/8 on the web side (L-MERGE.request/2): "A sharer tries to merge without the lead's acceptance by any
 * route (including the API). It is refused." The web's route handlers for the lead's answer, a draft's merge request
 * and the lead's Inbox item each ask the worker as the signed-in person only: a `user_id`, `as`, `answer` or `state`
 * the caller adds never reaches the worker, and the worker's refusal comes back with its status and code. The worker
 * side of the same row is `services/worker/tests/test_1pc_f_vacc_db.py` (over HTTP). Synthetic people only.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const KAVYA = "0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10";
const RAVI = "7a1f3c22-9e4b-4d10-b6a5-3f8e2c1d0b99";
const REQ = "5c2e1a70-6a4b-4f0e-9d1c-7e3b2a1f0c99";
const DRAFT = "2f0d6c1e-4b3a-4e2f-9a8b-7c6d5e4f3a21";
const NOTE = "I take these calls at our Hyderabad branch every day, about 40 a day.";
const NOT_LEAD = { error: { code: "not_lead", message: "Only the lead of this idea can answer." } };

const calls: { path: string; init?: RequestInit }[] = [];
let reply: { status: number; body: unknown } = { status: 200, body: {} };

vi.mock("@/server/auth/authorize", () => ({ signedIn: async () => ({ id: KAVYA }) }));
vi.mock("@/server/worker", () => ({
  workerFetch: async (path: string, init?: RequestInit) => {
    calls.push({ path, init });
    return new Response(JSON.stringify(reply.body), { status: reply.status });
  },
}));

const { NextRequest } = await import("next/server");
const answer = await import("@/app/api/team-up/[id]/answer/route");
const mergeRequest = await import("@/app/api/drafts/[id]/merge-request/route");
const inboxAction = await import("@/app/api/inbox/[id]/actions/[op]/route");

const ctx = <T extends Record<string, string>>(params: T) => ({ params: Promise.resolve(params) });
const post = (body: unknown, url = "http://localhost/api/x") =>
  new NextRequest(url, { method: "POST", body: JSON.stringify(body) });
const sent = (i = 0) => JSON.parse(String(calls[i]?.init?.body)) as unknown;

beforeEach(() => {
  calls.length = 0;
  reply = { status: 200, body: {} };
});

describe("V-ACC.similar/8 through the web's routes", () => {
  it("V-ACC.similar/8: the lead's answer route asks as the signed-in sharer, drops anything that claims to be the lead, and passes the worker's not_lead back", async () => {
    reply = { status: 403, body: NOT_LEAD };
    const res = await answer.POST(
      post(
        { answer: "merge", reason: "", user_id: RAVI, as: "lead", state: "approved_merged" },
        `http://localhost/api/team-up/${REQ}/answer?user_id=${RAVI}`,
      ),
      ctx({ id: REQ }),
    );
    expect(calls).toHaveLength(1);
    expect(calls[0]!.path).toBe(`/internal/team-up/${REQ}/answer?user_id=${KAVYA}`);
    expect(sent()).toEqual({ answer: "merge", reason: "" });
    expect(res.status).toBe(403);
    expect(await res.json()).toEqual(NOT_LEAD);
  });

  it("V-ACC.similar/8: a draft's merge request carries only the idea and the note, so it can never say it was accepted", async () => {
    reply = { status: 201, body: { id: REQ, state: "waiting" } };
    const res = await mergeRequest.POST(
      post({
        other_idea_id: "IDEA-2026-001412",
        note: NOTE,
        answer: "merge",
        state: "accepted",
        merged: true,
        user_id: RAVI,
      }),
      ctx({ id: DRAFT }),
    );
    expect(calls[0]!.path).toBe(`/internal/drafts/${DRAFT}/merge-request?user_id=${KAVYA}`);
    expect(sent()).toEqual({ other_idea_id: "IDEA-2026-001412", note: NOTE });
    expect(res.status).toBe(201);
    expect((await res.json()).state).toBe("waiting");

    reply = {
      status: 409,
      body: { error: { code: "already_requested", message: "Waiting on Ravi to merge" } },
    };
    const again = await mergeRequest.POST(
      post({ other_idea_id: "IDEA-2026-001412", note: NOTE }),
      ctx({ id: DRAFT }),
    );
    expect(again.status).toBe(409);
    expect((await again.json()).error.code).toBe("already_requested");
  });

  it("V-ACC.similar/8: Merge it on the lead's Inbox item goes to the sharer's own Inbox only, and the worker's not_found comes back", async () => {
    reply = { status: 404, body: { error: "not_found" } };
    const res = await inboxAction.POST(
      new NextRequest(`http://localhost/api/inbox/41/actions/merge?user_id=${RAVI}`, { method: "POST" }),
      ctx({ id: "41", op: "merge" }),
    );
    expect(calls[0]!.path).toBe(`/internal/inbox/${KAVYA}/41/actions/merge`);
    expect(calls[0]!.init?.body).toBeUndefined();
    expect(res.status).toBe(404);
    expect((await res.json()).error.code).toBe("not_found");
  });
});
