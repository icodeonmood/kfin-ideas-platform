import { NextResponse, type NextRequest } from "next/server";

import { appBaseUrl, privacyNoticeVersion } from "@/server/config";
import { getDb } from "@/server/db";
import {
  ATTEMPT_COOKIE,
  attemptCookieOptions,
  attemptKeyHash,
  cleanIntent,
  destination,
  intentStore,
  PLACE_COOKIE,
  placeCookieOptions,
  signInHref,
} from "@/server/auth/intents";
import { exchangeCode, OidcError } from "@/server/auth/oidc";
import {
  cookieOptions,
  createSession,
  openTx,
  sameSecret,
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
 * GET /auth/callback — finish single sign-on: check state (constant time) and that this browser holds the attempt
 * the transaction was started for (login CSRF, BLD-A177), exchange the code, verify the ID token, start a session
 * (L-AUTH.rules/5: length from rules/promises.md), then go where the attempt said (L-AUTH.rules/4). The attempt
 * cookie is kept on any failure, and S-02 is given the transaction's place as `to`, so "Try again" or the email code
 * still lands in the same place even when the write limit kept no row (BLD-A177).
 */
export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const tx = openTx(request.cookies.get(TX_COOKIE)?.value);
  const attemptKey = request.cookies.get(ATTEMPT_COOKIE)?.value;
  const attemptHash = attemptKey && attemptKey.length <= 128 ? attemptKeyHash(attemptKey) : undefined;
  const code = params.get("code");
  const error = params.get("error");
  // Where this browser's transaction was going: a same-site path (cleaned again), handed back to S-02 on any way out.
  const place = tx ? cleanIntent({ to: tx.next }) : null;
  const failed = (kind: "failed" | "refused", errorCode: string) =>
    go(failurePath(kind, logFailure("callback", errorCode, attemptHash), new Date(), place));

  if (error) {
    if (callbackErrorOutcome(error, Boolean(tx?.silent)) === "show_sign_in") {
      log.info("auth.silent_unavailable", attemptHash ? { attempt_id: attemptHash.slice(0, 32) } : {});
      return go(signInHref(place));
    }
    return failed("failed", "idp_refused");
  }
  if (!tx || !code || !sameSecret(params.get("state"), tx.state)) return failed("failed", "state_mismatch");
  if (!sameSecret(attemptHash, tx.attempt)) return failed("failed", "attempt_mismatch");

  try {
    const claims = await exchangeCode(code, tx.verifier, tx.nonce);
    const user = await userFromClaims(claims);
    const ttl = await sessionTtlSeconds();
    const token = await createSession(user.id, ttl);
    const intent = await intentStore().use(attemptHash!, new Date());
    // No row (nowhere in particular, or over the write limit): the sealed transaction carries the place.
    const to = destination(intent ?? place);
    const accepted = await getDb()
      .selectFrom("privacy_acceptances")
      .select("user_id")
      .where("user_id", "=", user.id)
      .where("notice_version", "=", privacyNoticeVersion())
      .executeTakeFirst();
    const response = go(accepted ? to : `/privacy-notice?next=${encodeURIComponent(to)}`);
    response.cookies.set(SESSION_COOKIE, token, cookieOptions(ttl));
    response.cookies.set(ATTEMPT_COOKIE, "", attemptCookieOptions(secureCookies(), 0));
    if (request.cookies.get(PLACE_COOKIE)) {
      response.cookies.set(PLACE_COOKIE, "", placeCookieOptions(secureCookies(), 0));
    }
    log.info("auth.signed_in", { user_id: user.id, first_sign_in: user.created, route: "sso" });
    return response;
  } catch (err) {
    if (err instanceof SignInRefused) return failed("refused", err.code);
    return failed("failed", err instanceof OidcError ? err.code : "signin_failed");
  }
}
