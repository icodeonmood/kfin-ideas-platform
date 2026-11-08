/**
 * Sessions (§3.1 step 3, AT-B2-05): an HttpOnly, Secure, SameSite=Lax cookie with an 8-hour lifetime, refreshed
 * on activity. The cookie carries a random token; the database keeps only its SHA-256, so a leaked table cannot
 * be replayed. Sign-out revokes the row.
 */
import { createHash, createHmac, randomBytes, timingSafeEqual } from "node:crypto";

import { sql } from "kysely";

import { privacyNoticeVersion, sessionSecret } from "../config";
import { getDb } from "../db";

export const SESSION_COOKIE = "ideas_session";
export const SESSION_TTL_SECONDS = 8 * 60 * 60;
export const SESSION_ABSOLUTE_HOURS = 12; // sliding refresh never extends a session past a working day
const REFRESH_AFTER_MS = 5 * 60 * 1000;

export const cookieOptions = (maxAge = SESSION_TTL_SECONDS) => ({
  httpOnly: true,
  secure: true,
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

export async function createSession(userId: string): Promise<string> {
  const token = randomBytes(32).toString("base64url");
  await getDb()
    .insertInto("sessions")
    .values({
      id_hash: hashToken(token),
      user_id: userId,
      expires_at: new Date(Date.now() + SESSION_TTL_SECONDS * 1000),
    })
    .execute();
  return token;
}

/** One query: the session, the person, their live role grants and the current privacy notice. */
export async function readSession(token: string | undefined): Promise<SessionInfo | null> {
  if (!token || token.length > 128) return null;
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
      AND s.created_at > now() - make_interval(hours => ${SESSION_ABSOLUTE_HOURS})
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

export async function refreshSession(token: string): Promise<void> {
  await getDb()
    .updateTable("sessions")
    .set({ last_seen_at: new Date(), expires_at: new Date(Date.now() + SESSION_TTL_SECONDS * 1000) })
    .where("id_hash", "=", hashToken(token))
    .where("revoked_at", "is", null)
    .execute();
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
export type SignInTx = { state: string; nonce: string; verifier: string; next: string; iat: number };

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
