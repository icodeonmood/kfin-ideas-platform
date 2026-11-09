import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { lenses } from "@/server/delivery";
import { asResponse } from "@/server/http";

/** GET /api/lenses — The LOB, role and people lenses: counts only (§4.14). */
export async function GET() {
  const me = await authorize("view_lenses");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await lenses(me));
  } catch (err) {
    return asResponse(err);
  }
}
