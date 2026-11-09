import { NextResponse, type NextRequest } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { glowUpSeen } from "@/server/ones";

/** POST /api/me/one/glow-up/{id}/seen — The glow-up has played; it does not play again (DEC-084). */
export async function POST(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await glowUpSeen(me, (await params).id));
  } catch (err) {
    return asResponse(err);
  }
}
