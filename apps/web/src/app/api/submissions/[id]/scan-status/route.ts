import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { scanStatus } from "@/server/scan";

/** GET /api/submissions/{id}/scan-status — the owner's view of the scan: step, outcome, what to do next. */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await scanStatus(me, (await params).id), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (err) {
    return asResponse(err);
  }
}
