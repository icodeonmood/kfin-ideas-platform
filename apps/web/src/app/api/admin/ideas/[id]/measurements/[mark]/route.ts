import { NextResponse, type NextRequest } from "next/server";

import { badRef, IDEA_REF, MARKS, programmeCall } from "@/server/admin/programme";
import { authorize } from "@/server/auth/authorize";
import { readJson } from "@/server/http";

/** PUT /api/admin/ideas/{id}/measurements/{day_30|day_90} {time?, money?, effort?, scale?, sentence?} — L-IMPACT/2:
 * an admin enters what the fix changed, for the team that runs it. Money waits for Finance (L-IMPACT/3). Entering
 * may induct Ones and raise tiers (L-ONES.rules/1, /3). Admin only; audited by the worker. */
export async function PUT(request: NextRequest, { params }: { params: Promise<{ id: string; mark: string }> }) {
  const me = await authorize("run_programme");
  if (me instanceof NextResponse) return me;
  const { id: ref, mark } = await params;
  if (!IDEA_REF.test(ref)) return badRef();
  if (!(MARKS as readonly string[]).includes(mark))
    return NextResponse.json({ error: { code: "not_found", message: "", field: "mark" } }, { status: 404 });
  const body = await readJson(request);
  return programmeCall("PUT", `/ideas/${ref}/measurements/${mark}`, me.id, {
    time: body.time,
    money: body.money,
    effort: body.effort,
    scale: body.scale,
    sentence: body.sentence,
  });
}
