import { NextResponse, type NextRequest } from "next/server";

import { appBaseUrl, privacyNoticeVersion } from "@/server/config";
import { getDb } from "@/server/db";
import { exchangeCode, OidcError } from "@/server/auth/oidc";
import { cookieOptions, createSession, openTx, SESSION_COOKIE, TX_COOKIE } from "@/server/auth/session";
import { SignInRefused, userFromClaims } from "@/server/auth/users";
import { log } from "@/server/log";

export const dynamic = "force-dynamic";

function failed(code: string) {
  const response = NextResponse.redirect(new URL(`/sign-in?error=${encodeURIComponent(code)}`, appBaseUrl()));
  response.cookies.set(TX_COOKIE, "", { ...cookieOptions(0), path: "/auth" });
  return response;
}

/** GET /auth/callback — finish sign-in: check state, exchange the code, verify the ID token, start a session. */
export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const tx = openTx(request.cookies.get(TX_COOKIE)?.value);
  const code = params.get("code");
  if (params.get("error")) return failed("idp_refused");
  if (!tx || !code || params.get("state") !== tx.state) return failed("state_mismatch");

  try {
    const claims = await exchangeCode(code, tx.verifier, tx.nonce);
    const user = await userFromClaims(claims);
    const token = await createSession(user.id);
    const accepted = await getDb()
      .selectFrom("privacy_acceptances")
      .select("user_id")
      .where("user_id", "=", user.id)
      .where("notice_version", "=", privacyNoticeVersion())
      .executeTakeFirst();
    const next = accepted ? tx.next : `/privacy-notice?next=${encodeURIComponent(tx.next)}`;
    const response = NextResponse.redirect(new URL(next, appBaseUrl()));
    response.cookies.set(SESSION_COOKIE, token, cookieOptions());
    response.cookies.set(TX_COOKIE, "", { ...cookieOptions(0), path: "/auth" });
    log.info("auth.signed_in", { user_id: user.id, first_sign_in: user.created });
    return response;
  } catch (err) {
    const code = err instanceof OidcError || err instanceof SignInRefused ? err.code : "signin_failed";
    log.error("auth.callback_failed", { error_code: code });
    return failed(code);
  }
}
