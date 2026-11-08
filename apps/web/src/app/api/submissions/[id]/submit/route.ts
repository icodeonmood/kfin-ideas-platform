import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse, readJson } from "@/server/http";
import { log } from "@/server/log";
import { submit } from "@/server/submissions";

/** POST /api/submissions/{id}/submit {canvas} — assign IDs, stage scanning, queue the scan (§4.1 step 4). */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const started = performance.now();
  try {
    const result = await submit(me, (await params).id, (await readJson(request)).canvas);
    log.info("submission.submitted", {
      idea_id: result.idea_id,
      strength: result.strength,
      duration_ms: Math.round(performance.now() - started),
    });
    return NextResponse.json(result, { status: 202 });
  } catch (err) {
    return asResponse(err);
  }
}
