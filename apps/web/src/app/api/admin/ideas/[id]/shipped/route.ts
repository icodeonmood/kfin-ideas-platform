import { NextResponse, type NextRequest } from "next/server";

import { badRef, IDEA_REF, programmeCall } from "@/server/admin/programme";
import { authorize } from "@/server/auth/authorize";

/** POST /api/admin/ideas/{id}/shipped — L-DECIDE.after "Shipped": the sharer's track reaches Shipped and the 30- and
 * 90-day measurements are scheduled (L-IMPACT/1). Admin only; audited by the worker. */
export async function POST(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("run_programme");
  if (me instanceof NextResponse) return me;
  const ref = (await params).id;
  if (!IDEA_REF.test(ref)) return badRef();
  return programmeCall("POST", `/ideas/${ref}/shipped`, me.id);
}
