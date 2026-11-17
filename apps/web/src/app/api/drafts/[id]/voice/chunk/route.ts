import { NextResponse, type NextRequest } from "next/server";

import { parseSeq, VOICE_MAX_CHUNK_BYTES } from "@/lib/voice-stream";
import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { sendChunk } from "@/server/voice-stream";

/** POST /api/drafts/{id}/voice/chunk?stream={stream}&seq={n}, body: raw 16 kHz mono 16-bit PCM, about one second.
 * Relayed to the worker and on to Sarvam, never kept. Answers the words heard so far, for the sharer alone. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const header = request.headers.get("content-length");
  if (header === null) return NextResponse.json({ error: "length_required" }, { status: 411 });
  if (Number(header) > VOICE_MAX_CHUNK_BYTES)
    return NextResponse.json({ error: "chunk_too_large" }, { status: 413 });
  const seq = parseSeq(request.nextUrl.searchParams.get("seq"));
  if (seq === undefined) return NextResponse.json({ error: "seq_required" }, { status: 400 });
  const data = await request.arrayBuffer();
  if (data.byteLength > VOICE_MAX_CHUNK_BYTES)
    return NextResponse.json({ error: "chunk_too_large" }, { status: 413 });
  try {
    const stream = request.nextUrl.searchParams.get("stream") ?? "";
    return NextResponse.json(await sendChunk(me, (await params).id, stream, seq, data));
  } catch (err) {
    return asResponse(err);
  }
}
