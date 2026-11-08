import { NextResponse, type NextRequest } from "next/server";

import { BANNERS, switchesFor } from "@/lib/killswitch-routes";
import { isOn, switchStates } from "@/server/killswitch";
import { log } from "@/server/log";

/**
 * Runs before every /api request (Next.js proxy, Node.js runtime). Kill switches first (§7.6, non-negotiable 9);
 * authentication and RBAC join here in B2.
 */
export async function proxy(request: NextRequest) {
  const needed = switchesFor(request.method, request.nextUrl.pathname);
  if (needed.length === 0) return NextResponse.next();

  let states;
  try {
    states = await switchStates();
  } catch {
    // Cannot read the switches: refuse the change rather than risk running a killed feature.
    log.error("killswitch.read_failed", { method: request.method });
    return NextResponse.json(
      { error: "unavailable", banner: "Something went wrong on our side. Please try again in a minute." },
      { status: 503, headers: { "Retry-After": "60" } },
    );
  }
  const off = needed.find((name) => !isOn(states, name));
  if (off) {
    return NextResponse.json(
      { error: "paused", switch: off, banner: BANNERS[off] },
      { status: 503, headers: { "Retry-After": "60", "Cache-Control": "no-store" } },
    );
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/api/:path*"],
};
