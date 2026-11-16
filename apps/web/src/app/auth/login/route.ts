import type { NextRequest } from "next/server";

import { startSso } from "@/server/auth/sso";

export const dynamic = "force-dynamic";

/**
 * GET /auth/login?next=… — the older way in, kept for links already sent. It is single sign-on with the place to
 * go kept on the server like every other start (L-AUTH.rules/4), never only in the browser.
 */
export async function GET(request: NextRequest) {
  return startSso(request, { to: request.nextUrl.searchParams.get("next") ?? "/" }, "link");
}
