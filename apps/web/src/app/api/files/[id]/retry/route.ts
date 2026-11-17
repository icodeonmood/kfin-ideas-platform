import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { retryFile } from "@/server/files";

/** POST /api/files/{id}/retry ("Try again" on a file that did not upload): the checks run again on the kept copy.
 * The person who added it only. Behind `attachments.upload` and `submissions`. */
export async function POST(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  return retryFile(me, (await params).id);
}
