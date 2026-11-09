import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { openCycle } from "@/server/committee";
import { asResponse } from "@/server/http";

/** POST /api/committee/cycles — the chair opens this month's cycle (§4.6 step 1). */

export async function POST(request: NextRequest) {
  const me = await authorize("decide");
  if (me instanceof NextResponse) return me;
  const body = ((await request.json().catch(() => null)) ?? {}) as Record<string, unknown>;
  try {
    return NextResponse.json(await openCycle(me, body));
  } catch (err) {
    return asResponse(err);
  }
}
