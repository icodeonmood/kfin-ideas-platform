import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { bodyOf, deviceOf, draftError, drafts, noStore } from "@/server/drafts";

/** PATCH /api/drafts/{id}/messages/{mid} `{ text, text_en? }` — the person changes their words: the box autosaving
 * (the client waits for a 2-second pause) or "Edit" on a sent message. Hidden again, saved at once, and the parts not
 * pinned are built again (A-API.drafts, L-DRAFT.autosave/1). `202` with the run id. */
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; mid: string }> },
) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const body = await bodyOf(request);
  try {
    const { id, mid } = await params;
    const path = `${encodeURIComponent(id)}/messages/${encodeURIComponent(mid)}`;
    const { body: out } = await drafts.write(me, deviceOf(request), "PATCH", path, {
      text: body.text,
      ...(typeof body.text_en === "string" ? { text_en: body.text_en } : {}),
    });
    return NextResponse.json(out, { status: 202, headers: noStore });
  } catch (err) {
    return draftError(err);
  }
}
