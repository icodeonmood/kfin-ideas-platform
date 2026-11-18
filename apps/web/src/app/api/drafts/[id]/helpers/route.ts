import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { jsonBody, putHelpers } from "@/server/share";

type Ctx = { params: Promise<{ id: string }> };

/** PUT /api/drafts/{id}/helpers `{ picks, text? }`: "Who would help" (S-05 part 6, A-API.drafts). Behind
 * `submissions`. */
export async function PUT(request: NextRequest, { params }: Ctx) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  return putHelpers(me, (await params).id, await jsonBody(request));
}
