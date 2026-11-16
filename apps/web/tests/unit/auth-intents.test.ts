import { describe, expect, it, vi } from "vitest";

import {
  cleanIntent,
  destination,
  draftFromPath,
  MemoryIntentStore,
  nextScreen,
  INTENT_TTL_MINUTES,
} from "@/server/auth/intents";
import { withTableFallback } from "@/server/auth/table-fallback";

const DRAFT = "0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10";

describe("L-AUTH.rules/4: where the person was going", () => {
  it("keeps only same-site paths, and never a sign-in page (that would loop)", () => {
    for (const evil of ["https://example.com", "//example.com", "/\\example.com", "/\t/example.com", "x"]) {
      expect(cleanIntent({ to: evil }).to).toBe("/");
    }
    for (const loop of ["/sign-in", "/sign-in?signing=1", "/auth/callback", "/signed-out"]) {
      expect(cleanIntent({ to: loop }).to).toBe("/");
    }
    expect(cleanIntent({ to: "/share" })).toEqual({ to: "/share", draftId: null, step: null });
    expect(cleanIntent({ to: "/my-ideas?tab=drafts" }).to).toBe("/my-ideas?tab=drafts");
  });

  it("reads a draft and its step from the path, and keeps only E-ENUMS steps", () => {
    expect(draftFromPath(`/share/${DRAFT}`)).toEqual({ draftId: DRAFT, step: "tell" });
    expect(draftFromPath(`/share/${DRAFT}/check`)).toEqual({ draftId: DRAFT, step: "check:1" });
    expect(draftFromPath("/share/not-a-draft")).toBeNull();
    expect(cleanIntent({ to: `/share/${DRAFT}/check`, step: "check:4" }).step).toBe("check:4");
    expect(cleanIntent({ to: `/share/${DRAFT}`, step: "drop table" }).step).toBe("tell");
    expect(cleanIntent({ to: "/", draftId: "nope" }).draftId).toBeNull();
  });

  it("lands on the draft at its step, the composer after Share a problem, else Home (P-ROUTES.state)", () => {
    expect(destination(cleanIntent({ to: `/share/${DRAFT}`, step: "check:3" }))).toBe(
      `/share/${DRAFT}/check`,
    );
    expect(destination(cleanIntent({ to: `/share/${DRAFT}`, step: "send" }))).toBe(`/share/${DRAFT}/check`);
    expect(destination(cleanIntent({ to: `/share/${DRAFT}` }))).toBe(`/share/${DRAFT}`);
    expect(destination(cleanIntent({ to: "/share" }))).toBe("/share");
    expect(destination(null)).toBe("/");
  });

  it("S-02's Next: line names the composer, Home, or nothing else (the cameFrom tweak)", () => {
    expect(nextScreen(cleanIntent({ to: "/share" }))).toBe("share");
    expect(nextScreen(cleanIntent({ to: `/share/${DRAFT}` }))).toBe("share");
    expect(nextScreen(cleanIntent({ to: "/" }))).toBe("home");
    expect(nextScreen(cleanIntent({ to: "/wall" }))).toBeNull();
  });

  it("is used once, and not after the TTL (a replayed callback finds nothing)", async () => {
    const store = new MemoryIntentStore();
    const t0 = new Date("2026-11-20T04:00:00Z");
    await store.save("k", cleanIntent({ to: "/share" }), t0);
    expect(await store.find("k", t0)).toEqual({ to: "/share", draftId: null, step: null });
    expect(await store.use("k", t0)).toEqual({ to: "/share", draftId: null, step: null });
    expect(await store.use("k", t0)).toBeNull();

    await store.save("old", cleanIntent({ to: "/share" }), t0);
    const late = new Date(t0.getTime() + (INTENT_TTL_MINUTES + 1) * 60_000);
    expect(await store.find("old", late)).toBeNull();
    expect(await store.use("old", late)).toBeNull();
  });
});

describe("BLD-A173: storage before lane E's cut-over", () => {
  it("uses the table, and process memory only once the table is reported missing", async () => {
    const missing = Object.assign(new Error("relation does not exist"), { code: "42P01" });
    const db = { hit: vi.fn(async () => "db") };
    const memory = { hit: vi.fn(async () => "memory") };
    const store = withTableFallback("t", db, memory);
    expect(await store.hit()).toBe("db");
    db.hit.mockRejectedValueOnce(missing);
    expect(await store.hit()).toBe("memory");
    expect(await store.hit()).toBe("memory");
    expect(db.hit).toHaveBeenCalledTimes(2);
  });

  it("never hides any other database error", async () => {
    const boom = Object.assign(new Error("connection lost"), { code: "08006" });
    const store = withTableFallback(
      "t",
      { hit: async () => Promise.reject(boom) },
      { hit: async () => "memory" },
    );
    await expect(store.hit()).rejects.toBe(boom);
  });
});
