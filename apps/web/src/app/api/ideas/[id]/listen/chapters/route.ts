import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { isIdeaRef, listenChapters } from "@/server/listen";

/** GET /api/ideas/{id}/listen/chapters → { parts: [{ part, start_s }], duration_s }, each part's real length from
 * the audio (L-LISTEN/1); 202 { pending: true } until the audio is cached (a prefetch is queued). */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("view_review_queue");
  if (me instanceof NextResponse) return me;
  const { id } = await params;
  if (!isIdeaRef(id)) return NextResponse.json({ error: "not_found" }, { status: 404 });
  return listenChapters(id, me.id);
}
