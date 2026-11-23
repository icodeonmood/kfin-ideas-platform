import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { answerVoiceStatus } from "@/server/answer-voice";

/** GET /api/questions/{id}/answer/voice/{stream} → the note's state for the question's sharer (polling, as a draft's
 * note polls; BLD-B276). Live: the words so far. Done: their own words. */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string; stream: string }> },
) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const { id, stream } = await params;
  try {
    return NextResponse.json(await answerVoiceStatus(me, id, stream));
  } catch (err) {
    return asResponse(err);
  }
}
