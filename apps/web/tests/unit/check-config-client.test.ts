/**
 * S-05 and S-06B read GET /api/config through `api.config()`. When the worker is down the route answers 200 with the
 * person's flags only (BLD-A216); the client treats that as "config unavailable", so the screens keep their defaults
 * and never read `sorting` from an answer that has none (L-AUDIT.config, S-05, S-06B).
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, fullConfig } from "@/app/share/[id]/check/client";

const FLAGS = { s1: "default", s2: "default", s3: "default" };
const FULL = {
  promises: { min_chars: 30 },
  sorting: { affects: [], areas: [], brings: [], helpers: [] },
  declaration: { version: "v1", submit: "s", save: "v" },
  flags: FLAGS,
};

function answer(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(body, { status })),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("S-05/S-06B: api.config() and the flags-only answer (BLD-A216)", () => {
  it("a flags-only answer counts as config unavailable", async () => {
    answer({ flags: FLAGS });
    expect(await api.config()).toEqual({ ok: false, status: 503, error: null });
  });

  it("the full answer comes through as it is", async () => {
    answer(FULL);
    const r = await api.config();
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.body.sorting.helpers).toEqual([]);
  });

  it("a failed call stays failed", async () => {
    answer({ error: { code: "unauthorized", message: "" } }, 401);
    const r = await api.config();
    expect(r.ok).toBe(false);
    expect(r.status).toBe(401);
  });

  it("fullConfig needs both promises and sorting", () => {
    expect(fullConfig({ flags: FLAGS } as never)).toBe(false);
    expect(fullConfig({ promises: {}, flags: FLAGS } as never)).toBe(false);
    expect(fullConfig(FULL as never)).toBe(true);
    expect(fullConfig(null)).toBe(false);
  });
});
