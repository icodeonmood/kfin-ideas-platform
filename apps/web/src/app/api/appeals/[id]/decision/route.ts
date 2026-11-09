import { NextResponse, type NextRequest } from "next/server";

import { decideAppeal } from "@/server/appeals";
import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";

/** POST /api/appeals/{id}/decision — the panel chair records upheld, back to scoring or overturned (§4.12 step 4). */

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("hear_appeals");
  if (me instanceof NextResponse) return me;
  const body = ((await request.json().catch(() => null)) ?? {}) as Record<string, unknown>;
  try {
    return NextResponse.json(await decideAppeal(me, (await params).id, body));
  } catch (err) {
    return asResponse(err);
  }
}
