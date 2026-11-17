import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { wallOnes, wallQuery } from "@/server/wall";

/** GET /api/wall/ones?order=wall|leaderboard — every One as a card; the leaderboard by tier, then hours (A-API.ones). */
export async function GET(request: NextRequest) {
  const me = await authorize("see_org_ideas");
  if (me instanceof NextResponse) return me;
  const q = wallQuery(request.nextUrl.searchParams, ["order"]);
  return q instanceof NextResponse ? q : wallOnes(q);
}
