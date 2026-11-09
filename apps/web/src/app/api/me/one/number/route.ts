import { NextResponse, type NextRequest } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { asResponse, readJson } from "@/server/http";
import { swapNumber } from "@/server/ones";

/** POST /api/me/one/number — A One chooses a free number in their first 30 days (DEC-067). */
export async function POST(request: NextRequest) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await swapNumber(me, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
