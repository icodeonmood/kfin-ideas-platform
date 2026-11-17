import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { wallEmber } from "@/server/wall";

/** GET /api/wall/ember — the latest issue and the next as "Coming soon" (A-API.wall, L-WALL.ember). */
export async function GET() {
  const me = await authorize("see_org_ideas");
  if (me instanceof NextResponse) return me;
  return wallEmber();
}
