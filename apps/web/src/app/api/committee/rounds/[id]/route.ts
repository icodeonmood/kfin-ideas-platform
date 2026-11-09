import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { roundView } from "@/server/committee";
import { asResponse } from "@/server/http";

/** GET /api/committee/rounds/{id} — one blind review as this member may see it (§4.6). */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("score");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await roundView(me, (await params).id), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (err) {
    return asResponse(err);
  }
}
