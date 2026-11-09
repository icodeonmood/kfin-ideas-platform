import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { draftPack } from "@/server/delivery";
import { asResponse } from "@/server/http";

/** POST /api/delivery/{id}/pack-draft — the assistant proposes the handover pack's fields from the picked idea or
 * group. Nothing is saved: the person edits the draft and saves the pack as usual (BLD-138). */
export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("work_delivery");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await draftPack(me, (await params).id));
  } catch (err) {
    return asResponse(err);
  }
}
