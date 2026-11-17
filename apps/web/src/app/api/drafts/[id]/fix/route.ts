import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { jsonBody, putFix, removeFix } from "@/server/share";

type Ctx = { params: Promise<{ id: string }> };

/** PUT /api/drafts/{id}/fix: the fix sheet's answers (S-05.fix, A-API.drafts). Returns `Fix` with `ready_count`;
 * amounts in any Indian form come back normalised. Behind `submissions`. */
export async function PUT(request: NextRequest, { params }: Ctx) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  return putFix(me, (await params).id, await jsonBody(request));
}

/** DELETE /api/drafts/{id}/fix: "Remove" takes the fix and its figures away. Behind `submissions`. */
export async function DELETE(_request: NextRequest, { params }: Ctx) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  return removeFix(me, (await params).id);
}
