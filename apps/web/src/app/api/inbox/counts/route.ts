import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { inboxCounts } from "@/server/inbox";

/** GET /api/inbox/counts: every tab's count; `unread` is the sidebar and tab-bar number, `needs_you` Home's total
 * (L-INBOX.rules/1). */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  return NextResponse.json(await inboxCounts(me), { headers: { "Cache-Control": "no-store" } });
}
