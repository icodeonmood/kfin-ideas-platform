import { NextResponse, type NextRequest } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { inboxFor, isTab } from "@/server/inbox";

/** GET /api/inbox?tab=all|needs_you|unread|archived (A-API.inbox): the tab's items, newest first, every tab's count
 * and the unread total. Items are grouped by the client (L-INBOX.rules/4). */
export async function GET(request: NextRequest) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  const tab = request.nextUrl.searchParams.get("tab") ?? "all";
  if (!isTab(tab))
    return NextResponse.json({ error: { code: "bad_tab", message: "No such tab." } }, { status: 400 });
  return NextResponse.json(await inboxFor(me, tab), { headers: { "Cache-Control": "no-store" } });
}
