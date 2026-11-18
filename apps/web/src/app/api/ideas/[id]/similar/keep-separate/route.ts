import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse, readJson } from "@/server/http";
import { keepSeparate } from "@/server/similar";

/** POST /api/ideas/{row ID}/similar/keep-separate { on?: boolean } — "Keep mine separate" on Check it, recorded for
 * the reviewer (L-SIMILAR.rules/8, C-SIMGRID.grid/4); `on: false` is "Show them again". The sharer's own unsent
 * draft only (BLD-C095). Behind `submissions`. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const body = await readJson(request);
  if (body.on !== undefined && typeof body.on !== "boolean")
    return NextResponse.json({ error: "bad_request", field: "on" }, { status: 400 });
  try {
    return NextResponse.json(await keepSeparate(me, (await params).id, body.on !== false));
  } catch (err) {
    return asResponse(err);
  }
}
