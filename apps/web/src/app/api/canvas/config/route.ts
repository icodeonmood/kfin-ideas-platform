import { NextResponse } from "next/server";

import { canvasConfig, kfinDomains } from "@/server/canvas-config";

export const dynamic = "force-dynamic";

/** GET /api/canvas/config — limits, the strength rubric and the "what good looks like" examples (§4.1). */
export async function GET() {
  const config = await canvasConfig();
  return NextResponse.json(
    { ...config, kfin_domains: kfinDomains() },
    { headers: { "Cache-Control": "private, max-age=60" } },
  );
}
