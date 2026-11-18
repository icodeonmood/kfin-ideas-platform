import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { viewFile } from "@/server/files";

/**
 * GET /api/files/{id}/view (A-API.files, C-FILE.view): the checked copy only. Checked files open for the person
 * who added them, the idea's sharers and crew, the review desk and the Ones Committee; a file with a customer detail
 * for the person who added it, the review desk and the Ones Committee only (DEC-107). The worker decides and audits
 * each opening; anything not yet checked, and anyone else, gets 403 or 404. Behind `attachments.open`.
 */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("open_attachments");
  if (me instanceof NextResponse) return me;
  return viewFile(me, (await params).id);
}
