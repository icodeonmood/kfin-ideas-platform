/**
 * The live wiring for sign-in by email code (L-AUTH.rules/2-3): rules from rules/promises.md, the address check,
 * the account lookup, the worker's mail path, the session, and the kept intent. Off behind `auth.email_code` until
 * InfoSec approves it (BLD-E002); the proxy refuses both routes while it is off, and so does each route.
 */
import { NextResponse, type NextRequest } from "next/server";
import { sql } from "kysely";

import { privacyNoticeVersion, sessionSecret } from "../config";
import { getDb } from "../db";
import { isOn, switchStates } from "../killswitch";
import { promises } from "../promises";
import { workerFetch } from "../worker";
import { allowedDomains, codeStore, type CodeDeps } from "./codes";
import { ATTEMPT_COOKIE, attemptCookieOptions, attemptKeyHash, destination, intentStore } from "./intents";
import { cookieOptions, createSession, secureCookies, sessionTtlSeconds, SESSION_COOKIE } from "./session";

export const EMAIL_CODE_SWITCH = "auth.email_code";

/** Whether the email route may show and run. Unknown or unreadable counts as off (fail closed, §7.6). */
export async function emailCodeOn(): Promise<boolean> {
  try {
    return isOn(await switchStates(), EMAIL_CODE_SWITCH);
  } catch {
    return false;
  }
}

export class MailFailed extends Error {}

export async function liveCodeDeps(): Promise<CodeDeps> {
  return {
    store: codeStore(),
    rules: (await promises()).sign_in,
    secret: sessionSecret(),
    domains: allowedDomains(),
    now: () => new Date(),
    findUser: async (email) => {
      const r = await sql<{ id: string; active: boolean }>`
        SELECT id, active FROM users WHERE lower(email) = ${email} ORDER BY active DESC LIMIT 1
      `.execute(getDb());
      return r.rows[0] ?? null;
    },
    mail: async (userId, code, validMinutes) => {
      const res = await workerFetch("/internal/auth/code-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, code, valid_minutes: validMinutes }),
      });
      if (!res.ok) throw new MailFailed(String(res.status));
    },
  };
}

/** Starts the session for a verified person and sends them where their attempt was going. */
export async function signedInResponse(request: NextRequest, userId: string): Promise<NextResponse> {
  const ttl = await sessionTtlSeconds();
  const token = await createSession(userId, ttl);
  const key = request.cookies.get(ATTEMPT_COOKIE)?.value;
  const intent = key && key.length <= 128 ? await intentStore().use(attemptKeyHash(key), new Date()) : null;
  const to = destination(intent);
  const accepted = await getDb()
    .selectFrom("privacy_acceptances")
    .select("user_id")
    .where("user_id", "=", userId)
    .where("notice_version", "=", privacyNoticeVersion())
    .executeTakeFirst();
  const response = NextResponse.json(
    { signed_in: true, to: accepted ? to : `/privacy-notice?next=${encodeURIComponent(to)}` },
    { headers: { "Cache-Control": "no-store" } },
  );
  response.cookies.set(SESSION_COOKIE, token, cookieOptions(ttl));
  response.cookies.set(ATTEMPT_COOKIE, "", attemptCookieOptions(secureCookies(), 0));
  return response;
}
