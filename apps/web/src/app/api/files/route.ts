import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { addFile } from "@/server/files";

/** POST /api/files (A-API.files; multipart: `file` and one of `draft_id`, `idea_id`, `answer_id`). The FileItem comes
 * back `checking`; the worker scans it, reads its text and hides customers' details (L-HIDE.files). Behind
 * `attachments.upload` and `submissions` (lib/killswitch-routes.ts). */
export async function POST(request: NextRequest) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  return addFile(me, request);
}
