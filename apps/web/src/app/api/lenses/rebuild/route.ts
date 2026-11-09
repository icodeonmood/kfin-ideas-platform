import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { rebuildLenses } from "@/server/delivery";
import { asResponse } from "@/server/http";

/** POST /api/lenses/rebuild — Rebuild the lenses now instead of waiting for Monday. */
export async function POST() {
  const me = await authorize("review_learning");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await rebuildLenses(me));
  } catch (err) {
    return asResponse(err);
  }
}
