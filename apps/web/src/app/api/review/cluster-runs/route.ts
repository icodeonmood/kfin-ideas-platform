import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { runNow, runs } from "@/server/clusters";
import { asResponse } from "@/server/http";

/** GET /api/review/cluster-runs — the latest weekly clustering runs (numbers only, §4.4 B). */
export async function GET() {
  const me = await authorize("view_review_queue");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await runs(), { headers: { "Cache-Control": "no-store" } });
  } catch (err) {
    return asResponse(err);
  }
}

/** POST /api/review/cluster-runs — run the clustering batch now (behind `clusters.batch`). */
export async function POST() {
  const me = await authorize("approve_cluster_proposals");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await runNow(me), { status: 202 });
  } catch (err) {
    return asResponse(err);
  }
}
