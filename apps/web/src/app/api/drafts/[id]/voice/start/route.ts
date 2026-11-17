import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { startVoice } from "@/server/voice-stream";

/** POST /api/drafts/{id}/voice/start → 201 { id, state: "live", encoding, sample_rate, channels, chunk_seconds,
 * max_chunk_bytes, max_seconds, idle_seconds }. The sharer only; behind capture.voice, speech.hosted and
 * submissions (DEC-108, BLD-C112). */
export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await startVoice(me, (await params).id), { status: 201 });
  } catch (err) {
    return asResponse(err);
  }
}
