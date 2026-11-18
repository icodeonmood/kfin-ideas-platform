import { NextResponse, type NextRequest } from "next/server";

import { badRef, IDEA_REF, programmeCall } from "@/server/admin/programme";
import { authorize } from "@/server/auth/authorize";
import { readJson } from "@/server/http";

type Params = { params: Promise<{ id: string }> };

/** POST /api/admin/ideas/{id}/wall-removal {reason} — "Take off the Wall" (DEC-106): the review desk or an admin
 * takes an idea's summary off the Wall. Audited by the worker. */
export async function POST(request: NextRequest, { params }: Params) {
  const me = await authorize("take_off_wall");
  if (me instanceof NextResponse) return me;
  const ref = (await params).id;
  if (!IDEA_REF.test(ref)) return badRef();
  const body = await readJson(request);
  return programmeCall("POST", `/ideas/${ref}/wall-removal`, me.id, { reason: body.reason });
}

/** DELETE /api/admin/ideas/{id}/wall-removal {reason} — put it back on the Wall. Audited by the worker. */
export async function DELETE(request: NextRequest, { params }: Params) {
  const me = await authorize("take_off_wall");
  if (me instanceof NextResponse) return me;
  const ref = (await params).id;
  if (!IDEA_REF.test(ref)) return badRef();
  const body = await readJson(request);
  return programmeCall("POST", `/ideas/${ref}/wall-restore`, me.id, { reason: body.reason });
}
