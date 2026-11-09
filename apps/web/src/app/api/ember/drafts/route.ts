import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { emberDraft } from "@/server/ember";
import { asResponse, readJson } from "@/server/http";

/** POST /api/ember/drafts — An admin opens the month's draft of The Ember (BLD-128). */
export async function POST(request: NextRequest) {
  const me = await authorize("send_ember");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await emberDraft(me, await readJson(request)), { status: 201 });
  } catch (err) {
    return asResponse(err);
  }
}
