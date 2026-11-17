/** S-R4 and S-R2: what a failed call shows (A-API.conventions/2; §7.6 kill switches, non-negotiable 9). */
import { afterEach, describe, expect, it, vi } from "vitest";

import { BANNERS } from "@/lib/killswitch-routes";
import { call, replyError, TRY_AGAIN } from "@/lib/desk/reply";

describe("S-R4 A2: replyError", () => {
  it("a paused committee shows its banner, never the code", () => {
    const paused = { error: "paused", switch: "committee.flow", banner: BANNERS["committee.flow"] };
    expect(replyError(paused)).toEqual({ code: "paused", message: BANNERS["committee.flow"] });
    expect(replyError({ error: "paused", switch: "committee.flow" })?.message).toBe(
      BANNERS["committee.flow"],
    );
    expect(replyError({ error: "paused", banner: "Paused for now." })?.message).toBe("Paused for now.");
  });

  it("a bare 401 or 403 code shows the failure line", () => {
    expect(replyError({ error: "forbidden" })).toEqual({ code: "forbidden", message: TRY_AGAIN });
    expect(replyError({ error: "sign_in_required" })?.message).toBe(TRY_AGAIN);
  });

  it("the worker's own error keeps its words and its field", () => {
    const e = { code: "note_too_short", message: "Tell Kavya why, in a line or two.", field: "note" };
    expect(replyError({ error: e })).toEqual(e);
  });

  it("no error, no message", () => {
    expect(replyError({ window_id: "W-1" })).toBeNull();
    expect(replyError(null)).toBeNull();
    expect(replyError({ error: {} })?.message).toBe(TRY_AGAIN);
  });
});

describe("S-R4 A2: call", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("a 503 from the kill-switch check comes back as the banner", async () => {
    const body = { error: "paused", switch: "committee.flow", banner: BANNERS["committee.flow"] };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(body), { status: 503 })),
    );
    const r = await call("/api/committee/windows/W-1/extend", { method: "POST" });
    expect(r).toMatchObject({ ok: false, status: 503, error: { message: BANNERS["committee.flow"] } });
  });

  it("a dropped network is the failure line, and never throws", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );
    const r = await call("/api/committee/windows/W-1/extend", { method: "POST" });
    expect(r).toMatchObject({ ok: false, status: 0, error: { message: TRY_AGAIN } });
  });

  it("a good reply gives its body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response('{"window_id":"W-1"}', { status: 200 })),
    );
    expect(await call("/api/x", { method: "POST" })).toEqual({ ok: true, body: { window_id: "W-1" } });
  });
});
