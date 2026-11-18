import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { deskHide, hideErrorResponse } from "@/server/hide";
import { readJson } from "@/server/http";

/** POST /api/desk/ideas/{id}/hide — S-R2 "Hide this" (L-HIDE.rules/7): the review desk and the Ones Committee mask
 * the selected words at once in every copy. Body `{ source: { kind, id }, start, end, selected? }`, offsets in the
 * text they read (UTF-16 units) and the masked words selected there. Returns the `HiddenDetail`. Errors: 409 `stale`
 * when the text changed under the selection, 422 `selection_too_long`, 403 `forbidden` on the reviewer's own idea
 * (`server/hide.ts`). Never behind a switch: hiding only ever protects someone. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("hide_for_desk");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await deskHide(me, (await params).id, await readJson(request)), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (err) {
    return hideErrorResponse(err);
  }
}
