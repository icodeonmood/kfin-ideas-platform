import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { emberCurrent } from "@/server/ember";
import { asResponse } from "@/server/http";

/** GET /api/ember/current — The newest draft, for the chair and admins (BLD-128). */
export async function GET() {
  const me = await authorize("write_ember_note");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await emberCurrent(me));
  } catch (err) {
    return asResponse(err);
  }
}
