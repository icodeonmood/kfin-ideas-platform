import { describe, expect, it } from "vitest";

import {
  CODE_KEEP_HOURS,
  isWorkEmail,
  MemoryCodeStore,
  SEND_WINDOW_MINUTES,
  SENDS_PER_WINDOW,
  sendCode,
  verifyCode,
  type CodeDeps,
} from "@/server/auth/codes";

/** rules/promises.md `sign_in` (BLD-A181). */
const RULES = { code_digits: 6, code_valid_minutes: 10, code_tries: 3, resend_after_seconds: 45 };
const DOMAINS = ["kfintech.com", "kfintech.example"];
const ME = "kavya.menon@kfintech.example"; // synthetic
const LEAVER = "left.already@kfintech.example";

function world() {
  let now = new Date("2026-11-20T04:12:00Z");
  const store = new MemoryCodeStore();
  const mailed: Array<{ userId: string; code: string; validMinutes: number }> = [];
  let next = 0;
  const codes = ["481902", "112233", "445566", "778899", "135790", "246801", "999000"];
  const deps: CodeDeps = {
    store,
    rules: RULES,
    secret: "test-secret-of-at-least-32-characters!!",
    domains: DOMAINS,
    now: () => now,
    findUser: async (email) =>
      email === ME ? { id: "u-1", active: true } : email === LEAVER ? { id: "u-2", active: false } : null,
    mail: async (userId, code, validMinutes) => {
      mailed.push({ userId, code, validMinutes });
    },
    randomCode: () => codes[next++ % codes.length]!,
  };
  return {
    deps,
    store,
    mailed,
    later: (seconds: number) => {
      now = new Date(now.getTime() + seconds * 1000);
    },
  };
}

describe("L-AUTH.rules/2, V-FIELDS.signin/1: work addresses only", () => {
  it("takes @kfintech.com and the configured domains, nothing else", () => {
    expect(isWorkEmail("Name@KFintech.com", DOMAINS)).toBe(true);
    expect(isWorkEmail(ME, DOMAINS)).toBe(true);
    for (const bad of [
      "name@gmail.com",
      "name@kfintech.com.evil.in",
      "kfintech.com",
      "a b@kfintech.com",
      "",
    ]) {
      expect(isWorkEmail(bad, DOMAINS)).toBe(false);
    }
  });

  it("refuses to send to any other address", async () => {
    const w = world();
    expect(await sendCode(w.deps, "someone@gmail.com")).toEqual({ ok: false, error: "not_work_email" });
    expect(w.mailed).toEqual([]);
  });
});

