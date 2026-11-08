import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { decryptJson, encryptJson } from "@/server/crypto";

describe("column encryption", () => {
  const saved = { ...process.env };
  beforeEach(() => {
    process.env.VAULT_ENCRYPTION_KEY = "unit-test-vault-key-0123456789abcdef";
  });
  afterEach(() => {
    process.env = { ...saved };
  });

  it("round-trips and binds the ciphertext to its row", () => {
    const blob = encryptJson({ details: "synthetic draft text" }, "row-1");
    expect(blob.includes(Buffer.from("synthetic"))).toBe(false);
    expect(decryptJson(blob, "row-1")).toEqual({ details: "synthetic draft text" });
    expect(() => decryptJson(blob, "row-2")).toThrow();
    const tampered = Buffer.from(blob);
    tampered[tampered.length - 1]! ^= 1;
    expect(() => decryptJson(tampered, "row-1")).toThrow();
  });

  it("refuses the placeholder key outside dev", () => {
    process.env.VAULT_ENCRYPTION_KEY = "change-me";
    process.env.APP_ENV = "prod";
    expect(() => encryptJson({}, "row")).toThrow(/placeholder/);
  });
});
