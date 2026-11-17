/**
 * L-AUTH.rules/4, S-02, BLD-A177: over the intent-write limit nobody loses their place (J-SHARE step 1, J-RESUME's
 * sign-in-again step). Single sign-on: the callback hands the sealed transaction's place back to S-02 as `to`, "Try
 * again" carries it on, and a start with nothing asked and no row takes the attempt's sealed place. Email code: an
 * explicit place travels in a sealed cookie that verify reads when there is no row. Every `to` stays a same-site path.
 */
import { NextRequest } from "next/server";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/server/auth/oidc", async (original) => ({
  ...(await original<typeof import("@/server/auth/oidc")>()),
  authorizationUrl: async () => "https://idp.example/authorize",
}));
vi.mock("@/server/auth/email-code", async (original) => ({
  ...(await original<typeof import("@/server/auth/email-code")>()),
  emailCodeOn: async () => true,
  liveCodeDeps: async () => ({}),
}));
vi.mock("@/server/auth/codes", async (original) => ({
  ...(await original<typeof import("@/server/auth/codes")>()),
  sendCode: async () => ({
    ok: true,
    sentTo: "kavya.menon@kfintech.example",
    validMinutes: 10,
    resendInSeconds: 45,
  }),
}));

import { GET as callback } from "@/app/auth/callback/route";
import { POST as sendCodeRoute } from "@/app/auth/code/send/route";
import { GET as startLink } from "@/app/auth/sso/start/route";
import {
  ATTEMPT_COOKIE,
  attemptKeyHash,
  cleanIntent,
  destination,
  MemoryIntentStore,
  openPlace,
  PLACE_COOKIE,
  retryHref,
  sealPlace,
  setIntentStoreForTests,
  signInHref,
  takePlace,
} from "@/server/auth/intents";
import { openTx, sealTx, TX_COOKIE } from "@/server/auth/session";
import { failurePath, startSso } from "@/server/auth/sso";
import { resetLimitsForTests } from "@/server/auth/throttle";

const saved = { ...process.env };
const BASE = "http://localhost:3000";
const DRAFT = "0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10"; // synthetic
const SHUT = { limit: 0, windowMs: 60_000 };
let store: MemoryIntentStore;

beforeAll(() => {
  process.env.SESSION_SECRET = "unit-test-secret-unit-test-secret-0123456789";
  process.env.APP_BASE_URL = BASE;
});
afterAll(() => {
  process.env = { ...saved };
  setIntentStoreForTests(undefined);
  resetLimitsForTests();
});
beforeEach(() => {
  store = new MemoryIntentStore();
  setIntentStoreForTests(store);
  resetLimitsForTests(SHUT, SHUT); // every write is over the limit
});

const request = (
  path: string,
  headers: Record<string, string> = {},
  init: { method?: string; body?: string } = {},
) =>
  new NextRequest(new URL(path, BASE), {
    method: init.method ?? "GET",
    body: init.body,
    headers: { "x-forwarded-for": "10.20.0.1", ...headers },
  });

/** Starts single sign-on for `to` with every write over the limit; returns the browser's cookies. */
async function startOver(to: string, silent = false) {
  const res = await startSso(request(`/auth/sso/start`), { to, silent: silent ? "1" : undefined }, "link");
  const attempt = res.cookies.get(ATTEMPT_COOKIE)!.value;
  const tx = res.cookies.get(TX_COOKIE)!.value;
  return { attempt, tx, cookie: `${ATTEMPT_COOKIE}=${attempt}; ${TX_COOKIE}=${tx}` };
}

const location = (res: Response) => res.headers.get("location") ?? "";

