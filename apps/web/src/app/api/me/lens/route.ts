import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { myLens } from "@/server/points";

/** GET /api/me/lens — The signed-in person's own lens: their ideas and groups, counts only (BLD-135). */
export async function GET() {
  const me = await authorize("signed_in");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await myLens(me));
  } catch (err) {
    return asResponse(err);
  }
}
