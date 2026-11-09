import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { presentationContributorAct } from "@/server/committee";
import { asResponse } from "@/server/http";

/** POST /api/presentations/{id}/action — accept with presenters and a slot; edit the outline (§4.7). */

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("present");
  if (me instanceof NextResponse) return me;
  const body = ((await request.json().catch(() => null)) ?? {}) as Record<string, unknown>;
  try {
    return NextResponse.json(await presentationContributorAct(me, (await params).id, body));
  } catch (err) {
    return asResponse(err);
  }
}
