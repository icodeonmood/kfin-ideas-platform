import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { emberArchive } from "@/server/ember";
import { asResponse } from "@/server/http";

/** GET /api/ember — Every issue of The Ember that has gone out (BLD-128). */
export async function GET() {
  const me = await authorize("signed_in");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await emberArchive());
  } catch (err) {
    return asResponse(err);
  }
}
