import { describe, expect, it, vi } from "vitest";

import { LogPolicyError, fieldIsForbidden, log } from "@/server/log";

describe("web logger (non-negotiable 3)", () => {
  it("refuses text-like field names", () => {
    for (const f of ["one_line", "details", "idea_text", "canvas", "name", "email", "neutral_summary"]) {
      expect(fieldIsForbidden(f)).toBe(true);
    }
    for (const f of ["idea_id", "outbox_id", "switch", "reason_code", "duration_ms"]) {
      expect(fieldIsForbidden(f)).toBe(false);
    }
  });

  it("throws in dev and test instead of writing text", () => {
    expect(() => log.info("scan.done", { details: "the idea body" })).toThrow(LogPolicyError);
    expect(() => log.info("Saved the idea")).toThrow(LogPolicyError);
    expect(() => log.info("scan.done", { ref: "mail someone@example.com" })).toThrow(LogPolicyError);
  });
});

describe("an actor UUID is an ID, not personal data (BLD-A183)", () => {
  it("never trips the value scan, while a phone number beside it still does", async () => {
    const { logValuePatterns } = await import("@/lib/pii/patterns");
    for (const tripped of [
      "user:39a14df0-6457-4f72-bc06-a6528110703c",
      "user:48bcbea8-338c-463c-b892-37429447669b",
      "user:39a048b5-e7c2-46e2-9a5f-811782882274",
    ]) {
      expect(logValuePatterns(tripped)).toEqual([]);
    }
    for (let i = 0; i < 5000; i += 1) {
      expect(logValuePatterns(`user:${crypto.randomUUID()}`)).toEqual([]);
    }
    expect(logValuePatterns("user:39a14df0-6457-4f72-bc06-a6528110703c 9876543210")).not.toEqual([]);
  });
});

describe("L-AUDIT, NN3: exact ID shapes skip the value scan, personal data does not (BLD-A189)", () => {
  // Synthetic UUIDs from the worker test's seed (random.Random(20261120)) whose digit runs look like a mobile,
  // card or Aadhaar number: as DRAFT-<uuid> or in upper case they were refused in dev, the demo and CI.
  const tripped = [
    "9f7499ea-9c89-96af-8f52-9c6965331798",
    "10fe3541-75dc-15f7-2993-4465871481aa",
    "85536546-2506-e890-1a21-e17110cbe889",
  ];
  const shapes = (u: string) => [u, `DRAFT-${u}`, `IDEA-${u}`, u.toUpperCase(), `DRAFT-${u.toUpperCase()}`];

  // mulberry32: a seeded generator, so the 20,000 IDs are the same on every run.
  function seeded(seed: number): () => number {
    let a = seed >>> 0;
    return () => {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return (t ^ (t >>> 14)) >>> 0;
    };
  }
  function uuidFrom(next: () => number): string {
    const hex = [next(), next(), next(), next()].map((n) => n.toString(16).padStart(8, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  it("the gateway's ref_id shapes are logged in strict mode, plain, prefixed and in a list", async () => {
    const { logValuePatterns, scan } = await import("@/lib/pii/patterns");
    const write = vi.spyOn(process.stdout, "write").mockImplementation(() => true);
    try {
      for (const u of tripped) {
        expect(scan(`DRAFT-${u}`).length).toBeGreaterThan(0);
        for (const value of shapes(u)) {
          expect(() => log.info("gateway.call", { ref_id: value, idea_uuid: value })).not.toThrow();
        }
        expect(() => log.info("gateway.batch", { ref_ids: shapes(u) })).not.toThrow();
      }
      const next = seeded(20261120);
      let wouldHaveTripped = 0;
      for (let i = 0; i < 20000; i += 1) {
        const u = uuidFrom(next);
        if (scan(`DRAFT-${u}`).length) wouldHaveTripped += 1;
        for (const value of shapes(u)) expect(logValuePatterns(value)).toEqual([]);
      }
      expect(wouldHaveTripped).toBeGreaterThan(0);
    } finally {
      write.mockRestore();
    }
  });

  it("still refuses a card, PAN, email or phone, alone, after DRAFT- or beside an ID", () => {
    const fixed = "1b2c3d4e-5f60-4a1b-9c2d-0a1b2c3d4e5f";
    const personal = [
      "4111-1111-1111-1111",
      "4111111111111111",
      "4111 1111 1111 1111",
      "ABCPE1234F",
      "asha.rao12@example.com",
      "+91 98765 43210",
      "9876543210",
    ];
    for (const value of personal) {
      for (const wrapped of [
        value,
        `DRAFT-${value}`,
        `IDEA-${value}`,
        `DRAFT-${fixed} ${value}`,
        `${fixed} ${value}`,
        `ref for ${value} here`,
      ]) {
        expect(() => log.info("gateway.call", { ref_id: wrapped })).toThrow(LogPolicyError);
        expect(() => log.info("gateway.batch", { ref_ids: [`DRAFT-${fixed}`, wrapped] })).toThrow(
          LogPolicyError,
        );
      }
    }
  });
});
