/**
 * Sessions (§3.1 step 3, AT-B2-05; L-AUTH.rules/5): an HttpOnly, Secure, SameSite=Lax cookie. A session lasts
 * `session.hours` from rules/promises.md (8, KFintech policy) from sign-in, and activity never extends it past that
 * (BLD-A178); "KFintech apps sign everyone out after 8 hours" is then true. The cookie carries a random token; the
 * database keeps only its SHA-256, so a leaked table cannot be replayed. Sign-out revokes the row.
 */
import { createHash, createHmac, randomBytes, timingSafeEqual } from "node:crypto";

import { sql } from "kysely";

import { appBaseUrl, isProductionLike, privacyNoticeVersion, sessionSecret } from "../config";
import { getDb } from "../db";
import { log } from "../log";
import { promises } from "../promises";

export const SESSION_COOKIE = "ideas_session";
/** KFintech policy, 8 hours: used only when rules/promises.md cannot be read (`sessionTtlSeconds`). */
export const SESSION_TTL_SECONDS = 8 * 60 * 60;
/** How often activity is recorded (`last_seen_at`); it never moves the end of the session. */
const REFRESH_AFTER_MS = 5 * 60 * 1000;

/**
 * Secure everywhere that matters: UAT and production always, and any HTTPS address. Only the plain-HTTP dev and
 * test stack on localhost drops the flag, because Safari refuses Secure cookies over http://localhost, which left
 * the sign-in state cookie behind and sent every Safari sign-in back to the start (BLD-153).
 */
export const secureCookies = () => isProductionLike() || appBaseUrl().protocol === "https:";

export const cookieOptions = (maxAge = SESSION_TTL_SECONDS) => ({
  httpOnly: true,
  secure: secureCookies(),
  sameSite: "lax" as const,
  path: "/",
  maxAge,
});

const hashToken = (token: string) => createHash("sha256").update(token, "utf8").digest();

export type SessionInfo = {
  userId: string;
  active: boolean;
  privacyAccepted: boolean;
  grants: Array<{ role: string; scope_id: string | null }>;
  needsRefresh: boolean;
};

/** After the worker fails to answer, how long every request uses the policy's 8 hours before asking again. */
const PROMISES_RETRY_MS = 60_000;
let promisesFailedAt = 0;

/**
 * Session length from P-PRODUCT.promises `session.hours` (rules/promises.md, BLD-A181; L-AUTH.rules/5). Every request
 * asks (readSession), so `promises()` answers from its one-minute cache. If the worker cannot be read, the policy's
 * 8 hours, with one warning, and the worker is not asked again for a minute: a worker that hangs must not hold up
 * every page by its timeout (BLD-A178).
 */
export async function sessionTtlSeconds(): Promise<number> {
  if (Date.now() - promisesFailedAt < PROMISES_RETRY_MS) return SESSION_TTL_SECONDS;
  try {
    const hours = (await promises()).session.hours;
    if (Number.isFinite(hours) && hours > 0) return Math.round(hours * 3600);
  } catch {
    promisesFailedAt = Date.now();
    log.warn("auth.promises_unavailable");
  }
  return SESSION_TTL_SECONDS;
}

export async function createSession(userId: string, ttlSeconds = SESSION_TTL_SECONDS): Promise<string> {
  const token = randomBytes(32).toString("base64url");
  await getDb()
    .insertInto("sessions")
    .values({
      id_hash: hashToken(token),
      user_id: userId,
      expires_at: new Date(Date.now() + ttlSeconds * 1000),
    })
    .execute();
  return token;
}

/**
 * One query: the session, the person, their live role grants and the current privacy notice. A session older than
 * `session.hours` is over, whatever its `expires_at` says (L-AUTH.rules/5).
 */
export async function readSession(token: string | undefined): Promise<SessionInfo | null> {
  if (!token || token.length > 128) return null;
  const ttl = await sessionTtlSeconds();
  const row = await sql<{
    user_id: string;
    active: boolean;
    last_seen_at: Date;
    privacy_ok: boolean;
    grants: Array<{ role: string; scope_id: string | null }>;
  }>`
    SELECT s.user_id, u.active, s.last_seen_at,
           EXISTS (SELECT 1 FROM privacy_acceptances p
                   WHERE p.user_id = u.id AND p.notice_version = ${privacyNoticeVersion()}) AS privacy_ok,
           COALESCE((SELECT json_agg(json_build_object('role', g.role, 'scope_id', g.scope_id))
                     FROM role_grants g
                     WHERE g.user_id = u.id AND g.valid_from <= now()
                       AND (g.valid_to IS NULL OR g.valid_to > now())), '[]'::json) AS grants
    FROM sessions s JOIN users u ON u.id = s.user_id
    WHERE s.id_hash = ${hashToken(token)} AND s.revoked_at IS NULL AND s.expires_at > now()
      AND s.created_at > now() - make_interval(secs => ${ttl})
  `.execute(getDb());
  const r = row.rows[0];
  if (!r || !r.active) return null;
  return {
    userId: r.user_id,
    active: r.active,
    privacyAccepted: r.privacy_ok,
    grants: r.grants,
    needsRefresh: Date.now() - new Date(r.last_seen_at).getTime() > REFRESH_AFTER_MS,
  };
}

