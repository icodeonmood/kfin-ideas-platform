import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { jsonBody, patchSorting, readSorting } from "@/server/share";

type Ctx = { params: Promise<{ id: string }> };

/** GET /api/drafts/{id}/sorting: the sorting the draft suggests, or what the person confirmed (L-SORT). */
export async function GET(_request: NextRequest, { params }: Ctx) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  return readSorting(me, (await params).id);
}

/** PATCH /api/drafts/{id}/sorting: change a field, or `{confirm: true}` for every untouched suggestion
 * (L-SORT.rules/2–3). Behind `submissions`. */
export async function PATCH(request: NextRequest, { params }: Ctx) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  return patchSorting(me, (await params).id, await jsonBody(request));
}
