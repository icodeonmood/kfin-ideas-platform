/**
 * L-AUTH.rules/1,4,8 and BLD-A177: starting single sign-on keeps a row only for somewhere other than `/` and within
 * the write limit, carries the place in the sealed transaction either way, and binds the transaction to the
 * browser's attempt; the callback refuses a transaction from another browser's attempt and compares state in
 * constant time.
 */
import { NextRequest } from "next/server";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/server/auth/oidc", async (original) => ({
  ...(await original<typeof import("@/server/auth/oidc")>()),
  authorizationUrl: async () => "https://idp.example/authorize",
}));

import { GET as callback } from "@/app/auth/callback/route";
import {
  ATTEMPT_COOKIE,
  attemptKeyHash,
  cleanIntent,
  INTENT_KEEP_HOURS,
  MemoryIntentStore,
  setIntentStoreForTests,
  worthKeeping,
} from "@/server/auth/intents";
import { openTx, sameSecret, sealTx, TX_COOKIE } from "@/server/auth/session";
import { startSso } from "@/server/auth/sso";
import { clientAddress, PER_ADDRESS, WindowLimiter } from "@/server/auth/throttle";

const saved = { ...process.env };
let store: MemoryIntentStore;
let address = 0;

beforeAll(() => {
  process.env.SESSION_SECRET = "unit-test-secret-unit-test-secret-0123456789";
  process.env.APP_BASE_URL = "http://localhost:3000";
});
afterAll(() => {
  process.env = { ...saved };
  setIntentStoreForTests(undefined);
});
beforeEach(() => {
  store = new MemoryIntentStore();
  setIntentStoreForTests(store);
  address += 1;
});

const request = (path: string, headers: Record<string, string> = {}) =>
  new NextRequest(new URL(path, "http://localhost:3000"), {
    headers: { "x-forwarded-for": `10.0.0.${address}`, ...headers },
  });

async function start(to: string) {
  const res = await startSso(request(`/auth/sso/start?to=${encodeURIComponent(to)}`), { to }, "link");
  const key = res.cookies.get(ATTEMPT_COOKIE)?.value;
  const tx = openTx(res.cookies.get(TX_COOKIE)?.value);
  return { res, key, tx };
}

describe("L-AUTH.rules/4, BLD-A177: what starting single sign-on writes", () => {
  it("keeps no row for `/`, but still binds the transaction to a fresh attempt", async () => {
    const { key, tx } = await start("/");
    expect(store.rows.size).toBe(0);
    expect(key).toBeTruthy();
    expect(tx?.next).toBe("/");
    expect(tx?.attempt).toBe(attemptKeyHash(key!));
  });

  it("keeps a row for the composer, and the transaction carries the same place", async () => {
    const { key, tx } = await start("/share");
    expect(store.rows.size).toBe(1);
    expect(await store.find(attemptKeyHash(key!), new Date())).toEqual({
      to: "/share",
      draftId: null,
      step: null,
    });
    expect(tx?.next).toBe("/share");
  });

  it("over the per-address limit, writes no row and the transaction alone carries the place", async () => {
    for (let i = 0; i < PER_ADDRESS.limit; i++) await start("/share");
    expect(store.rows.size).toBe(PER_ADDRESS.limit);
    const { tx } = await start("/share");
    expect(store.rows.size).toBe(PER_ADDRESS.limit);
    expect(tx?.next).toBe("/share");
  });

  it("is worth a row only somewhere other than `/`, or for a draft", () => {
    expect(worthKeeping(cleanIntent({ to: "/" }))).toBe(false);
    expect(worthKeeping(cleanIntent({ to: "/sign-in" }))).toBe(false);
    expect(worthKeeping(cleanIntent({ to: "/share" }))).toBe(true);
    expect(worthKeeping(cleanIntent({ to: "/share/0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10" }))).toBe(true);
  });

  it("deletes rows older than a day when another is written, and a used row at once", async () => {
    const t0 = new Date("2026-11-20T04:00:00Z");
    await store.save("old", cleanIntent({ to: "/share" }), t0);
    await store.save("used", cleanIntent({ to: "/wall" }), t0);
    expect(await store.use("used", t0)).not.toBeNull();
    expect(store.rows.has("used")).toBe(false);
    await store.save(
      "new",
      cleanIntent({ to: "/share" }),
      new Date(t0.getTime() + (INTENT_KEEP_HOURS + 1) * 3_600_000),
    );
    expect([...store.rows.keys()]).toEqual(["new"]);
  });
});

