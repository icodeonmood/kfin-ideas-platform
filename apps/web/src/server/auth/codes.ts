/**
 * Sign-in by email code, the other route (L-AUTH.rules/2-3, V-FIELDS.signin, A-API.auth). Built behind the
 * `auth.email_code` kill switch, off until InfoSec approves it (BLD-E002, DEC-105).
 *
 * - Only work addresses: @kfintech.com plus the domains in KFIN_EMAIL_DOMAINS.
 * - A code of `code_digits` digits, valid `code_valid_minutes`, `code_tries` tries, a new one after
 *   `resend_after_seconds` (rules/promises.md `sign_in`, BLD-A181). A new code supersedes the old one.
 * - Only keyed hashes are stored: of the address and of the code (HMAC with the session secret, so a copy of the
 *   table cannot be turned back into codes by trying all million of them).
 * - Every guess spends a try before it is compared, so parallel guesses cannot exceed the tries.
 * - Out of tries or expired: a fresh code goes out automatically, once per spent code (`L-AUTH.states`), within
 *   the send limit.
 * - An address with no account gets the same answers as one with an account, and no email (no list of who works
 *   here). A leaver's address is told it cannot sign in (`L-AUTH.errors`).
 *
 * Storage sits behind `CodeStore`: `sign_in_codes` arrives in lane E's cut-over; memory backs the unit tests.
 */
import { createHmac, randomInt, timingSafeEqual } from "node:crypto";

import { sql } from "kysely";

import { getDb } from "../db";
import { withTableFallback } from "./table-fallback";

/** Sends allowed per address in the window; "Too many tries. Wait 10 minutes, or use single sign-on." */
export const SENDS_PER_WINDOW = 5;
export const SEND_WINDOW_MINUTES = 10;

export type CodeRules = {
  code_digits: number;
  code_valid_minutes: number;
  code_tries: number;
  resend_after_seconds: number;
};

export type CodeRow = {
  id: string;
  emailHash: string;
  codeHash: string;
  expiresAt: Date;
  triesLeft: number;
  sentAt: Date;
  supersededAt: Date | null;
};

export interface CodeStore {
  /** The newest code for the address that has not been superseded or used. */
  current(emailHash: string): Promise<CodeRow | null>;
  /** Stores a new code and supersedes every earlier one for the address, in one step. */
  issue(row: Omit<CodeRow, "id" | "supersededAt">): Promise<void>;
  /** Spends one try if the code is still live; the tries left after it, or null if none could be spent. */
  spendTry(id: string, now: Date): Promise<number | null>;
  /** Marks the code used (superseded) so it never works twice; false if it was already used. */
  use(id: string, now: Date): Promise<boolean>;
  /** How many codes went to the address since then (the send limit). */
  sentSince(emailHash: string, since: Date): Promise<number>;
}

export type SendResult =
  | { ok: true; sentTo: string; validMinutes: number; resendInSeconds: number }
  | { ok: false; error: "not_work_email" | "rate_limited" | "account_disabled" }
  | { ok: false; error: "too_soon"; resendInSeconds: number };

export type VerifyResult =
  | { ok: true; userId: string }
  | { ok: false; error: "wrong_code"; triesLeft: number }
  | { ok: false; error: "code_expired"; resent: true }
  | { ok: false; error: "not_work_email" | "rate_limited" | "account_disabled" };

export type CodeDeps = {
  store: CodeStore;
  rules: CodeRules;
  secret: string;
  /** Allowed domains, lower case, without "@". */
  domains: readonly string[];
  now: () => Date;
  findUser: (email: string) => Promise<{ id: string; active: boolean } | null>;
  /** Emails the code to the person (the worker's comms path); never logged. */
  mail: (userId: string, code: string, validMinutes: number) => Promise<void>;
  randomCode?: (digits: number) => string;
};

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Work addresses only (V-FIELDS.signin/1): @kfintech.com and the configured domains. */
export function isWorkEmail(email: string, domains: readonly string[]): boolean {
  const e = email.trim().toLowerCase();
  if (e.length > 254 || !EMAIL.test(e)) return false;
  return domains.includes(e.split("@").pop() ?? "");
}

