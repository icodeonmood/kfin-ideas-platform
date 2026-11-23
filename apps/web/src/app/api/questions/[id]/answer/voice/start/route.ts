import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { startAnswerVoice } from "@/server/answer-voice";

/** POST /api/questions/{id}/answer/voice/start → 201 { id, state: "live", encoding, sample_rate, … }, as a draft's
 * note starts (BLD-B276). The question's sharer only, checked by the worker; anyone else gets 404. Behind
 * capture.voice, speech.hosted and submissions (lib/killswitch-routes.ts). No English copy is made for an answer. */
export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await startAnswerVoice(me, (await params).id), { status: 201 });
  } catch (err) {
    return asResponse(err);
  }
}
