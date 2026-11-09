import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { emberReady } from "@/server/ember";
import { asResponse } from "@/server/http";

/** POST /api/ember/{id}/ready — The core committee chair approves the note; the issue is then ready for an admin
 * who did not write it to send (BLD-134). The worker refuses anyone but the chair. */
export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("write_ember_note");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await emberReady(me, (await params).id));
  } catch (err) {
    return asResponse(err);
  }
}
