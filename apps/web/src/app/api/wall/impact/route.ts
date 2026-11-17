import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { wallImpact } from "@/server/wall";

/** GET /api/wall/impact — the four totals, their tiles and the live fixes (A-API.wall, L-IMPACT). */
export async function GET() {
  const me = await authorize("see_org_ideas");
  if (me instanceof NextResponse) return me;
  return wallImpact();
}
