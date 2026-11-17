import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { kindling, wallQuery } from "@/server/wall";

/** GET /api/wall/kindling?kind= — Picked, Being built, Shipped with counts and up to three ideas (A-API.wall). */
export async function GET(request: NextRequest) {
  const me = await authorize("see_org_ideas");
  if (me instanceof NextResponse) return me;
  const q = wallQuery(request.nextUrl.searchParams, ["kind"]);
  return q instanceof NextResponse ? q : kindling(q);
}
