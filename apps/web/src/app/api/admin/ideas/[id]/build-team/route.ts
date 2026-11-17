import { NextResponse, type NextRequest } from "next/server";

import { badRef, IDEA_REF, programmeCall } from "@/server/admin/programme";
import { authorize } from "@/server/auth/authorize";
import { readJson } from "@/server/http";

/** POST /api/admin/ideas/{id}/build-team {name, lead_email, member_emails} — L-DECIDE.after "Team chosen": the
 * picked idea moves to Being built. Admin only; audited by the worker. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("run_programme");
  if (me instanceof NextResponse) return me;
  const ref = (await params).id;
  if (!IDEA_REF.test(ref)) return badRef();
  const body = await readJson(request);
  return programmeCall("POST", `/ideas/${ref}/build-team`, me.id, {
    name: body.name,
    lead_email: body.lead_email,
    member_emails: body.member_emails,
  });
}
