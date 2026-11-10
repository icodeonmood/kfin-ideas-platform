import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { MAX_VOICE_BYTES, uploadVoice } from "@/server/voice";

/** POST /api/submissions/{id}/voice (multipart, field "file") — a voice note into quarantine (DEC-096). Behind
 * `capture.voice` and `submissions`. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const header = request.headers.get("content-length");
  if (header === null) return NextResponse.json({ error: "length_required" }, { status: 411 });
  if (Number(header) > MAX_VOICE_BYTES + 64 * 1024)
    return NextResponse.json({ error: "file_too_large" }, { status: 413 });
  const form = await request.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof Blob)) return NextResponse.json({ error: "file_required" }, { status: 400 });
  try {
    return NextResponse.json(await uploadVoice(me, (await params).id, file), { status: 201 });
  } catch (err) {
    return asResponse(err);
  }
}