describe("L-AUTH.rules/4, BLD-A177: single sign-on over the write limit", () => {
  it("a silent try the provider can't finish shows S-02 with the place as `to` (J-SHARE step 1)", async () => {
    const { cookie } = await startOver("/share", true);
    expect(store.rows.size).toBe(0);
    const res = await callback(request(`/auth/callback?error=login_required`, { cookie }));
    expect(location(res)).toBe(`${BASE}/sign-in?to=%2Fshare`);
  });

  it("Could not sign in keeps the place, and its Try again starts single sign-on for it again", async () => {
    const { cookie } = await startOver("/share");
    const res = await callback(request(`/auth/callback?error=temporarily_unavailable`, { cookie }));
    expect(location(res)).toMatch(/\/sign-in\?failed=SSO-[0-9A-F]{4}&at=\d+&to=%2Fshare$/);

    const kept = cleanIntent({ to: new URL(location(res)).searchParams.get("to") });
    expect(retryHref(kept)).toBe("/auth/sso/start?to=%2Fshare");
    expect(signInHref(kept)).toBe("/sign-in?to=%2Fshare");
    const again = await startLink(request(retryHref(kept), { cookie }));
    expect(openTx(again.cookies.get(TX_COOKIE)?.value)?.next).toBe("/share");
  });

  it("a state or attempt mismatch also hands the place back, with a reference", async () => {
    const { tx } = await startOver("/share");
    const res = await callback(
      request(`/auth/callback?code=abc&state=${"x".repeat(43)}`, {
        cookie: `${TX_COOKIE}=${tx}; ${ATTEMPT_COOKIE}=other`,
      }),
    );
    expect(location(res)).toMatch(/\/sign-in\?failed=SSO-[0-9A-F]{4}&at=\d+&to=%2Fshare$/);
  });

  it("J-RESUME: a draft at Check it comes back to the same draft, and Try again names it", async () => {
    const { cookie } = await startOver(`/share/${DRAFT}/check`, true);
    const res = await callback(request(`/auth/callback?error=interaction_required`, { cookie }));
    expect(location(res)).toBe(`${BASE}/sign-in?to=${encodeURIComponent(`/share/${DRAFT}/check`)}`);
    const kept = cleanIntent({ to: `/share/${DRAFT}/check` });
    expect(retryHref(kept)).toBe(
      `/auth/sso/start?to=${encodeURIComponent(`/share/${DRAFT}/check`)}&draft_id=${DRAFT}&step=check%3A1`,
    );
  });

  it("a start with nothing asked and no row takes the place this attempt's sealed transaction carried", async () => {
    const { cookie } = await startOver("/share");
    const res = await startSso(request("/auth/sso/start", { cookie }), {}, "redirect");
    expect(openTx(res.cookies.get(TX_COOKIE)?.value)?.next).toBe("/share");
  });

  it("but not a transaction from another attempt: that lands on `/`", async () => {
    const { tx } = await startOver("/share");
    const res = await startSso(
      request("/auth/sso/start", { cookie: `${ATTEMPT_COOKIE}=someone-else; ${TX_COOKIE}=${tx}` }),
      {},
      "redirect",
    );
    expect(openTx(res.cookies.get(TX_COOKIE)?.value)?.next).toBe("/");
  });

  it("the place handed back is always a same-site path (no open redirect)", async () => {
    for (const next of [
      "//evil.example/x",
      "https://evil.example",
      "/\t/evil.example",
      "/sign-in?to=/share",
    ]) {
      const sealed = sealTx({
        state: "s",
        nonce: "n",
        verifier: "v",
        silent: true,
        next,
        iat: Math.floor(Date.now() / 1000),
      });
      const res = await callback(
        request(`/auth/callback?error=login_required`, { cookie: `${TX_COOKIE}=${sealed}` }),
      );
      expect(location(res)).toBe(`${BASE}/sign-in`);
    }
    expect(failurePath("failed", "SSO-7F3A", new Date(0), cleanIntent({ to: "//evil.example" }))).toBe(
      "/sign-in?failed=SSO-7F3A&at=0",
    );
  });

  it("with no place, the links stay as they were", () => {
    expect(retryHref(null)).toBe("/auth/sso/start");
    expect(retryHref(cleanIntent({ to: "/" }))).toBe("/auth/sso/start");
    expect(signInHref(cleanIntent({ to: "/" }))).toBe("/sign-in");
  });
});

