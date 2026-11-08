import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { act } from "@/server/review";

/** POST /api/review/items/{id}/action — decide, redirect, ask, visibility, hold or confirm_hold (§4.3). */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("work_review_queue");
  if (me instanceof NextResponse) return me;
  const body = await request.json().catch(() => null);
  try {
    return NextResponse.json(await act(me, (await params).id, body));
  } catch (err) {
    return asResponse(err);
  }
}