describe("L-AUTH.rules/3: a 6-digit code, 10 minutes, 3 tries, a new one after 45 seconds", () => {
  it("sends a code and says for how long it works and when another can be asked for", async () => {
    const w = world();
    expect(await sendCode(w.deps, ` ${ME.toUpperCase()} `)).toEqual({
      ok: true,
      sentTo: ME,
      validMinutes: 10,
      resendInSeconds: 45,
    });
    expect(w.mailed).toEqual([{ userId: "u-1", code: "481902", validMinutes: 10 }]);
  });

  it("keeps only keyed hashes: neither the code nor the address is stored", async () => {
    const w = world();
    await sendCode(w.deps, ME);
    const row = w.store.rows[0]!;
    expect(JSON.stringify(w.store.rows)).not.toContain("481902");
    expect(JSON.stringify(w.store.rows)).not.toContain("kavya");
    expect(row.codeHash).toMatch(/^[0-9a-f]{64}$/);
    expect(row.emailHash).toMatch(/^[0-9a-f]{64}$/);
  });

  it("V-FIELDS.signin/6: no new code before the countdown ends", async () => {
    const w = world();
    await sendCode(w.deps, ME);
    w.later(30);
    expect(await sendCode(w.deps, ME)).toEqual({ ok: false, error: "too_soon", resendInSeconds: 15 });
    expect(w.mailed).toHaveLength(1);
  });

  it("a new code invalidates the old one", async () => {
    const w = world();
    await sendCode(w.deps, ME);
    w.later(45);
    await sendCode(w.deps, ME);
    expect(await verifyCode(w.deps, ME, "481902")).toEqual({ ok: false, error: "wrong_code", triesLeft: 2 });
    expect(await verifyCode(w.deps, ME, "112233")).toEqual({ ok: true, userId: "u-1" });
  });

  it("V-FIELDS.signin/4: a wrong code says how many tries are left, counted on the server", async () => {
    const w = world();
    await sendCode(w.deps, ME);
    expect(await verifyCode(w.deps, ME, "000000")).toEqual({ ok: false, error: "wrong_code", triesLeft: 2 });
    expect(await verifyCode(w.deps, ME, "000001")).toEqual({ ok: false, error: "wrong_code", triesLeft: 1 });
  });

  it("V-FIELDS.signin/5: out of tries, a fresh code goes out once and the old one never works", async () => {
    const w = world();
    await sendCode(w.deps, ME);
    w.later(RULES.resend_after_seconds);
    await verifyCode(w.deps, ME, "000000");
    await verifyCode(w.deps, ME, "000001");
    expect(await verifyCode(w.deps, ME, "000002")).toEqual({
      ok: false,
      error: "code_expired",
      resent: true,
      resendInSeconds: 45,
    });
    expect(w.mailed.map((m) => m.code)).toEqual(["481902", "112233"]);
    expect(await verifyCode(w.deps, ME, "481902")).toEqual({ ok: false, error: "wrong_code", triesLeft: 2 });
    expect(await verifyCode(w.deps, ME, "112233")).toEqual({ ok: true, userId: "u-1" });
  });

  it("V-FIELDS.signin/5: after 10 minutes the code has run out and a fresh one is sent", async () => {
    const w = world();
    await sendCode(w.deps, ME);
    w.later(10 * 60);
    expect(await verifyCode(w.deps, ME, "481902")).toEqual({
      ok: false,
      error: "code_expired",
      resent: true,
      resendInSeconds: 45,
    });
    expect(w.mailed).toHaveLength(2);
  });

  it("L-AUTH.rules/3: out of tries inside 45 seconds, no new code until the countdown ends", async () => {
    const w = world();
    await sendCode(w.deps, ME);
    w.later(10);
    await verifyCode(w.deps, ME, "000000");
    await verifyCode(w.deps, ME, "000001");
    expect(await verifyCode(w.deps, ME, "000002")).toEqual({
      ok: false,
      error: "code_expired",
      resent: false,
      resendInSeconds: 35,
    });
    expect(w.mailed).toHaveLength(1);
    w.later(20);
    expect(await verifyCode(w.deps, ME, "481902")).toMatchObject({ resent: false, resendInSeconds: 15 });
    w.later(15);
    expect(await verifyCode(w.deps, ME, "481902")).toMatchObject({ error: "code_expired", resent: true });
    expect(w.mailed.map((m) => m.code)).toEqual(["481902", "112233"]);
    expect(await verifyCode(w.deps, ME, "112233")).toEqual({ ok: true, userId: "u-1" });
  });

  it("BLD-A177: issuing a code deletes codes that ran out more than a day ago", async () => {
    const w = world();
    await sendCode(w.deps, ME);
    w.later(60);
    await sendCode(w.deps, "no.such.person@kfintech.example");
    expect(w.store.rows).toHaveLength(2);
    w.later(CODE_KEEP_HOURS * 3600 + 11 * 60);
    await sendCode(w.deps, ME);
    expect(w.store.rows).toHaveLength(1);
    expect(await verifyCode(w.deps, ME, "445566")).toEqual({ ok: true, userId: "u-1" });
  });

  it("a code works once", async () => {
    const w = world();
    await sendCode(w.deps, ME);
    expect(await verifyCode(w.deps, ME, "481902")).toEqual({ ok: true, userId: "u-1" });
    expect((await verifyCode(w.deps, ME, "481902")).ok).toBe(false);
  });

  it("V-FIELDS.signin/7: too many codes in the window is refused", async () => {
    const w = world();
    for (let i = 0; i < SENDS_PER_WINDOW; i++) {
      expect((await sendCode(w.deps, ME)).ok).toBe(true);
      w.later(RULES.resend_after_seconds);
    }
    expect(await sendCode(w.deps, ME)).toEqual({ ok: false, error: "rate_limited" });
    w.later(SEND_WINDOW_MINUTES * 60);
    expect((await sendCode(w.deps, ME)).ok).toBe(true);
  });
});

describe("L-AUTH.errors: who can sign in this way", () => {
  it("a leaver is told the account cannot sign in", async () => {
    const w = world();
    expect(await sendCode(w.deps, LEAVER)).toEqual({ ok: false, error: "account_disabled" });
    expect(w.mailed).toEqual([]);
  });

  it("an address with no account gets the same answers and no email (no list of who works here)", async () => {
    const w = world();
    const stranger = "no.such.person@kfintech.example";
    expect(await sendCode(w.deps, stranger)).toEqual({
      ok: true,
      sentTo: stranger,
      validMinutes: 10,
      resendInSeconds: 45,
    });
    expect(w.mailed).toEqual([]);
    expect(await verifyCode(w.deps, stranger, "000000")).toEqual({
      ok: false,
      error: "wrong_code",
      triesLeft: 2,
    });
  });
});
