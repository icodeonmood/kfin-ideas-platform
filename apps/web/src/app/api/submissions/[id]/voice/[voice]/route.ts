import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { removeVoice, voiceStatus } from "@/server/voice";

type Params = { params: Promise<{ id: string; voice: string }> };

/** GET /api/submissions/{id}/voice/{voice} — the owner's voice note: its state, and its text once ready. */
export async function GET(_request: NextRequest, { params }: Params) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const { id, voice } = await params;
  try {
    return NextResponse.json(await voiceStatus(me, id, voice), { headers: { "Cache-Control": "no-store" } });
  } catch (err) {
    return asResponse(err);
  }
}

/** DELETE /api/submissions/{id}/voice/{voice} — the recording and any held text go (the text is in the box now,
 * or the person threw the note away). */
export async function DELETE(_request: NextRequest, { params }: Params) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const { id, voice } = await params;
  try {
    await removeVoice(me, id, voice);
    return new NextResponse(null, { status: 204 });
  } catch (err) {
    return asResponse(err);
  }
}
