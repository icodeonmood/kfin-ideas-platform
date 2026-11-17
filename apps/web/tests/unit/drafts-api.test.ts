/** L-DRAFT web side (BLD-C071): the device asking, the A-API error shape, and the kill switches on drafts. */
import { NextRequest } from "next/server";
import { describe, expect, it, vi } from "vitest";

import { switchesFor } from "@/lib/killswitch-routes";
import type { CurrentUser } from "@/server/auth/current";
import { DRAFT_MESSAGES, DraftApiError, deviceOf, draftError, drafts, openElsewhere } from "@/server/drafts";
import { workerFetch } from "@/server/worker";

vi.mock("@/server/worker", () => ({
  workerFetch: vi.fn(async () => Response.json({ latest: null, run: null })),
}));

const req = (headers: Record<string, string>) => new NextRequest("http://localhost/api/drafts", { headers });

describe("L-DRAFT.autosave/4: which device asks", () => {
  it("takes the client's word for phone or laptop and keeps only a well-formed device id", () => {
    expect(deviceOf(req({ "x-device": "phone", "x-device-id": "dev_abc12345" }))).toEqual({
      kind: "phone",
      id: "dev_abc12345",
    });
    expect(deviceOf(req({ "x-device": "laptop", "x-device-id": "bad id!" }))).toEqual({
      kind: "laptop",
      id: null,
    });
  });

  it("falls back to the browser: a phone's user agent is a phone", () => {
    const ua = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Mobile Safari/537.36";
    expect(deviceOf(req({ "user-agent": ua })).kind).toBe("phone");
    expect(deviceOf(req({ "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0)" })).kind).toBe(
      "laptop",
    );
  });
});

describe("A-API.conventions/2 on drafts", () => {
  it("L-DRAFT.autosave/5: open on another device says where, ready to show", async () => {
    const res = draftError(new DraftApiError(409, "open_elsewhere", { device: "phone" }));
    expect(res.status).toBe(409);
    expect(await res.json()).toEqual({
      error: {
        code: "open_elsewhere",
        message: "This draft is open on your phone. Carry on here?",
        device: "phone",
      },
    });
    expect(openElsewhere("laptop")).toBe("This draft is open on your laptop. Carry on here?");
  });

  it("names the field a refusal is about", async () => {
    const res = draftError(new DraftApiError(422, "too_long", { field: "value" }));
    expect(await res.json()).toEqual({
      error: { code: "too_long", message: DRAFT_MESSAGES.too_long, field: "value" },
    });
  });

  it("never says rejected, invalid or duplicate", () => {
    for (const text of Object.values(DRAFT_MESSAGES))
      expect(text).not.toMatch(/rejected|invalid|duplicate|garage/i);
  });

  it("rethrows what it does not know", () => {
    expect(() => draftError(new Error("boom"))).toThrow("boom");
  });
});

describe("kill switches on drafts (§7.6, DEC-105)", () => {
  it("saving pauses with sharing; reading and the stream stay open; the assistant switch is never needed", () => {
    expect(switchesFor("POST", "/api/drafts")).toEqual(["submissions"]);
    expect(switchesFor("POST", "/api/drafts/x/messages")).toEqual(["submissions"]);
    expect(switchesFor("PATCH", "/api/drafts/x/parts/title")).toEqual(["submissions"]);
    expect(switchesFor("DELETE", "/api/drafts/x")).toEqual(["submissions"]);
    expect(switchesFor("GET", "/api/drafts/x")).toEqual([]);
    expect(switchesFor("GET", "/api/drafts/x/stream")).toEqual([]);
  });
});

describe("A-API.draft-stream: each read keeps its own time limit (BLD-C039)", () => {
  it("the stream's 5-second read is not stretched to the 15 seconds a write gets", async () => {
    const timeout = vi.spyOn(AbortSignal, "timeout");
    const me = { id: "00000000-0000-4000-8000-000000000c39", contributorCode: "CTR-0a1b2c" } as CurrentUser;
    const device = { kind: "laptop" as const, id: null };
    await drafts.live(me, device, "00000000-0000-4000-8000-0000000000d1");
    expect(timeout.mock.calls.map((c) => c[0])).toEqual([5_000]);
    expect(vi.mocked(workerFetch).mock.calls[0]?.[1]?.signal).toBe(timeout.mock.results[0]?.value);
    await drafts.create(me, device, { channel: "web" });
    expect(timeout.mock.calls.map((c) => c[0])).toEqual([5_000, 15_000]);
    timeout.mockRestore();
  });
});
