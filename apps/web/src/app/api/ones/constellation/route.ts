import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { constellation } from "@/server/ones";

/** GET /api/ones/constellation — Every One's spark and the impact cards the office screens alternate with (DEC-069, DEC-074). */
export async function GET() {
  const auth = await authorize("see_org_ideas");
  if (auth instanceof NextResponse) return auth;
  try {
    return NextResponse.json(await constellation());
  } catch (err) {
    return asResponse(err);
  }
}
