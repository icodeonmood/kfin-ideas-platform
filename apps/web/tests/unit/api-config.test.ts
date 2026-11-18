/**
 * GET /api/config (A-API.config; L-AUDIT.flags, L-AUDIT.config; BLD-A216): lane C's config (the promises, the
 * sorting lists and the declaration, `publicConfig`) and the person's S1 to S3 variants. If the worker cannot give the
 * config, the person's flags still come back, with the rest left out, rather than the whole call failing. The config
 * and the flags are replaced by stubs.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  me: null as null | Record<string, unknown>,
  workerUp: false,
  flagsFor: [] as string[],
}));

vi.mock("@/server/auth/current", () => ({ currentUser: async () => state.me }));
const CONFIG = {
  promises: { min_chars: 30, review_working_days: 5 },
  sorting: { affects: ["Investors"], areas: ["Operations"], brings: [], helpers: [] },
  declaration: { version: "2026-11-17", submit: "s", save: "v" },
};
vi.mock("@/server/share", () => ({
  publicConfig: async () => {
    if (!state.workerUp) throw new Error("config_unavailable");
    return CONFIG;
  },
}));
vi.mock("@/server/flags", () => ({
  flagsFor: async (userId: string) => {
    state.flagsFor.push(userId);
    return { s1: "alternative", s2: "default", s3: "default" };
  },
}));

const { GET } = await import("@/app/api/config/route");

const ME = "5d1e2f3a-4b5c-4d6e-8f70-81a2b3c4d5e6";

beforeEach(() => {
  state.me = { id: ME, privacyAccepted: true, roles: new Set(["contributor"]) };
  state.flagsFor = [];
  state.workerUp = true;
});

describe("L-AUDIT.config: GET /api/config", () => {
  it("BLD-A216: the worker down still gives the person's flags, with promises left out", async () => {
    state.workerUp = false;
    const res = await GET();
    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("private, no-store");
    expect(await res.json()).toEqual({ flags: { s1: "alternative", s2: "default", s3: "default" } });
    expect(state.flagsFor).toEqual([ME]);
  });

  it("with the worker up, gives both", async () => {
    state.workerUp = true;
    const res = await GET();
    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("private, no-store");
    expect(await res.json()).toEqual({
      ...CONFIG,
      flags: { s1: "alternative", s2: "default", s3: "default" },
    });
    expect(state.flagsFor).toEqual([ME]);
  });

  it("someone signed out gets nothing", async () => {
    state.me = null;
    expect((await GET()).status).toBe(401);
    expect(state.flagsFor).toEqual([]);
  });
});
