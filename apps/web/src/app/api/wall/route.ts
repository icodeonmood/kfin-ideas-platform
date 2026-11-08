import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { wall } from "@/server/ideas";

/** GET /api/wall — the public wall (§4.13). The proxy answers 503 while `wall.public` is off. */
export async function GET() {
  const me = await authorize("see_org_ideas");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await wall(), { headers: { "Cache-Control": "no-store" } });
  } catch (err) {
    return asResponse(err);
  }
}
