import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { oneDashboard } from "@/server/wall";

/**
 * GET /api/one — the signed-in One's dashboard: card, idea, impact, number window, brief and any tier moment
 * (A-API.wall, S-ONE). Anyone else gets 403 `not_a_one` and the page sends them to Profile (S-ONE.rules/1).
 */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  return oneDashboard(me);
}
