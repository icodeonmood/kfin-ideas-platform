import { NextResponse, type NextRequest } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { setNameOnWall } from "@/server/ideas";

/** PUT /api/me/comms-prefs — {name_on_wall: boolean}: whether my name may appear on the wall. */
export async function PUT(request: NextRequest) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  const body = (await request.json().catch(() => null)) as { name_on_wall?: unknown } | null;
  try {
    return NextResponse.json(await setNameOnWall(me, body?.name_on_wall));
  } catch (err) {
    return asResponse(err);
  }
}
