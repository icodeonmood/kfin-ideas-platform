import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { openTx, safeNext, sealTx } from "@/server/auth/session";

describe("sign-in helpers", () => {
  const saved = { ...process.env };
  beforeEach(() => {
    process.env.SESSION_SECRET = "unit-test-session-secret-0123456789";
  });
  afterEach(() => {
    process.env = { ...saved };
  });

  it("only allows same-site relative paths after sign-in", () => {
    expect(safeNext("/my-ideas?tab=2")).toBe("/my-ideas?tab=2");
    for (const evil of ["https://example.com", "//example.com", "/\\example.com", "", null, undefined]) {
      expect(safeNext(evil)).toBe("/");
    }
  });

  it("seals the sign-in transaction against tampering and expiry", () => {
    const tx = { state: "s", nonce: "n", verifier: "v", next: "/", iat: Math.floor(Date.now() / 1000) };
    const sealed = sealTx(tx);
    expect(openTx(sealed)).toEqual(tx);
    const [payload] = sealed.split(".");
    const forged = Buffer.from(JSON.stringify({ ...tx, next: "/admin" })).toString("base64url");
    expect(openTx(`${forged}.${sealed.split(".")[1]}`)).toBeNull();
    expect(openTx(`${payload}.not-the-mac`)).toBeNull();
    expect(openTx(sealTx({ ...tx, iat: tx.iat - 3600 }))).toBeNull();
  });
});
