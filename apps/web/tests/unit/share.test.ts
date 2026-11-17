/**
 * L-SORT and L-SUBMIT, web side (lane C, BLD-C084): the routes pass the signed-in person and the body to the
 * worker, refuse a malformed key before calling it, keep the A-API error shape, and stop with `submissions`.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const calls: { path: string; init: RequestInit }[] = [];
let answer: () => Promise<Response> = async () => Response.json({ ok: true });

vi.mock("@/server/worker", () => ({
  workerFetch: (path: string, init: RequestInit = {}) => {
    calls.push({ path, init });
    return answer();
  },
}));
vi.mock("@/server/promises", () => ({ promises: async () => ({}) }));

const { isKey, patchSorting, readSorting, saveEdit, sendView, submitDraft, versions, SEND_FAILED } =
  await import("@/server/share");
const { switchesFor } = await import("@/lib/killswitch-routes");

const me = { id: "6f1c2b0e-1d2e-4c3b-9a8f-0123456789ab" } as never;
const DRAFT = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d";

beforeEach(() => {
  calls.length = 0;
  answer = async () => Response.json({ ok: true });
});

describe("L-SUBMIT web routes", () => {
  it("L-SUBMIT keys: a draft's row id or an idea's reference, nothing else", () => {
    expect(isKey(DRAFT)).toBe(true);
    expect(isKey("IDEA-2026-001481")).toBe(true);
    for (const bad of ["", "x' or 1=1", "IDEA-26-1", DRAFT.toUpperCase(), "../internal/config"]) {
      expect(isKey(bad)).toBe(false);
    }
  });

  it("L-SUBMIT a malformed key is a 404 and never reaches the worker", async () => {
    for (const res of await Promise.all([
      readSorting(me, "nope"),
      patchSorting(me, "nope", {}),
      sendView(me, "nope"),
      submitDraft(me, "nope", {}, new Headers()),
      saveEdit(me, "nope", {}),
      versions(me, "nope"),
    ])) {
      expect(res.status).toBe(404);
      expect((await res.json()).error.code).toBe("not_found");
    }
    expect(calls).toEqual([]);
  });

  it("L-SUBMIT.send passes the person, the body and the Idempotency-Key (A-API.conventions/3)", async () => {
    answer = async () => Response.json({ idea_id: "IDEA-2026-001481" }, { status: 201 });
    const res = await submitDraft(
      me,
      DRAFT,
      { declaration_version: "1pc-2026-11" },
      new Headers({ "Idempotency-Key": "k-0123456789" }),
    );
    expect(res.status).toBe(201);
    expect(await res.json()).toEqual({ idea_id: "IDEA-2026-001481" });
    const url = new URL(calls[0]!.path, "http://worker");
    expect(url.pathname).toBe(`/internal/drafts/${DRAFT}/submit`);
    expect(url.searchParams.get("user_id")).toBe((me as { id: string }).id);
    expect(url.searchParams.get("idempotency_key")).toBe("k-0123456789");
    expect(calls[0]!.init.method).toBe("POST");
    expect(JSON.parse(String(calls[0]!.init.body))).toEqual({ declaration_version: "1pc-2026-11" });
  });

  it("L-SUBMIT.send refuses a malformed Idempotency-Key before calling the worker", async () => {
    const res = await submitDraft(me, DRAFT, {}, new Headers({ "Idempotency-Key": "short" }));
    expect(res.status).toBe(400);
    expect(calls).toEqual([]);
  });

  it("V-FIELDS.checkit/13: when sending fails, the draft is safe and Submit says so", async () => {
    answer = async () => {
      throw new Error("connection refused");
    };
    const res = await submitDraft(me, DRAFT, {}, new Headers());
    expect(res.status).toBe(502);
    expect(await res.json()).toEqual(SEND_FAILED);
    expect(SEND_FAILED.error.message).toBe(
      "Couldn’t send. Your draft is safe. Check your connection, then try again.",
    );
  });

  it("L-SORT.rules/4: the worker's refusal reaches the screen unchanged, under its field", async () => {
    const refusal = {
      error: {
        code: "sorting_unconfirmed",
        message: "Confirm the sorting first, or change any of it.",
        field: "sorting",
      },
    };
    answer = async () => Response.json(refusal, { status: 422 });
    const res = await submitDraft(me, DRAFT, {}, new Headers());
    expect(res.status).toBe(422);
    expect(await res.json()).toEqual(refusal);
  });

  it("L-SORT and L-SUBMIT writes stop with the submissions switch; reads do not", () => {
    expect(switchesFor("PATCH", `/api/drafts/${DRAFT}/sorting`)).toContain("submissions");
    expect(switchesFor("POST", `/api/drafts/${DRAFT}/submit`)).toContain("submissions");
    expect(switchesFor("PATCH", "/api/ideas/IDEA-2026-001481/edit")).toContain("submissions");
    expect(switchesFor("GET", `/api/drafts/${DRAFT}/send`)).toEqual([]);
    expect(switchesFor("GET", "/api/ideas/IDEA-2026-001481/versions")).toEqual([]);
  });
});
