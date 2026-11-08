import { NextResponse, type NextRequest } from "next/server";

import { appBaseUrl } from "@/server/config";
import { authorizationUrl, OidcError, randomToken } from "@/server/auth/oidc";
import { cookieOptions, safeNext, sealTx, TX_COOKIE, TX_TTL_SECONDS } from "@/server/auth/session";
import { log } from "@/server/log";

export const dynamic = "force-dynamic";

/** GET /auth/login — start the authorisation-code flow with PKCE (§3.1, §8). */
export async function GET(request: NextRequest) {
  const tx = {
    state: randomToken(),
    nonce: randomToken(),
    verifier: randomToken(48),
    next: safeNext(request.nextUrl.searchParams.get("next")),
    iat: Math.floor(Date.now() / 1000),
  };
  try {
    const response = NextResponse.redirect(await authorizationUrl(tx));
    response.cookies.set(TX_COOKIE, sealTx(tx), { ...cookieOptions(TX_TTL_SECONDS), path: "/auth" });
    return response;
  } catch (err) {
    log.error("auth.login_failed", { error_code: err instanceof OidcError ? err.code : "unexpected" });
    return NextResponse.redirect(new URL("/sign-in?error=idp_unavailable", appBaseUrl()));
  }
}
