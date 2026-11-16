import { describe, expect, it } from "vitest";

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
