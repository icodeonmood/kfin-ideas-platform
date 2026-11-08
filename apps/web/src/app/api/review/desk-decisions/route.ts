import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { deskDecisions } from "@/server/review";

/** GET /api/review/desk-decisions — everything the desk decided, with veto windows, and open disagreements. */
export async function GET() {
  const me = await authorize("view_review_queue");
  if (me instanceof NextResponse) return me;
  return NextResponse.json(await deskDecisions(), { headers: { "Cache-Control": "no-store" } });
}
