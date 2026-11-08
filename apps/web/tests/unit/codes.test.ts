import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { contributorCode, empIdHash, SecretMissing } from "@/server/identity/codes";

// Same vector as services/worker/tests/test_b2_02_contributor_codes.py: both languages must agree exactly.
const VECTOR = {
  secret: "vector-secret-for-tests-only-0001",
  id: "SYN-90001",
  code: "CTR-fb857d",
  code8: "CTR-fb857d55",
  hash16: "a0cd9e28ae246d18",
};

describe("contributor codes (AT-B2-02, TypeScript side)", () => {
  const saved = { ...process.env };
  beforeEach(() => {
    process.env.CONTRIBUTOR_HMAC_SECRET = VECTOR.secret;
  });
  afterEach(() => {
    process.env = { ...saved };
  });

  it("matches the shared vector", () => {
    expect(contributorCode(VECTOR.id)).toBe(VECTOR.code);
    expect(contributorCode("  syn-90001 ")).toBe(VECTOR.code);
    expect(contributorCode(VECTOR.id, 8)).toBe(VECTOR.code8);
    expect(empIdHash(VECTOR.id).slice(0, 16)).toBe(VECTOR.hash16);
  });

  it("takes the secret only from the environment", () => {
    delete process.env.CONTRIBUTOR_HMAC_SECRET;
    expect(() => contributorCode(VECTOR.id)).toThrow(SecretMissing);
  });

  it("refuses the placeholder secret outside dev", () => {
    process.env.CONTRIBUTOR_HMAC_SECRET = "change-me";
    process.env.APP_ENV = "prod";
    expect(() => contributorCode(VECTOR.id)).toThrow(SecretMissing);
  });
});
