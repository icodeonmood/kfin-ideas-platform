import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { officeScreen } from "@/server/display";
import { asResponse } from "@/server/http";

/** GET /api/display/office — the Ones the office screen rotates through, for the display role (S-OFFICE, L-DISPLAY). */
export async function GET() {
  const auth = await authorize("open_display");
  if (auth instanceof NextResponse) return auth;
  try {
    return NextResponse.json(await officeScreen(), { headers: { "Cache-Control": "no-store" } });
  } catch (err) {
    return asResponse(err);
  }
}