export function allowedDomains(): string[] {
  const extra = (process.env.KFIN_EMAIL_DOMAINS ?? "")
    .split(",")
    .map((d) => d.trim().toLowerCase().replace(/^@/, ""))
    .filter(Boolean);
  return [...new Set(["kfintech.com", ...extra])];
}

const hmac = (secret: string, value: string) => createHmac("sha256", secret).update(value).digest("hex");
export const emailHash = (secret: string, email: string) =>
  hmac(secret, `email:${email.trim().toLowerCase()}`);
const codeHash = (secret: string, eHash: string, code: string) => hmac(secret, `code:${eHash}:${code}`);

const sameHash = (a: string, b: string) => {
  const x = Buffer.from(a, "hex");
  const y = Buffer.from(b, "hex");
  return x.length === y.length && timingSafeEqual(x, y);
};

export const randomDigits = (digits: number) =>
  Array.from({ length: digits }, () => randomInt(0, 10).toString()).join("");

async function issueAndMail(
  deps: CodeDeps,
  email: string,
  eHash: string,
  user: { id: string; active: boolean } | null,
) {
  const now = deps.now();
  const sent = await deps.store.sentSince(eHash, new Date(now.getTime() - SEND_WINDOW_MINUTES * 60_000));
  if (sent >= SENDS_PER_WINDOW) return false;
  const code = (deps.randomCode ?? randomDigits)(deps.rules.code_digits);
  await deps.store.issue({
    emailHash: eHash,
    codeHash: codeHash(deps.secret, eHash, code),
    expiresAt: new Date(now.getTime() + deps.rules.code_valid_minutes * 60_000),
    triesLeft: deps.rules.code_tries,
    sentAt: now,
  });
  if (user?.active) await deps.mail(user.id, code, deps.rules.code_valid_minutes);
  return true;
}

/** POST /auth/code/send. */
export async function sendCode(deps: CodeDeps, rawEmail: string): Promise<SendResult> {
  const email = rawEmail.trim().toLowerCase();
  if (!isWorkEmail(email, deps.domains)) return { ok: false, error: "not_work_email" };
  const user = await deps.findUser(email);
  if (user && !user.active) return { ok: false, error: "account_disabled" };
  const eHash = emailHash(deps.secret, email);
  const now = deps.now();
  const last = await deps.store.current(eHash);
  if (last) {
    const waited = (now.getTime() - last.sentAt.getTime()) / 1000;
    if (waited < deps.rules.resend_after_seconds) {
      return {
        ok: false,
        error: "too_soon",
        resendInSeconds: Math.ceil(deps.rules.resend_after_seconds - waited),
      };
    }
  }
  if (!(await issueAndMail(deps, email, eHash, user))) return { ok: false, error: "rate_limited" };
  return {
    ok: true,
    sentTo: email,
    validMinutes: deps.rules.code_valid_minutes,
    resendInSeconds: deps.rules.resend_after_seconds,
  };
}

/** POST /auth/code/verify. */
export async function verifyCode(deps: CodeDeps, rawEmail: string, rawCode: string): Promise<VerifyResult> {
  const email = rawEmail.trim().toLowerCase();
  if (!isWorkEmail(email, deps.domains)) return { ok: false, error: "not_work_email" };
  const code = rawCode.trim();
  const eHash = emailHash(deps.secret, email);
  const now = deps.now();

  const runOut = async (): Promise<VerifyResult> => {
    const user = await deps.findUser(email);
    if (user && !user.active) return { ok: false, error: "account_disabled" };
    return (await issueAndMail(deps, email, eHash, user))
      ? { ok: false, error: "code_expired", resent: true }
      : { ok: false, error: "rate_limited" };
  };

  const row = await deps.store.current(eHash);
  if (!row || row.expiresAt <= now || row.triesLeft <= 0) return runOut();
  const left = await deps.store.spendTry(row.id, now);
  if (left === null) return runOut();

  const shaped = new RegExp(`^\\d{${deps.rules.code_digits}}$`).test(code);
  if (shaped && sameHash(row.codeHash, codeHash(deps.secret, eHash, code))) {
    if (!(await deps.store.use(row.id, now))) return runOut();
    const user = await deps.findUser(email);
    if (!user || !user.active) return { ok: false, error: "account_disabled" };
    return { ok: true, userId: user.id };
  }
  if (left > 0) return { ok: false, error: "wrong_code", triesLeft: left };
  return runOut();
}