describe("BLD-A177: the write limit", () => {
  it("allows the limit in the window, refuses the next, and frees up as the window slides", () => {
    const limiter = new WindowLimiter(2, 1_000);
    expect(limiter.take("a", 0)).toBe(true);
    expect(limiter.take("a", 10)).toBe(true);
    expect(limiter.take("a", 20)).toBe(false);
    expect(limiter.take("b", 20)).toBe(true);
    expect(limiter.take("a", 1_001)).toBe(true);
  });

  it("forgets the least recently used address beyond its size", () => {
    const limiter = new WindowLimiter(1, 60_000, 2);
    limiter.take("a", 0);
    limiter.take("b", 0);
    limiter.take("c", 0);
    expect(limiter.take("a", 1)).toBe(true); // "a" was forgotten
    expect(limiter.take("c", 1)).toBe(false);
  });

  it("reads the address the nearest proxy saw (the last X-Forwarded-For entry)", () => {
    const h = (headers: Record<string, string>) => ({ headers: new Headers(headers) });
    expect(clientAddress(h({ "x-forwarded-for": "1.1.1.1, 10.1.2.3" }))).toBe("10.1.2.3");
    expect(clientAddress(h({ "x-real-ip": "10.9.9.9" }))).toBe("10.9.9.9");
    expect(clientAddress(h({}))).toBe("unknown");
  });
});

describe("L-AUTH.rules/8, BLD-A177: the callback signs in only the browser that started", () => {
  const tx = (attempt: string) =>
    sealTx({
      state: "s".repeat(43),
      nonce: "n",
      verifier: "v",
      next: "/share",
      attempt,
      iat: Math.floor(Date.now() / 1000),
    });

  it("refuses a transaction whose attempt is not this browser's (login CSRF), with a reference", async () => {
    const res = await callback(
      request(`/auth/callback?code=abc&state=${"s".repeat(43)}`, {
        cookie: `${TX_COOKIE}=${tx(attemptKeyHash("theirs"))}; ${ATTEMPT_COOKIE}=mine`,
      }),
    );
    expect(res.headers.get("location")).toMatch(/\/sign-in\?failed=SSO-[0-9A-F]{4}&at=\d+$/);
    expect(res.cookies.get("ideas_session")).toBeUndefined();
  });

  it("refuses a missing attempt cookie and a wrong state", async () => {
    for (const cookie of [
      `${TX_COOKIE}=${tx(attemptKeyHash("mine"))}`,
      `${TX_COOKIE}=${tx(attemptKeyHash("mine"))}; ${ATTEMPT_COOKIE}=mine; x=`,
    ]) {
      const state = cookie.endsWith("x=") ? "t".repeat(43) : "s".repeat(43);
      const res = await callback(request(`/auth/callback?code=abc&state=${state}`, { cookie }));
      expect(res.headers.get("location")).toMatch(/\/sign-in\?failed=SSO-/);
    }
  });

  it("compares secrets in constant time, and unequal lengths are unequal", () => {
    expect(sameSecret("abc", "abc")).toBe(true);
    expect(sameSecret("abc", "abd")).toBe(false);
    expect(sameSecret("abc", "abcd")).toBe(false);
    expect(sameSecret(undefined, "abc")).toBe(false);
    expect(sameSecret(null, null)).toBe(false);
  });
});
