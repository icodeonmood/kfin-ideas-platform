import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { hideErrorResponse, showHidden } from "@/server/hide";
import { readJson } from "@/server/http";

/** POST /api/drafts/{id}/hidden/{hid}/show — C-HIDDEN "Show it" (L-HIDE.rules/6). Body `{ reason }`, one of the
 * three. The person whose words they are, only; audited and shown to the desk as "Shown, because …". */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; hid: string }> },
) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const { id, hid } = await params;
  try {
    const body = await readJson(request);
    return NextResponse.json(await showHidden(me, id, hid, body.reason), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (err) {
    return hideErrorResponse(err);
  }
}
