import { NextResponse, type NextRequest } from "next/server";

import { asResponse, readJson } from "@/server/http";
import { authorize } from "@/server/auth/authorize";
import { endAnswerVoice } from "@/server/answer-voice";

/** POST /api/questions/{id}/answer/voice/end { stream } → the finished note for the question's sharer: their own
 * words (`text`, `spans`), with no English copy (BLD-B276), or `{ state: "failed", failure }`. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await endAnswerVoice(me, (await params).id, (await readJson(request)).stream));
  } catch (err) {
    return asResponse(err);
  }
}
