import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { justIn, wallQuery } from "@/server/wall";

/**
 * GET /api/wall/just-in?kind=&sort=popular|newest|crew|ones&limit=&offset= — ideas with the review desk, one sort
 * at a time, five a page on desktop and three on the phone (A-API.wall, L-WALL.justin).
 */
export async function GET(request: NextRequest) {
  const me = await authorize("see_org_ideas");
  if (me instanceof NextResponse) return me;
  const q = wallQuery(request.nextUrl.searchParams, ["kind", "sort", "limit", "offset"]);
  return q instanceof NextResponse ? q : justIn(q);
}
