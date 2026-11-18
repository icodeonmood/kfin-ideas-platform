import { NextResponse, type NextRequest } from "next/server";

import { programmeCall } from "@/server/admin/programme";
import { authorize } from "@/server/auth/authorize";

/** DELETE /api/admin/ones/{id} — remove a One (DEC-106): their number rests and they leave the Wall, Home and the
 * office screen. Admin only; the worker calls lane E's `wall.ones.remove_one`, which audits it (BLD-A217). */
export async function DELETE(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("run_programme");
  if (me instanceof NextResponse) return me;
  const id = (await params).id;
  if (!/^[1-9][0-9]{0,17}$/.test(id))
    return NextResponse.json({ error: { code: "not_found", message: "" } }, { status: 404 });
  return programmeCall("POST", `/ones/${id}/remove`, me.id);
}
