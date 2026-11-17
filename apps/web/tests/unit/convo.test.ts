import { beforeEach, describe, expect, it, vi } from "vitest";

const calls: { path: string; init?: RequestInit }[] = [];
let signedIn: { id: string } | Response = { id: "0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10" };
let reply: { status: number; body: unknown } = { status: 200, body: { ok: true } };

vi.mock("@/server/auth/authorize", () => ({ signedIn: async () => signedIn }));
vi.mock("@/server/worker", () => ({
  workerFetch: async (path: string, init?: RequestInit) => {
    calls.push({ path, init });
    return new Response(JSON.stringify(reply.body), { status: reply.status });
  },
}));

const { NextResponse, NextRequest } = await import("next/server");
const convo = await import("@/server/convo");

const ctx = (id: string, entryId?: string) => ({ params: Promise.resolve({ id, entryId }) });
const req = (method: string, body?: unknown, headers: Record<string, string> = {}) =>
  new NextRequest("http://localhost/api/ideas/IDEA-2026-001481/conversation", {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

beforeEach(() => {
  calls.length = 0;
  signedIn = { id: "0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10" };
  reply = { status: 200, body: { ok: true } };
});

describe("L-CONVO web handlers (A-API.inbox conversation)", () => {
  it("GET forwards the signed-in person as user_id and passes the worker's answer through", async () => {
    reply = { status: 404, body: { error: { code: "not_found", message: "" } } };
    const res = await convo.getConversation(req("GET"), ctx("IDEA-2026-001481"));
    expect(calls[0].path).toBe(
      "/internal/ideas/IDEA-2026-001481/conversation?user_id=0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10",
    );
    expect(res.status).toBe(404);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
    expect(await res.json()).toEqual({ error: { code: "not_found", message: "" } });
  });

  it("refuses without a session and never calls the worker", async () => {
    signedIn = NextResponse.json({ error: "sign_in_required" }, { status: 401 });
    const res = await convo.postMessage(req("POST", { text: "Hello" }), ctx("IDEA-2026-001481"));
    expect(res.status).toBe(401);
    expect(calls).toHaveLength(0);
  });

  it("POST sends only the fields the worker reads, and the Idempotency-Key", async () => {
    reply = { status: 422, body: { error: { code: "empty_message", message: "Write a message or attach a file first.", field: "text" } } };
    const res = await convo.postMessage(
      req("POST", { text: "", file_ids: ["ATT-2026-000001", 7], mentions: ["u-2"], as_user: "someone-else" }, {
        "Idempotency-Key": "key-say-hello-0001",
      }),
      ctx("IDEA-2026-001481"),
    );
    const sent = calls[0];
    expect(sent.path).toBe(
      "/internal/ideas/IDEA-2026-001481/conversation/messages?user_id=0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10",
    );
    expect(sent.init?.method).toBe("POST");
    expect(JSON.parse(String(sent.init?.body))).toEqual({
      text: "",
      file_ids: ["ATT-2026-000001"],
      mentions: ["u-2"],
    });
    expect(new Headers(sent.init?.headers).get("Idempotency-Key")).toBe("key-say-hello-0001");
    expect(res.status).toBe(422);
    expect((await res.json()).error.message).toBe("Write a message or attach a file first.");
  });

  it("DELETE removes by entry id, escaped", async () => {
    await convo.deleteMessage(req("DELETE"), ctx("IDEA-2026-001481", "a/b"));
    expect(calls[0].path).toBe(
      "/internal/ideas/IDEA-2026-001481/conversation/messages/a%2Fb?user_id=0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10",
    );
    expect(calls[0].init?.method).toBe("DELETE");
  });

  it("messageBody drops anything that is not the contract's", () => {
    expect(convo.messageBody(null)).toEqual({ text: "" });
    expect(convo.messageBody({ text: 5, mentions: "u-1" })).toEqual({ text: "" });
  });
});
