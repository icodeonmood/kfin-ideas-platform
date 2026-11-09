import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse, readJson } from "@/server/http";
import { setScreenMode } from "@/server/ones";

/** PUT /api/ones/screen-mode — Static sky or ambient mode on the office screens (DEC-069). */
export async function PUT(request: NextRequest) {
  const me = await authorize("carry_out_ones");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await setScreenMode(me, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
