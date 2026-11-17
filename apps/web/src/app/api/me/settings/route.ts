import { NextResponse, type NextRequest } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { objectBody, saveSettings } from "@/server/wall";

/**
 * PATCH /api/me/settings — any of the switches, each a boolean; saves at once and returns every switch's state
 * (A-API.me, S-H6.rules/1). A failed save answers "Couldn't save that. Try again." naming the switch, so it flips
 * back. Teams stays off until IT approves it (DEC-105).
 */
export async function PATCH(request: NextRequest) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  return saveSettings(me, await objectBody(request));
}
