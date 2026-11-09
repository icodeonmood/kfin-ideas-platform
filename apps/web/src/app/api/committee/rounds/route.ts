import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { rounds } from "@/server/committee";
import { asResponse } from "@/server/http";

/** GET /api/committee/rounds — the reviews this person sits on (§4.6). */
export async function GET() {
  const me = await authorize("score");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await rounds(me), { headers: { "Cache-Control": "no-store" } });
  } catch (err) {
    return asResponse(err);
  }
}
