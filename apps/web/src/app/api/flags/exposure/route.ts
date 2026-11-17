import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { bodyOf } from "@/server/drafts";
import { isFlagKey, logExposure } from "@/server/flags";

/** POST /api/flags/exposure `{ flag, screen }` — the screen that differs for this flag was rendered for the signed-in
 * person, once per page load (P-DECISIONS.experiments, BLD-C173). The server decides the variant and logs it: the
 * client only says what it rendered. Nothing is logged while the flag is off or for a screen the flag does not
 * change. Always `204`: an exposure never fails a page. */
export async function POST(request: Request) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  const body = await bodyOf(request);
  if (isFlagKey(body.flag) && typeof body.screen === "string")
    await logExposure(me.id, body.flag, body.screen);
  return new NextResponse(null, { status: 204, headers: { "Cache-Control": "no-store" } });
}
