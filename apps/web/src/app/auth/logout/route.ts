import { NextResponse, type NextRequest } from "next/server";

import { appBaseUrl } from "@/server/config";
import { cookieOptions, revokeSession, SESSION_COOKIE } from "@/server/auth/session";

/** POST /auth/logout — revoke the session server-side and clear the cookie. */
export async function POST(request: NextRequest) {
  await revokeSession(request.cookies.get(SESSION_COOKIE)?.value);
  const response = NextResponse.redirect(new URL("/signed-out", appBaseUrl()), 303);
  response.cookies.set(SESSION_COOKIE, "", cookieOptions(0));
  return response;
}
