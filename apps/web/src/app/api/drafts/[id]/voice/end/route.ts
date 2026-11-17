import { NextResponse, type NextRequest } from "next/server";

import { asResponse, readJson } from "@/server/http";
import { authorize } from "@/server/auth/authorize";
import { endVoice } from "@/server/voice-stream";

/** POST /api/drafts/{id}/voice/end { stream } → the finished note for the sharer: their own words (`text`, `spans`)
 * and the English copy (`text_en`, labelled `text_en_label`), or `{ state: "failed", failure }`. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await endVoice(me, (await params).id, (await readJson(request)).stream));
  } catch (err) {
    return asResponse(err);
  }
}
