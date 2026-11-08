import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { wall } from "@/server/ideas";

/** GET /api/ideas — recent ideas everyone may see (the wall's first list; empty while `wall.public` is off). */
export async function GET() {
  const me = await authorize("see_org_ideas");
  if (me instanceof NextResponse) return me;
  try {
    const w = await wall();
    return NextResponse.json(
      { ideas: w.paused ? [] : w.recent },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch (err) {
    return asResponse(err);
  }
}
