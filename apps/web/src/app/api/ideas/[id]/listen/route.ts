import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { isIdeaRef, listenAudio } from "@/server/listen";

/** GET /api/ideas/{id}/listen → the whole idea read aloud (audio/mpeg), part by part in E-ENUMS.part order, from the
 * masked script (DEC-108 (4), L-LISTEN/1). Supports Range once cached. Desk and committee; behind desk.listen and
 * speech.hosted (503 `paused`). 503 `script_unavailable` or any error: the player uses the on-device voice. */
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("view_review_queue");
  if (me instanceof NextResponse) return me;
  const { id } = await params;
  if (!isIdeaRef(id)) return NextResponse.json({ error: "not_found" }, { status: 404 });
  return listenAudio(id, me.id, request.headers.get("range"));
}
