import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { leaderboard } from "@/server/ones";

/** GET /api/ones/leaderboard — Ones only (DEC-077): people by tier then measured impact, and teams. */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  try {
    const board = await leaderboard(me);
    return board ? NextResponse.json(board) : NextResponse.json({ error: "ones_only" }, { status: 403 });
  } catch (err) {
    return asResponse(err);
  }
}
