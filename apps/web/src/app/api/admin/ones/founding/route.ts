import { NextResponse, type NextRequest } from "next/server";

import { programmeCall } from "@/server/admin/programme";
import { authorize } from "@/server/auth/authorize";
import { readJson } from "@/server/http";

/** POST /api/admin/ones/founding {email, reason} — mark a Founding One (L-ONES.rules/1, DEC-106). Admin only;
 * audited by the worker. */
export async function POST(request: NextRequest) {
  const me = await authorize("run_programme");
  if (me instanceof NextResponse) return me;
  const body = await readJson(request);
  return programmeCall("POST", "/ones/founding", me.id, { email: body.email, reason: body.reason });
}
