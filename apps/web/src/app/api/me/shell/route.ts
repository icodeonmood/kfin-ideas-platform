import { NextResponse } from "next/server";

import { currentUser } from "@/server/auth/current";
import { shellData } from "@/server/shell";

export const dynamic = "force-dynamic";

/**
 * GET /api/me/shell: what the shell shows around every screen (initials, tier, unread Inbox count, drafts, ideas).
 * The root layout renders it once; the shell asks again after each navigation so the counts stay the same
 * everywhere (C-SIDEBAR.rules/2). The person's own titles only; nothing is logged.
 */
export async function GET() {
  const me = await currentUser();
  if (!me || !me.privacyAccepted) return NextResponse.json({ error: "sign_in_required" }, { status: 401 });
  return NextResponse.json(await shellData(me), { headers: { "Cache-Control": "no-store" } });
}
