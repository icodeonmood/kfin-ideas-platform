import { NextResponse, type NextRequest } from "next/server";

import { appBaseUrl, privacyNoticeVersion } from "@/server/config";
import { getDb } from "@/server/db";
import {
  ATTEMPT_COOKIE,
  attemptCookieOptions,
  attemptKeyHash,
  destination,
  intentStore,
} from "@/server/auth/intents";
import { exchangeCode, OidcError } from "@/server/auth/oidc";
import {
  cookieOptions,
  createSession,
  openTx,
  secureCookies,
  sessionTtlSeconds,
  SESSION_COOKIE,
  TX_COOKIE,
} from "@/server/auth/session";
import { callbackErrorOutcome, failurePath, logFailure } from "@/server/auth/sso";
import { SignInRefused, userFromClaims } from "@/server/auth/users";
import { log } from "@/server/log";

export const dynamic = "force-dynamic";

function go(path: string) {
  const response = NextResponse.redirect(new URL(path, appBaseUrl()));
  response.cookies.set(TX_COOKIE, "", { ...cookieOptions(0), path: "/auth" });
  return response;
}

/**
 * GET /auth/callback — finish single sign-on: check state, exchange the code, verify the ID token, start a session
 * (L-AUTH.rules/5: length from rules/promises.md), then go where the attempt said (L-AUTH.rules/4). The attempt
 * cookie is kept on any failure, so "Try again" or the email code still lands in the same place.
 */
export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const tx = openTx(request.cookies.get(TX_COOKIE)?.value);
  const attemptKey = request.cookies.get(ATTEMPT_COOKIE)?.value;
  const attemptHash = attemptKey && attemptKey.length <= 128 ? attemptKeyHash(attemptKey) : undefined;
  const code = params.get("code");
  const error = params.get("error");

  if (error) {
    if (callbackErrorOutcome(error, Boolean(tx?.silent)) === "show_sign_in") {
      log.info("auth.silent_unavailable", attemptHash ? { attempt_id: attemptHash.slice(0, 32) } : {});
      return go("/sign-in");
    }
    return go(failurePath("failed", logFailure("callback", "idp_refused", attemptHash)));
  }
  if (!tx || !code || params.get("state") !== tx.state) {
    return go(failurePath("failed", logFailure("callback", "state_mismatch", attemptHash)));
  }

  try {
    const claims = await exchangeCode(code, tx.verifier, tx.nonce);
    const user = await userFromClaims(claims);
    const ttl = await sessionTtlSeconds();
    const token = await createSession(user.id, ttl);
    const intent = attemptHash ? await intentStore().use(attemptHash, new Date()) : null;
    // A transaction started before intents were kept on the server carries its own `next`.
    const to = intent ? destination(intent) : destination({ to: tx.next ?? "/", draftId: null, step: null });
    const accepted = await getDb()
      .selectFrom("privacy_acceptances")
      .select("user_id")
      .where("user_id", "=", user.id)
      .where("notice_version", "=", privacyNoticeVersion())
      .executeTakeFirst();
    const response = go(accepted ? to : `/privacy-notice?next=${encodeURIComponent(to)}`);
    response.cookies.set(SESSION_COOKIE, token, cookieOptions(ttl));
    response.cookies.set(ATTEMPT_COOKIE, "", attemptCookieOptions(secureCookies(), 0));
    log.info("auth.signed_in", { user_id: user.id, first_sign_in: user.created, route: "sso" });
    return response;
  } catch (err) {
    if (err instanceof SignInRefused) {
      return go(failurePath("refused", logFailure("callback", err.code, attemptHash)));
    }
    const errorCode = err instanceof OidcError ? err.code : "signin_failed";
    return go(failurePath("failed", logFailure("callback", errorCode, attemptHash)));
  }
}
