import { NextResponse, type NextRequest } from "next/server";

import { appBaseUrl } from "@/server/config";
import { cookieOptions, revokeSession, SESSION_COOKIE } from "@/server/auth/session";

/**
 * POST /auth/logout — revoke the session server-side, clear the cookie, and land on S-01 Landing, the signed-out
 * front door (the separate signed-out page is retired, BLD-A179).
 */
export async function POST(request: NextRequest) {
  await revokeSession(request.cookies.get(SESSION_COOKIE)?.value);
  const response = NextResponse.redirect(new URL("/", appBaseUrl()), 303);
  response.cookies.set(SESSION_COOKIE, "", cookieOptions(0));
  return response;
}