describe("L-AUTH.rules/4, BLD-A177: the email code over the write limit", () => {
  const send = (intent: Record<string, unknown> | undefined, cookie = "") =>
    sendCodeRoute(
      request(
        "/auth/code/send",
        { "content-type": "application/json", ...(cookie ? { cookie } : {}) },
        { method: "POST", body: JSON.stringify({ email: "kavya.menon@kfintech.example", intent }) },
      ),
    );

  it("an explicit place is kept in a sealed cookie, and verify lands there with no row", async () => {
    const res = await send({ to: "/share" });
    expect(res.status).toBe(200);
    expect(store.rows.size).toBe(0);
    const place = res.cookies.get(PLACE_COOKIE)?.value;
    expect(place).toBeTruthy();
    const jar = new Map([[PLACE_COOKIE, { value: place! }]]);
    expect(destination(await takePlace(jar, new Date()))).toBe("/share");
  });

  it("an older attempt's row cannot send the person somewhere else", async () => {
    await store.save(attemptKeyHash("older"), cleanIntent({ to: "/wall" }), new Date());
    const res = await send({ to: "/share" }, `${ATTEMPT_COOKIE}=older`);
    expect(res.cookies.get(ATTEMPT_COOKIE)?.value).toBe("");
    const jar = new Map([[PLACE_COOKIE, { value: res.cookies.get(PLACE_COOKIE)!.value }]]);
    expect(destination(await takePlace(jar, new Date()))).toBe("/share");
  });

  it("under the limit a row is kept as before, and a stale sealed place is cleared", async () => {
    resetLimitsForTests();
    const stale = sealPlace(cleanIntent({ to: "/wall" }), new Date());
    const res = await send({ to: "/share" }, `${PLACE_COOKIE}=${stale}`);
    expect(store.rows.size).toBe(1);
    expect(res.cookies.get(PLACE_COOKIE)?.value).toBe("");
    const jar = new Map([[ATTEMPT_COOKIE, { value: res.cookies.get(ATTEMPT_COOKIE)!.value }]]);
    expect(destination(await takePlace(jar, new Date()))).toBe("/share");
  });

  it("asking for `/` clears a sealed place", async () => {
    const stale = sealPlace(cleanIntent({ to: "/wall" }), new Date());
    const res = await send({ to: "/" }, `${PLACE_COOKIE}=${stale}`);
    expect(res.cookies.get(PLACE_COOKIE)?.value).toBe("");
  });

  it("a sealed place cannot be edited, runs out with the attempt, and is cleaned again when read", () => {
    const now = new Date("2026-11-20T04:00:00Z");
    const sealed = sealPlace(cleanIntent({ to: `/share/${DRAFT}/check`, step: "check:3" }), now);
    expect(openPlace(sealed, now)).toEqual({ to: `/share/${DRAFT}/check`, draftId: DRAFT, step: "check:3" });

    const [payload, mac] = sealed.split(".");
    const edited = Buffer.from(
      JSON.stringify({ to: "https://evil.example", iat: Math.floor(now.getTime() / 1000) }),
    ).toString("base64url");
    expect(openPlace(`${edited}.${mac}`, now)).toBeNull();
    expect(openPlace(`${payload}.${mac!.slice(0, -1)}${mac!.endsWith("A") ? "B" : "A"}`, now)).toBeNull();
    expect(openPlace(sealed, new Date(now.getTime() + 31 * 60_000))).toBeNull();

    const hostile = sealPlace({ to: "//evil.example", draftId: null, step: null }, now);
    expect(destination(openPlace(hostile, now))).toBe("/");
  });
});
