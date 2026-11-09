import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { myTeam } from "@/server/ones";

/** GET /api/me/team — A manager's direct reports: counts only (DEC-079). */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await myTeam(me));
  } catch (err) {
    return asResponse(err);
  }
}
