import { NextResponse, type NextRequest } from "next/server";

import { badRef, IDEA_REF, MARKS, programmeCall } from "@/server/admin/programme";
import { authorize } from "@/server/auth/authorize";

/** POST /api/admin/ideas/{id}/measurements/{mark}/finance — L-IMPACT/3: a second admin, never the one who entered
 * the figures, records Finance's confirmation; only then does money show. Audited by the worker. */
export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string; mark: string }> },
) {
  const me = await authorize("run_programme");
  if (me instanceof NextResponse) return me;
  const { id: ref, mark } = await params;
  if (!IDEA_REF.test(ref)) return badRef();
  if (!(MARKS as readonly string[]).includes(mark))
    return NextResponse.json({ error: { code: "not_found", message: "", field: "mark" } }, { status: 404 });
  return programmeCall("POST", `/ideas/${ref}/measurements/${mark}/finance`, me.id);
}
