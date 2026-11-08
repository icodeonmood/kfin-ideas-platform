import { NextResponse, type NextRequest } from "next/server";

import { remove } from "@/server/attachments";
import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";

/** DELETE /api/submissions/{id}/attachments/{att} — remove a file from my draft (store and record). */
export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string; att: string }> },
) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const { id, att } = await params;
  try {
    await remove(me, id, att);
    return new NextResponse(null, { status: 204 });
  } catch (err) {
    return asResponse(err);
  }
}
