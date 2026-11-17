/**
 * The review side's proxy to the worker (A-API.conventions/2): the worker's answer is passed through as it is, and a
 * body that is not JSON, or no answer at all, becomes a 502 in the pack's error shape with none of the worker's text.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/server/auth/authorize", () => ({ authorize: vi.fn(), signedIn: vi.fn() }));

import { forward, WORKER_FAILED } from "@/server/desk";

describe("A-API.conventions/2: desk forward", () => {
  const saved = { ...process.env };
  beforeEach(() => {
    process.env.INTERNAL_API_TOKEN = "test-token-for-the-desk-proxy";
    process.env.WORKER_URL = "http://worker.test";
  });
  afterEach(() => {
    process.env = { ...saved };
    vi.unstubAllGlobals();
  });

  it("passes a JSON answer through with its status", async () => {
    const body = { error: { code: "reason_too_short", message: "Give Kavya a reason.", field: "reason" } };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(body), { status: 422 })),
    );
    const res = await forward("/internal/desk/ideas/IDEA-2026-001401/decision?user_id=u", { method: "POST" });
    expect(res.status).toBe(422);
    expect(await res.json()).toEqual(body);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
  });

  it("turns a body that is not JSON into a 502 in the pack's shape, without the worker's text", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("Internal Server Error: Traceback …", { status: 500 })),
    );
    const res = await forward("/internal/desk?user_id=u");
    expect(res.status).toBe(502);
    const json = (await res.json()) as typeof WORKER_FAILED;
    expect(json).toEqual(WORKER_FAILED);
    expect(JSON.stringify(json)).not.toContain("Traceback");
  });

  it("turns an unreachable worker into the same 502", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );
    const res = await forward("/internal/desk?user_id=u");
    expect(res.status).toBe(502);
    expect(await res.json()).toEqual(WORKER_FAILED);
  });

  it("keeps an empty body as null", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("", { status: 200 })),
    );
    const res = await forward("/internal/question-sets/x/remind?user_id=u", { method: "POST" });
    expect(res.status).toBe(200);
    expect(await res.json()).toBeNull();
  });
});
