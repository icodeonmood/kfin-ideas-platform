import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { sendView } from "@/server/share";

/** GET /api/drafts/{id}/send: the Send part's last look, the declaration, and what would stop Submit
 * (S-05 part 7, L-SUBMIT.pre). */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  return sendView(me, (await params).id);
}
