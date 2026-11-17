/** L-DRAFT web side (BLD-C071): the device asking, the A-API error shape, and the kill switches on drafts. */
import { NextRequest } from "next/server";
import { describe, expect, it, vi } from "vitest";

import { switchesFor } from "@/lib/killswitch-routes";
import type { CurrentUser } from "@/server/auth/current";
import { segments } from "@/lib/compose/hidden";
import {
  DRAFT_MESSAGES,
  DraftApiError,
  deviceOf,
  draftError,
  drafts,
  openElsewhere,
  spansForBrowser,
} from "@/server/drafts";
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

  it("BLD-C149: a voice note sent while voice is off reads the product lead's line, word for word", async () => {
    expect(DRAFT_MESSAGES.voice_unavailable).toBe("Voice notes are coming soon.");
    const res = draftError(new DraftApiError(503, "voice_unavailable"));
    expect(await res.json()).toMatchObject({
      error: { code: "voice_unavailable", message: "Voice notes are coming soon." },
    });
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

describe("L-HIDE offsets leave the server as the browser counts them (C-HIDDEN.where/1, BLD-C121)", () => {
  // Synthetic words. "🙂" is one code point (the worker's count) and two UTF-16 units (the browser's).
  const text = "🙂 Folio 1234567/89 called again";
  const folio = "Folio 1234567/89";
  const cp = { start: 2, end: 2 + folio.length, kind: "folio" }; // code points, after "🙂 "

  it("C-HIDDEN.where/1 an emoji before a detail: the underline still lands on the detail, not one unit early", () => {
    const body = {
      run_id: "r-1",
      message: { id: "m-1", text, spans: [cp] },
      draft: { id: "d-1", messages: [{ id: "m-1", text, spans: [cp] }], parts: { title: { value: "x" } } },
    };
    const out = spansForBrowser(body);
    expect(out.message.spans).toEqual([{ start: 3, end: 3 + folio.length, kind: "folio" }]);
    expect(out.draft.messages[0]!.spans).toEqual(out.message.spans);
    const cut = segments(text, out.message.spans as never).find((s) => s.kind);
    expect(cut?.text).toBe(folio);
    // Without the conversion the browser underlines from the space before "Folio" (the bug the review found).
    expect(segments(text, [cp] as never).find((s) => s.kind)?.text).not.toBe(folio);
    expect(out.run_id).toBe("r-1");
    expect(body.message.spans[0]).toBe(cp); // the worker's body is not changed in place
  });

  it("A-API.drafts the routes send the converted spans (GET /api/drafts/:id)", async () => {
    vi.mocked(workerFetch).mockResolvedValueOnce(
      Response.json({ id: "d-1", messages: [{ id: "m-1", text, spans: [cp] }] }),
    );
    vi.doMock("@/server/auth/authorize", () => ({
      authorize: vi.fn(async () => ({ id: "u-1", contributorCode: "C-0001" })),
    }));
    const { GET } = await import("@/app/api/drafts/[id]/route");
    const res = await GET(new NextRequest("http://localhost/api/drafts/d-1"), {
      params: Promise.resolve({ id: "d-1" }),
    });
    const body = (await res.json()) as { messages: { spans: { start: number }[] }[] };
    expect(body.messages[0]!.spans[0]!.start).toBe(3);
  });
});
