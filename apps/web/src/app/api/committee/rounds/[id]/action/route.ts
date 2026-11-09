import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { roundAct } from "@/server/committee";
import { asResponse } from "@/server/http";

/** POST /api/committee/rounds/{id}/action — score, revise, declare a conflict, reveal, decide (§4.6). */

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("score");
  if (me instanceof NextResponse) return me;
  const body = ((await request.json().catch(() => null)) ?? {}) as Record<string, unknown>;
  try {
    return NextResponse.json(await roundAct(me, (await params).id, body));
  } catch (err) {
    return asResponse(err);
  }
}
