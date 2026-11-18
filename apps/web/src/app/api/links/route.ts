import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { addLink } from "@/server/files";
import { readJson } from "@/server/http";

/** POST /api/links `{ url, draft_id | idea_id | answer_id }` (A-API.files, C-FILE.uploader/3). Classed internal or
 * external by its domain only and stored sealed; never fetched (BLD-E001). Behind `submissions`. */
export async function POST(request: NextRequest) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  return addLink(me, await readJson(request));
}
