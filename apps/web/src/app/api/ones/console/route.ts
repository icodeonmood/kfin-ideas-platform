import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { onesConsole } from "@/server/ones";

/** GET /api/ones/console — The committee console's Ones module (DEC-040). */
export async function GET() {
  const auth = await authorize("view_ones_console");
  if (auth instanceof NextResponse) return auth;
  try {
    return NextResponse.json(await onesConsole());
  } catch (err) {
    return asResponse(err);
  }
}
