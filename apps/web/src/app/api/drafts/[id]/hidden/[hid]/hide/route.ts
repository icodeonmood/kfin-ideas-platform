import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { hideAgain, hideErrorResponse } from "@/server/hide";

/** POST /api/drafts/{id}/hidden/{hid}/hide — C-HIDDEN "Hide it": reverses "Show it" (L-HIDE.rules/6). The person
 * whose words they are, only; audited. Never behind a switch: hiding only ever protects someone. */
export async function POST(_request: NextRequest, { params }: { params: Promise<{ id: string; hid: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const { id, hid } = await params;
  try {
    return NextResponse.json(await hideAgain(me, id, hid), { headers: { "Cache-Control": "no-store" } });
  } catch (err) {
    return hideErrorResponse(err);
  }
}
