import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { presentationCommitteeAct } from "@/server/committee";
import { asResponse } from "@/server/http";

/** POST /api/committee/presentations/{id}/action — session, sealed assessment, collation, decision (§4.7). */

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("decide");
  if (me instanceof NextResponse) return me;
  const body = ((await request.json().catch(() => null)) ?? {}) as Record<string, unknown>;
  try {
    return NextResponse.json(await presentationCommitteeAct(me, (await params).id, body));
  } catch (err) {
    return asResponse(err);
  }
}
