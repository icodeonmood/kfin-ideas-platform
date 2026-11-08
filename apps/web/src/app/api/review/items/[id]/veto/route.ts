import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { vetoItem } from "@/server/review";

/** POST /api/review/items/{id}/veto — {reason}: a core committee member takes the item back (5 working days). */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("veto_desk_decision");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await vetoItem(me, (await params).id, await request.json().catch(() => null)));
  } catch (err) {
    return asResponse(err);
  }
}
