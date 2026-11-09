import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { myPoints } from "@/server/points";

/** GET /api/me/points — The signed-in person's own points, never anyone else's (DEC-078). */
export async function GET() {
  const me = await authorize("signed_in");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await myPoints(me));
  } catch (err) {
    return asResponse(err);
  }
}
