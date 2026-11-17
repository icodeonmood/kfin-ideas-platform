import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { listFlags } from "@/server/flags";

export const dynamic = "force-dynamic";

/** GET /api/admin/flags — the S1 to S3 experiments with their share, people and exposures (L-AUDIT.flags). */
export async function GET() {
  const me = await authorize("manage_flags");
  if (me instanceof NextResponse) return me;
  return NextResponse.json({ flags: await listFlags() }, { headers: { "Cache-Control": "no-store" } });
}
