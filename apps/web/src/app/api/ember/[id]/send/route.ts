import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { emberSend } from "@/server/ember";
import { asResponse } from "@/server/http";

/** POST /api/ember/{id}/send — An admin sends the issue to everyone (behind ember.send and ones.public). */
export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("send_ember");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await emberSend(me, (await params).id));
  } catch (err) {
    return asResponse(err);
  }
}
