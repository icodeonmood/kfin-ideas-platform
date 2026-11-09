import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { act } from "@/server/clusters";
import { asResponse } from "@/server/http";

/** POST /api/review/cluster-proposals/{id}/action — approve (with edits), remove a member, or reject (§4.4 B). */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("approve_cluster_proposals");
  if (me instanceof NextResponse) return me;
  const body = await request.json().catch(() => null);
  try {
    return NextResponse.json(await act(me, (await params).id, body));
  } catch (err) {
    return asResponse(err);
  }
}
