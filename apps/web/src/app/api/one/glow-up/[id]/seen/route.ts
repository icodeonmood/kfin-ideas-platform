import { NextResponse, type NextRequest } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { glowUpSeen } from "@/server/wall";

/** POST /api/one/glow-up/{id}/seen — the tier moment has played; it never plays again (S-ONE.rules/3). */
export async function POST(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  return glowUpSeen(me, (await params).id);
}
