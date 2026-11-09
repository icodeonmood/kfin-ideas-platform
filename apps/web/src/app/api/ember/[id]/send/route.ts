import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { emberSend } from "@/server/ember";
import { asResponse, readJson } from "@/server/http";

/** POST /api/ember/{id}/send — An admin who neither wrote nor approved the note sends a ready issue, with the
 * confirm token from the chair's approval (behind ember.send and ones.public). */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("send_ember");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await emberSend(me, (await params).id, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
