import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { jsonBody, submitDraft } from "@/server/share";

/** POST /api/drafts/{id}/submit `{declaration_version}`, with an `Idempotency-Key` header: sends the idea and
 * returns what S-06 "Just shared" shows (L-SUBMIT.send). A retry never creates two ideas. Behind `submissions`. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  return submitDraft(me, (await params).id, await jsonBody(request), request.headers);
}
