import { NextResponse, type NextRequest } from "next/server";

import { cookieOptions, revokeSession, SESSION_COOKIE } from "@/server/auth/session";

/** POST /auth/sign-out (A-API.auth) → 204. The shell's form keeps using /auth/logout, which redirects. */
export async function POST(request: NextRequest) {
  await revokeSession(request.cookies.get(SESSION_COOKIE)?.value);
  const response = new NextResponse(null, { status: 204 });
  response.cookies.set(SESSION_COOKIE, "", cookieOptions(0));
  return response;
}
