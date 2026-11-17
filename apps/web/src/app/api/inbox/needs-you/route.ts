import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { needsYou } from "@/server/inbox";

/** GET /api/inbox/needs-you: Home's "Needs you", the total and the top two, soonest due first (A-API.home). */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  return NextResponse.json(await needsYou(me), { headers: { "Cache-Control": "no-store" } });
}