/**
 * Records activity. The end stays `session.hours` after sign-in: never later, even for someone working all day
 * (L-AUTH.rules/5, BLD-A178), and it follows a change to `session.hours`. The cookie's own lifetime may run on past
 * the end (the proxy renews it with activity): the server refuses it at the end all the same, and a cookie still
 * held after the end is what lets S-02 show "Session expired mid-draft" (`expiredSession`).
 */
export async function refreshSession(token: string, ttlSeconds = SESSION_TTL_SECONDS): Promise<void> {
  await getDb()
    .updateTable("sessions")
    .set({
      last_seen_at: new Date(),
      expires_at: sql<Date>`created_at + make_interval(secs => ${ttlSeconds})`,
    })
    .where("id_hash", "=", hashToken(token))
    .where("revoked_at", "is", null)
    .execute();
}

/**
 * A session that ran out (time, not signing out) within the last day, for S-02's "Session expired mid-draft"
 * (L-AUTH.states, A-API.auth `GET /auth/session` → `expired`). Only the browser holding the cookie can ask, and a
 * signed-out session never counts, so a shared laptop shows nothing after "Sign out".
 */
export async function expiredSession(
  token: string | undefined,
): Promise<{ userId: string; email: string } | null> {
  if (!token || token.length > 128) return null;
  const ttl = await sessionTtlSeconds();
  const r = await sql<{ user_id: string; email: string }>`
    SELECT s.user_id, u.email FROM sessions s JOIN users u ON u.id = s.user_id
    WHERE s.id_hash = ${hashToken(token)} AND s.revoked_at IS NULL AND u.active
      AND (s.expires_at <= now() OR s.created_at <= now() - make_interval(secs => ${ttl}))
      AND LEAST(s.expires_at, s.created_at + make_interval(secs => ${ttl})) > now() - interval '1 day'
  `.execute(getDb());
  const row = r.rows[0];
  return row ? { userId: row.user_id, email: row.email } : null;
}

export async function revokeSession(token: string | undefined): Promise<void> {
  if (!token) return;
  await getDb()
    .updateTable("sessions")
    .set({ revoked_at: new Date() })
    .where("id_hash", "=", hashToken(token))
    .execute();
}

// ---- the short-lived sign-in transaction (state, nonce, PKCE verifier, where to go next) ------------------

export const TX_COOKIE = "ideas_oidc";
export const TX_TTL_SECONDS = 10 * 60;
/**
 * The OIDC transaction. Where the person was going is kept on the server against the attempt (`intents.ts`,
 * L-AUTH.rules/4); `next` carries the same place for when no row was kept (nowhere in particular, or over the write
 * limit, BLD-A177). `attempt` is the attempt key's hash: the callback signs in only the browser that holds the same
 * attempt cookie (login CSRF). `silent` marks a `prompt=none` try, whose "not signed in at the provider" answer is
 * not a failure (L-AUTH.rules/1).
 */
export type SignInTx = {
  state: string;
  nonce: string;
  verifier: string;
  silent?: boolean;
  next?: string;
  attempt?: string;
  iat: number;
};

/** Equal strings, compared in constant time (state, attempt hashes). Unequal lengths are simply unequal. */
export function sameSecret(a: string | null | undefined, b: string | null | undefined): boolean {
  if (typeof a !== "string" || typeof b !== "string") return false;
  const x = Buffer.from(a, "utf8");
  const y = Buffer.from(b, "utf8");
  return x.length === y.length && timingSafeEqual(x, y);
}

const sign = (payload: string) => createHmac("sha256", sessionSecret()).update(payload).digest("base64url");

export function sealTx(tx: SignInTx): string {
  const payload = Buffer.from(JSON.stringify(tx)).toString("base64url");
  return `${payload}.${sign(payload)}`;
}

export function openTx(value: string | undefined): SignInTx | null {
  if (!value) return null;
  const [payload, mac] = value.split(".");
  if (!payload || !mac) return null;
  const expected = Buffer.from(sign(payload));
  const given = Buffer.from(mac);
  if (expected.length !== given.length || !timingSafeEqual(expected, given)) return null;
  const tx = JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as SignInTx;
  return Date.now() / 1000 - tx.iat > TX_TTL_SECONDS ? null : tx;
}

/**
 * Only same-site relative paths, so `next` cannot send anyone to another site after sign-in. Control characters
 * and whitespace are refused before parsing, because the URL parser strips tabs and newlines ("/\t/evil" would
 * otherwise become "//evil"). The parsed path is returned, never the raw string.
 */
export function safeNext(next: string | null | undefined): string {
  if (!next || next.length > 512 || !next.startsWith("/") || next.startsWith("//")) return "/";
  if (/[\u0000-\u0020\u007f\\]/.test(next)) return "/";
  const base = "http://same-site.invalid";
  let url: URL;
  try {
    url = new URL(next, base);
  } catch {
    return "/";
  }
  if (url.origin !== base || url.pathname.startsWith("//")) return "/";
  return url.pathname + url.search + url.hash;
}
