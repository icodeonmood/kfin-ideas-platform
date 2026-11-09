import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { announce } from "@/server/ones";

/** POST /api/ones/announce — Tell everyone about the Ones inducted since the last announcement (DEC-056). */
export async function POST() {
  const me = await authorize("carry_out_ones");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await announce(me));
  } catch (err) {
    return asResponse(err);
  }
}
