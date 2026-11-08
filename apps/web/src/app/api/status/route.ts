import { NextResponse } from "next/server";

import { BANNERS, type SwitchName } from "@/lib/killswitch-routes";
import { switchStates } from "@/server/killswitch";

export const dynamic = "force-dynamic";

/** Which features are paused, with the banner text, so every screen can explain itself. Read-only. */
export async function GET() {
  const states = await switchStates();
  const paused = (Object.keys(BANNERS) as SwitchName[])
    .filter((name) => states.get(name) !== "on")
    .map((name) => ({ switch: name, banner: BANNERS[name] }));
  return NextResponse.json({ paused }, { headers: { "Cache-Control": "no-store" } });
}
