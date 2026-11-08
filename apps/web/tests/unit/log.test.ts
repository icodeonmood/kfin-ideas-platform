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
