import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { deviceOf, draftError, drafts, noStore } from "@/server/drafts";

/** POST /api/drafts/{id}/runs — build the parts again: "Try again" after every part failed (L-DRAFT.errors), or the
 * one build after the S1 interview's answers (L-DRAFT.parts/10). `202 { run_id }`; `assistant_off` while the
 * assistant is paused (DEC-105), when the person fills the parts by hand. Addition to A-API.drafts. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  try {
    const id = encodeURIComponent((await params).id);
    const { body } = await drafts.write(me, deviceOf(request), "POST", `${id}/runs`);
    return NextResponse.json(body, { status: 202, headers: noStore });
  } catch (err) {
    return draftError(err);
  }
}
