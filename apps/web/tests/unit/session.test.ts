import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { cookieOptions, openTx, safeNext, sealTx } from "@/server/auth/session";

describe("sign-in cookies", () => {
  const saved = { ...process.env };
  afterEach(() => {
    process.env = { ...saved };
  });

  it("are Secure in UAT and production, and on any HTTPS address", () => {
    process.env.APP_ENV = "uat";
    process.env.APP_BASE_URL = "https://ideas.uat.example";
    expect(cookieOptions().secure).toBe(true);
    process.env.APP_ENV = "prod";
    expect(cookieOptions(0).secure).toBe(true);
    process.env.APP_ENV = "dev";
    process.env.APP_BASE_URL = "https://ideas.dev.example";
    expect(cookieOptions().secure).toBe(true);
  });

  it("stay Secure in every production-like environment even on a plain-HTTP address (behind a TLS proxy)", () => {
    process.env.APP_BASE_URL = "http://ideas.internal";
    for (const env of ["uat", "prod", "staging"]) {
      process.env.APP_ENV = env;
      expect(cookieOptions().secure).toBe(true);
    }
  });

  it("drop Secure only on the plain-HTTP local stack, so Safari keeps the sign-in state (BLD-153)", () => {
    process.env.APP_ENV = "dev";
    process.env.APP_BASE_URL = "http://localhost:3000";
    expect(cookieOptions().secure).toBe(false);
    delete process.env.APP_BASE_URL;
    expect(cookieOptions().secure).toBe(false);
  });
});

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
    // Review finding: the URL parser strips tabs and newlines, so "/\t/evil" would become "//evil".
    for (const evil of [
      "/\t/evil.example",
      "/\n/evil.example",
      "/\r/evil.example",
      "/ /evil.example",
      "/\u0000x",
    ]) {
      expect(safeNext(evil)).toBe("/");
    }
    expect(safeNext("/wall#top")).toBe("/wall#top");
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
