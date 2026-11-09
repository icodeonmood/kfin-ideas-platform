import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { proposalView } from "@/server/clusters";
import { asResponse } from "@/server/http";

/** GET /api/review/cluster-proposals/{id} — one cluster proposal as this viewer may see it (§4.4 B step 8). */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("view_review_queue");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await proposalView(me, (await params).id), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (err) {
    return asResponse(err);
  }
}
