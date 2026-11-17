import { NextResponse, type NextRequest } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { objectBody, oneNumber } from "@/server/wall";

/**
 * PUT /api/one/number — {number}: a One swaps to any free number from 1 to 999 inside the 30 days after becoming
 * a One. Errors: `out_of_range`, `taken` with `near`, `window_closed` (A-API.wall, V-FIELDS.one/1–3).
 */
export async function PUT(request: NextRequest) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  return oneNumber(me, await objectBody(request));
}
