import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { voiceStreamStatus } from "@/server/voice-stream";

/** GET /api/drafts/{id}/voice/{stream} → the note's state for the sharer (polling: `A-API.events` does not exist
 * yet). Live: the words so far. Done: their words and the English copy, until the draft takes it as a message. */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string; stream: string }> },
) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const { id, stream } = await params;
  try {
    return NextResponse.json(await voiceStreamStatus(me, id, stream));
  } catch (err) {
    return asResponse(err);
  }
}