// ---- stores ---------------------------------------------------------------------------------------------------

export class MemoryCodeStore implements CodeStore {
  rows: CodeRow[] = [];
  private seq = 0;

  async current(eHash: string) {
    const live = this.rows.filter((r) => r.emailHash === eHash && !r.supersededAt);
    return live.length ? { ...live[live.length - 1]! } : null;
  }

  async issue(row: Omit<CodeRow, "id" | "supersededAt">) {
    for (const r of this.rows)
      if (r.emailHash === row.emailHash && !r.supersededAt) r.supersededAt = row.sentAt;
    this.rows.push({ ...row, id: String(++this.seq), supersededAt: null });
  }

  async spendTry(id: string, now: Date) {
    const r = this.rows.find((x) => x.id === id);
    if (!r || r.supersededAt || r.expiresAt <= now || r.triesLeft <= 0) return null;
    r.triesLeft -= 1;
    return r.triesLeft;
  }

  async use(id: string, now: Date) {
    const r = this.rows.find((x) => x.id === id);
    if (!r || r.supersededAt) return false;
    r.supersededAt = now;
    return true;
  }

  async sentSince(eHash: string, since: Date) {
    return this.rows.filter((r) => r.emailHash === eHash && r.sentAt >= since).length;
  }
}

/**
 * `sign_in_codes` (lane E's cut-over, 20261121500100): id (bigint identity), email_hash, code_hash, expires_at,
 * tries_left, sent_at, superseded_at. Raw SQL so this file does not depend on generated types before the table is
 * on `main`.
 */
export class PgCodeStore implements CodeStore {
  async current(eHash: string) {
    const r = await sql<{
      id: string;
      code_hash: string;
      expires_at: Date;
      tries_left: number;
      sent_at: Date;
    }>`
      SELECT id::text AS id, code_hash, expires_at, tries_left, sent_at FROM sign_in_codes
      WHERE email_hash = ${eHash} AND superseded_at IS NULL
      ORDER BY sent_at DESC LIMIT 1
    `.execute(getDb());
    const row = r.rows[0];
    return row
      ? {
          id: row.id,
          emailHash: eHash,
          codeHash: row.code_hash,
          expiresAt: new Date(row.expires_at),
          triesLeft: row.tries_left,
          sentAt: new Date(row.sent_at),
          supersededAt: null,
        }
      : null;
  }

  async issue(row: Omit<CodeRow, "id" | "supersededAt">) {
    await getDb()
      .transaction()
      .execute(async (trx) => {
        await sql`
          UPDATE sign_in_codes SET superseded_at = ${row.sentAt}
          WHERE email_hash = ${row.emailHash} AND superseded_at IS NULL
        `.execute(trx);
        await sql`
          INSERT INTO sign_in_codes (email_hash, code_hash, expires_at, tries_left, sent_at)
          VALUES (${row.emailHash}, ${row.codeHash}, ${row.expiresAt}, ${row.triesLeft}, ${row.sentAt})
        `.execute(trx);
      });
  }

  async spendTry(id: string, now: Date) {
    const r = await sql<{ tries_left: number }>`
      UPDATE sign_in_codes SET tries_left = tries_left - 1
      WHERE id = ${id}::bigint AND superseded_at IS NULL AND expires_at > ${now} AND tries_left > 0
      RETURNING tries_left
    `.execute(getDb());
    return r.rows[0] ? r.rows[0].tries_left : null;
  }

  async use(id: string, now: Date) {
    const r = await sql`
      UPDATE sign_in_codes SET superseded_at = ${now} WHERE id = ${id}::bigint AND superseded_at IS NULL
      RETURNING 1
    `.execute(getDb());
    return r.rows.length === 1;
  }

  async sentSince(eHash: string, since: Date) {
    const r = await sql<{ n: string }>`
      SELECT count(*)::text AS n FROM sign_in_codes WHERE email_hash = ${eHash} AND sent_at >= ${since}
    `.execute(getDb());
    return Number(r.rows[0]?.n ?? 0);
  }
}

let store: CodeStore | undefined;

/** The table; in process memory while the table is missing (before the cut-over, BLD-A173). */
export function codeStore(): CodeStore {
  store ??= withTableFallback<CodeStore>("sign_in_codes", new PgCodeStore(), new MemoryCodeStore());
  return store;
}
